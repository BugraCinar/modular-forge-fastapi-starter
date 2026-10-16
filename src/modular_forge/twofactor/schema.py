from modular_forge.shared.persistence import ColumnSpec as C
from modular_forge.shared.persistence import TableSpec

TABLES = [
    TableSpec(
        "two_factor_credentials",
        (
            C("encrypted_secret", "text"),
            C("enabled", "bool"),
            C("pending_until", "int"),
            C("last_step", "int"),
        ),
    ),
    TableSpec(
        "two_factor_challenges",
        (
            C("account_id", length=64),
            C("auth_version", "int"),
            C("attempts", "int"),
            C("used", "bool"),
            C("expires_at", "int"),
        ),
        indexes=(("expires_at",),),
    ),
]
