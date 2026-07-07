from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.audit_events import AuditEventRead
from app.services.audit_events import list_audit_events

router = APIRouter(prefix="/api/audit-events", tags=["audit-events"])


@router.get("", response_model=list[AuditEventRead])
def get_audit_events(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[AuditEventRead]:
    return list_audit_events(db, limit=limit)
