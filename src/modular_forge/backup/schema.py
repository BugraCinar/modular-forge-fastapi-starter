from modular_forge.shared.persistence import ColumnSpec as C
from modular_forge.shared.persistence import TableSpec

TABLES = [
    TableSpec(
        "backup_jobs",
        (
            C("file_name", length=80),
            C("created_by", length=64),
            C("created_at", "int"),
            C("status", length=16),
        ),
    )
]
