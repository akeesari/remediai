from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal, cast
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.config import Settings, get_settings
from apps.api.schemas.targets import (
    DiscoveredTarget,
    MonitorTarget,
    UpsertMonitorTargetsRequest,
    UpsertMonitorTargetsResponse,
)
from packages.data_access.models.monitor_target_orm import MonitorTargetOrm
from packages.data_access.session import get_db_session


def _require_targets_access(
    x_remediai_admin_token: str | None = Header(default=None, alias="X-Remediai-Admin-Token"),
) -> None:
    settings: Settings = get_settings()
    if settings.local_mode:
        return

    expected = settings.target_api_token.strip()
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Target API token is not configured for non-local mode.",
        )
    if x_remediai_admin_token != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


router = APIRouter(
    prefix="/api/v1/targets",
    tags=["targets"],
    dependencies=[Depends(_require_targets_access)],
)


@router.get("", response_model=list[MonitorTarget])
async def list_targets(
    environment: Literal["local", "kubernetes"] = Query(
        default="local", pattern="^(local|kubernetes)$"
    ),
    enabled_only: bool = Query(default=False),
    db: AsyncSession = Depends(get_db_session),
) -> list[MonitorTarget]:
    stmt: Select[tuple[MonitorTargetOrm]] = (
        select(MonitorTargetOrm)
        .where(MonitorTargetOrm.environment == environment)
        .order_by(MonitorTargetOrm.target_type.asc(), MonitorTargetOrm.display_name.asc())
    )
    if enabled_only:
        stmt = stmt.where(MonitorTargetOrm.enabled.is_(True))

    rows = await db.execute(stmt)
    targets = list(rows.scalars().all())

    return [
        MonitorTarget(
            id=t.id,
            environment=cast(Literal["local", "kubernetes"], t.environment),
            target_type=cast(Literal["container", "namespace", "workload"], t.target_type),
            target_key=t.target_key,
            display_name=t.display_name,
            enabled=t.enabled,
            metadata=t.metadata_json,
            created_at=t.created_at,
            updated_at=t.updated_at,
        )
        for t in targets
    ]


@router.put("", response_model=UpsertMonitorTargetsResponse)
async def upsert_targets(
    payload: UpsertMonitorTargetsRequest,
    db: AsyncSession = Depends(get_db_session),
) -> UpsertMonitorTargetsResponse:
    updated = 0
    now = datetime.now(UTC)

    for target in payload.targets:
        existing = await db.scalar(
            select(MonitorTargetOrm).where(
                MonitorTargetOrm.environment == payload.environment,
                MonitorTargetOrm.target_type == target.target_type,
                MonitorTargetOrm.target_key == target.target_key,
            )
        )

        if existing is None:
            db.add(
                MonitorTargetOrm(
                    id=uuid4(),
                    environment=payload.environment,
                    target_type=target.target_type,
                    target_key=target.target_key,
                    display_name=target.display_name,
                    enabled=target.enabled,
                    metadata_json=target.metadata,
                    created_at=now,
                    updated_at=now,
                )
            )
            updated += 1
            continue

        existing.display_name = target.display_name
        existing.enabled = target.enabled
        existing.metadata_json = target.metadata
        existing.updated_at = now
        updated += 1

    return UpsertMonitorTargetsResponse(updated=updated)


@router.get("/discovered", response_model=list[DiscoveredTarget])
async def discover_targets(
    environment: Literal["local", "kubernetes"] = Query(
        default="local", pattern="^(local|kubernetes)$"
    ),
) -> list[DiscoveredTarget]:
    settings = get_settings()

    if environment == "local":
        return _discover_local_targets(settings.local_log_bridge_containers)

    return _discover_kubernetes_targets(
        raw_namespaces=str(getattr(settings, "kubernetes_discovery_namespaces", "") or ""),
        raw_workloads=str(getattr(settings, "kubernetes_discovery_workloads", "") or ""),
    )


def _discover_local_targets(raw_containers: str) -> list[DiscoveredTarget]:
    names = [name.strip() for name in raw_containers.split(",") if name.strip()]
    unique_names = sorted(set(names))
    return [
        DiscoveredTarget(
            environment="local",
            target_type="container",
            target_key=name,
            display_name=name,
            metadata={},
        )
        for name in unique_names
    ]


def _discover_kubernetes_targets(
    raw_namespaces: str,
    raw_workloads: str,
) -> list[DiscoveredTarget]:
    discovered: list[DiscoveredTarget] = []

    for namespace in sorted({v.strip() for v in raw_namespaces.split(",") if v.strip()}):
        discovered.append(
            DiscoveredTarget(
                environment="kubernetes",
                target_type="namespace",
                target_key=namespace,
                display_name=namespace,
                metadata={},
            )
        )

    for entry in sorted({v.strip() for v in raw_workloads.split(",") if v.strip()}):
        if "/" not in entry:
            continue
        namespace, workload = entry.split("/", 1)
        namespace = namespace.strip()
        workload = workload.strip()
        if not namespace or not workload:
            continue
        discovered.append(
            DiscoveredTarget(
                environment="kubernetes",
                target_type="workload",
                target_key=f"{namespace}/{workload}",
                display_name=f"{namespace}/{workload}",
                metadata={"namespace": namespace, "workload": workload},
            )
        )

    return discovered
