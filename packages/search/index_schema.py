from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class SearchDocument(BaseModel):
    """Represents a single document in the Azure AI Search index."""

    id: str
    source_type: str  # runbook | prior_fix | documentation | source_code
    title: str
    content: str
    content_vector: list[float] = Field(default_factory=list)
    url: str | None = None
    repo: str | None = None
    file_path: str | None = None
    exception_type: str | None = None
    created_at: str = Field(default_factory=lambda: datetime.now(tz=UTC).isoformat())

    def to_index_dict(self) -> dict[str, Any]:
        d = self.model_dump(exclude_none=False)
        # Azure AI Search requires None to be omitted or sent as null
        return {
            k: v
            for k, v in d.items()
            if v is not None or k in ("url", "repo", "file_path", "exception_type")
        }


def create_or_update_index(endpoint: str, index_name: str, api_key: str = "") -> None:
    """Create or update the Azure AI Search index schema (idempotent)."""
    from azure.core.credentials import AzureKeyCredential
    from azure.search.documents.indexes import SearchIndexClient
    from azure.search.documents.indexes.models import (
        HnswAlgorithmConfiguration,
        SearchField,
        SearchFieldDataType,
        SearchIndex,
        SemanticConfiguration,
        SemanticField,
        SemanticPrioritizedFields,
        SemanticSearch,
        SimpleField,
        VectorSearch,
        VectorSearchProfile,
    )

    credential: Any
    if api_key:
        credential = AzureKeyCredential(api_key)
    else:
        from azure.identity import DefaultAzureCredential

        credential = DefaultAzureCredential()

    client = SearchIndexClient(endpoint=endpoint, credential=credential)

    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True, filterable=True),
        SimpleField(
            name="source_type", type=SearchFieldDataType.String, filterable=True, facetable=True
        ),
        SearchField(name="title", type=SearchFieldDataType.String, searchable=True),
        SearchField(name="content", type=SearchFieldDataType.String, searchable=True),
        SearchField(
            name="content_vector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=1536,
            vector_search_profile_name="remediai-hnsw",
        ),
        SimpleField(name="url", type=SearchFieldDataType.String),
        SimpleField(name="repo", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="file_path", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="exception_type", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="created_at", type=SearchFieldDataType.DateTimeOffset, sortable=True),
    ]

    vector_search = VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(name="remediai-hnsw-algo")],
        profiles=[
            VectorSearchProfile(
                name="remediai-hnsw", algorithm_configuration_name="remediai-hnsw-algo"
            )
        ],
    )

    semantic_config = SemanticConfiguration(
        name="remediai-semantic",
        prioritized_fields=SemanticPrioritizedFields(
            title_field=SemanticField(field_name="title"),
            content_fields=[SemanticField(field_name="content")],
        ),
    )
    semantic_search = SemanticSearch(configurations=[semantic_config])

    index = SearchIndex(
        name=index_name,
        fields=fields,
        vector_search=vector_search,
        semantic_search=semantic_search,
    )

    client.create_or_update_index(index)
