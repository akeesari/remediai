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

    async def search(self, query: str, top: int = 10) -> list[dict[str, Any]]:
        """Return up to *top* results for *query*, each as a plain ``dict``."""
        results: list[dict[str, Any]] = []
        async for result in await self._client.search(search_text=query, top=top):
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
        return cls(
            endpoint=settings.azure_search_endpoint,
            index_name=settings.azure_search_index,
            api_key=settings.azure_search_api_key,
        )
