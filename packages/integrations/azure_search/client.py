from __future__ import annotations

from typing import Any

import structlog
from azure.core.credentials import AzureKeyCredential
from azure.search.documents.aio import SearchClient

logger = structlog.get_logger()


class AzureSearchClient:
    """Async wrapper around Azure AI Search for RAG retrieval.

    Authenticates with an API key when ``api_key`` is provided; otherwise
    falls back to ``DefaultAzureCredential`` (managed identity).
    Use ``from_settings(settings)`` in production; inject a mock in tests.
    """

    def __init__(
        self,
        endpoint: str,
        index_name: str,
        api_key: str = "",
    ) -> None:
        credential: AzureKeyCredential | Any
        if api_key:
            credential = AzureKeyCredential(api_key)
        else:
            from azure.identity.aio import DefaultAzureCredential

            credential = DefaultAzureCredential()
        self._client = SearchClient(
            endpoint=endpoint,
            index_name=index_name,
            credential=credential,
        )

    async def search(
        self,
        query: str,
        top: int = 10,
        *,
        vector_text: str | None = None,
        filter_expr: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return up to *top* hybrid-search results as plain ``dict`` objects."""
        results: list[dict[str, Any]] = []
        search_kwargs: dict[str, Any] = {"search_text": query, "top": top}
        if filter_expr:
            search_kwargs["filter"] = filter_expr
        if vector_text:
            try:
                from azure.search.documents.models import VectorizableTextQuery

                search_kwargs["vector_queries"] = [
                    VectorizableTextQuery(
                        text=vector_text, k_nearest_neighbors=top, fields="content_vector"
                    )
                ]
            except Exception:
                # Fall back to keyword/semantic-only search if vector query types are unavailable.
                logger.warning("azure_search_vector_query_unavailable")

        async for result in await self._client.search(**search_kwargs):
            results.append(dict(result))
        return results

    async def aclose(self) -> None:
        await self._client.close()

    async def __aenter__(self) -> AzureSearchClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    @classmethod
    def from_settings(cls, settings: Any) -> AzureSearchClient:
        key_field = settings.azure_search_api_key
        api_key = (
            key_field.get_secret_value()
            if hasattr(key_field, "get_secret_value")
            else str(key_field)
        )
        return cls(
            endpoint=settings.azure_search_endpoint,
            index_name=settings.azure_search_index,
            api_key=api_key,
        )
