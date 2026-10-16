from modular_forge.shared.persistence import ColumnSpec as C
from modular_forge.shared.persistence import TableSpec

TABLES = [
    TableSpec(
        "profiles",
        (
            C("display_name", length=120),
            C("biography", "text"),
            C("image_key", length=160, nullable=True),
            C("image_url", "text", nullable=True),
        ),
    )
]
