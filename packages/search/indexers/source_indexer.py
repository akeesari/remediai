from __future__ import annotations

import hashlib
import re
from typing import Protocol

import structlog

from packages.search.chunker import chunk_text
from packages.search.index_schema import SearchDocument

logger = structlog.get_logger()


class ReposClientProtocol(Protocol):
    """Minimal interface required by the source indexer."""

    repository: str

    async def list_files(self, path_prefix: str, extension: str = ".cs") -> list[str]: ...

    async def get_file_content(self, file_path: str) -> str | None: ...


_COMMENT_PATTERN = re.compile(r"/\*.*?\*/|//[^\n]*", re.DOTALL)


def _strip_comments(source: str) -> str:
    return _COMMENT_PATTERN.sub("", source)


async def index_source_files(
    client: ReposClientProtocol,
    path_prefix: str = "src/",
    extension: str = ".cs",
) -> list[SearchDocument]:
    """Fetch source files from ADO Repos and return indexable documents.

    *extension* defaults to ``.cs`` for backward compatibility.  Pass a different
    extension (e.g. ``.py``, ``.ts``, ``.java``) to index other languages.
    """
    documents: list[SearchDocument] = []
    log = logger.bind(indexer="source", repo=client.repository, prefix=path_prefix)

    file_paths = await client.list_files(path_prefix=path_prefix, extension=extension)
    log.info("source_index_start", file_count=len(file_paths))

    for file_path in file_paths:
        content = await client.get_file_content(file_path)
        if not content:
            continue

        stripped = _strip_comments(content)
        chunks = chunk_text(stripped)

        for idx, chunk in enumerate(chunks):
            source_id = f"source::{client.repository}::{file_path}"
            chunk_id = hashlib.sha256(f"{source_id}::chunk{idx}".encode()).hexdigest()[:32]
            documents.append(
                SearchDocument(
                    id=chunk_id,
                    source_type="source_code",
                    title=file_path.split("/")[-1],
                    content=chunk,
                    repo=client.repository,
                    file_path=file_path,
                )
            )

    log.info("source_index_done", document_count=len(documents))
    return documents
