from fastapi import APIRouter, Depends, Query

from modular_forge.security.dependencies import administrator, runtime

router = APIRouter(prefix="/api/v1/admin/audit", tags=["Audit"])


@router.get("")
def audit_events(
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    actor=Depends(administrator),
    rt=Depends(runtime),
):
    with rt.database.transaction() as tx:
        items = tx.find(
            "audit_events", limit=limit, offset=offset, order_by="created_at", descending=True
        )
        total = tx.count("audit_events")
    return {
        "items": [{k: v for k, v in row.items() if k != "revision"} for row in items],
        "total": total,
    }
