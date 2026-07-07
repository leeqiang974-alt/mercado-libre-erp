from sqlalchemy.orm import Session

from app.models.audit_event import AuditEvent
from app.schemas.audit_events import AuditEventRead


def create_audit_event(
    db: Session,
    actor_type: str,
    actor_id: str,
    action: str,
    entity_type: str,
    entity_id: str,
    before: dict | None = None,
    after: dict | None = None,
) -> AuditEvent:
    event = AuditEvent(
        actor_type=actor_type,
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before_json=before or {},
        after_json=after or {},
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def list_audit_events(db: Session, limit: int = 100) -> list[AuditEventRead]:
    rows = db.query(AuditEvent).order_by(AuditEvent.id.desc()).limit(limit).all()
    return [to_audit_event_read(row) for row in rows]


def to_audit_event_read(event: AuditEvent) -> AuditEventRead:
    return AuditEventRead(
        id=event.id,
        actor_type=event.actor_type,
        actor_id=event.actor_id,
        action=event.action,
        entity_type=event.entity_type,
        entity_id=event.entity_id,
        before=event.before_json or {},
        after=event.after_json or {},
        created_at=event.created_at,
    )
