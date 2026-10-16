import logging
import time
from uuid import uuid4

logger = logging.getLogger(__name__)


class DatabaseAudit:
    def __init__(self, database):
        self.database = database

    def record(self, event, actor_id, target_id=None):
        try:
            with self.database.transaction() as tx:
                tx.insert(
                    "audit_events",
                    {
                        "id": str(uuid4()),
                        "event": event,
                        "actor_id": actor_id,
                        "target_id": target_id,
                        "created_at": int(time.time()),
                    },
                )
        except Exception:
            # Audit sink failures must not turn a committed account operation into a failed request.
            logger.error("Audit sink unavailable; event=%s", event)
