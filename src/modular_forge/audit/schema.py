from modular_forge.shared.persistence import ColumnSpec as C
from modular_forge.shared.persistence import TableSpec

TABLES = [
    TableSpec(
        "audit_events",
        (
            C("event", length=80),
            C("actor_id", length=64, nullable=True),
            C("target_id", length=64, nullable=True),
            C("created_at", "int"),
        ),
        indexes=(("created_at",), ("actor_id",)),
    )
]
