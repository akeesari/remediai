#!/usr/bin/env python3
"""CLI to populate the Azure AI Search index with runbooks, source code, and prior fixes.

Usage:
    python scripts/populate_search_index.py --source all
    python scripts/populate_search_index.py --source runbooks
    python scripts/populate_search_index.py --source prior_fixes
    python scripts/populate_search_index.py --source source
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Ensure the repo root is on sys.path when running as a script
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import structlog  # noqa: E402

logger = structlog.get_logger()

_RUNBOOKS_DIR = _REPO_ROOT / "docs" / "runbooks"
_BATCH_SIZE = 50
_MAX_RETRIES = 3


def _build_search_upload_client(settings: object) -> object:
    from azure.core.credentials import AzureKeyCredential
    from azure.search.documents import SearchClient

    api_key: str = getattr(settings, "azure_search_api_key", "")
    endpoint: str = getattr(settings, "azure_search_endpoint", "")
    index_name: str = getattr(settings, "search_index_name", "remediai-incidents")

    if api_key:
        credential = AzureKeyCredential(api_key)
    else:
        from azure.identity import DefaultAzureCredential

        credential = DefaultAzureCredential()

    return SearchClient(endpoint=endpoint, index_name=index_name, credential=credential)


async def _generate_embeddings(texts: list[str], settings: object) -> list[list[float]]:
    """Batch-embed texts using Azure OpenAI with exponential back-off."""
    from langchain_openai import AzureOpenAIEmbeddings

    embeddings = AzureOpenAIEmbeddings(
        azure_endpoint=getattr(settings, "azure_openai_endpoint", ""),
        azure_deployment=getattr(settings, "openai_embedding_deployment", ""),
        model=getattr(settings, "openai_embedding_model", "text-embedding-3-small"),
        api_version="2024-02-01",
    )

    results: list[list[float]] = []
    for i in range(0, len(texts), _BATCH_SIZE):
        batch = texts[i : i + _BATCH_SIZE]
        for attempt in range(_MAX_RETRIES):
            try:
                batch_results = await embeddings.aembed_documents(batch)
                results.extend(batch_results)
                break
            except Exception as exc:
                if attempt == _MAX_RETRIES - 1:
                    raise
                wait = 2**attempt
                logger.warning("embedding_retry", attempt=attempt + 1, wait=wait, error=str(exc))
                await asyncio.sleep(wait)

    return results


async def _upload_documents(documents: list[object], settings: object) -> None:
    """Upload documents to Azure AI Search in batches."""
    upload_client = _build_search_upload_client(settings)
    total = len(documents)
    logger.info("upload_start", total=total)

    for i in range(0, total, _BATCH_SIZE):
        batch = documents[i : i + _BATCH_SIZE]
        batch_dicts = [doc.to_index_dict() for doc in batch]  # type: ignore[union-attr]
        upload_client.upload_documents(documents=batch_dicts)  # type: ignore[attr-defined]
        logger.info("upload_progress", uploaded=min(i + _BATCH_SIZE, total), total=total)

    logger.info("upload_complete", total=total)


async def run_runbooks(settings: object, embed: bool) -> None:
    from packages.search.indexers.runbook_indexer import index_runbooks

    if not _RUNBOOKS_DIR.exists():
        logger.warning("runbooks_dir_missing", path=str(_RUNBOOKS_DIR))
        return

    docs = index_runbooks(_RUNBOOKS_DIR)
    if not docs:
        logger.info("no_runbooks_found")
        return

    if embed:
        vectors = await _generate_embeddings([d.content for d in docs], settings)
        for doc, vec in zip(docs, vectors, strict=True):
            doc.content_vector = vec

    await _upload_documents(docs, settings)


async def run_source(settings: object, embed: bool) -> None:
    from packages.integrations.azure_devops.client import AzureDevOpsClient
    from packages.search.indexers.source_indexer import index_source_files

    client = AzureDevOpsClient.from_settings(settings)
    path_prefix: str = getattr(settings, "ado_source_path_prefix", "src/")
    docs = await index_source_files(client, path_prefix=path_prefix)

    if not docs:
        logger.info("no_source_files_found")
        return

    if embed:
        vectors = await _generate_embeddings([d.content for d in docs], settings)
        for doc, vec in zip(docs, vectors, strict=True):
            doc.content_vector = vec

    await _upload_documents(docs, settings)


async def run_prior_fixes(settings: object, embed: bool) -> None:
    from sqlalchemy.ext.asyncio import AsyncSession

    from apps.api.core.database import get_engine
    from packages.search.indexers.prior_fix_indexer import index_prior_fixes

    engine = get_engine(settings)
    async with AsyncSession(engine) as session:
        docs = await index_prior_fixes(session)

    if not docs:
        logger.info("no_prior_fixes_found")
        return

    if embed:
        vectors = await _generate_embeddings([d.content for d in docs], settings)
        for doc, vec in zip(docs, vectors, strict=True):
            doc.content_vector = vec

    await _upload_documents(docs, settings)


async def main(source: str, embed: bool) -> int:
    from apps.api.core.config import get_settings
    from packages.search.index_schema import create_or_update_index

    settings = get_settings()
    endpoint: str = getattr(settings, "azure_search_endpoint", "")
    index_name: str = getattr(settings, "search_index_name", "remediai-incidents")
    api_key: str = getattr(settings, "azure_search_api_key", "")

    logger.info("index_ensure", index=index_name)
    create_or_update_index(endpoint=endpoint, index_name=index_name, api_key=api_key)

    if source in ("runbooks", "all"):
        await run_runbooks(settings, embed)
    if source in ("source", "all"):
        await run_source(settings, embed)
    if source in ("prior_fixes", "all"):
        await run_prior_fixes(settings, embed)

    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Populate the Azure AI Search index.")
    parser.add_argument(
        "--source",
        choices=["runbooks", "source", "prior_fixes", "all"],
        default="all",
        help="Which source(s) to index (default: all).",
    )
    parser.add_argument(
        "--no-embed",
        action="store_true",
        help="Skip embedding generation (useful for dry-run or testing).",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    sys.exit(asyncio.run(main(source=args.source, embed=not args.no_embed)))
