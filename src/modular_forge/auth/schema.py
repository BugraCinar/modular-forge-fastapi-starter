from modular_forge.shared.persistence import ColumnSpec as C
from modular_forge.shared.persistence import TableSpec

TABLES = [
    TableSpec(
        "auth_tokens",
        (
            C("account_id", length=64),
            C("kind", length=24),
            C("family", length=64),
            C("used", "bool"),
            C("expires_at", "int"),
            C("created_at", "int"),
            C("auth_version", "int"),
            C("context", "json"),
        ),
        indexes=(("account_id", "kind"), ("family",), ("expires_at",)),
    )
]
