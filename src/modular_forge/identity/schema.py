from modular_forge.shared.persistence import ColumnSpec as C
from modular_forge.shared.persistence import TableSpec

TABLES = [
    TableSpec(
        "accounts",
        (
            C("email", length=254),
            C("username", length=64),
            C("password_hash", "text"),
            C("role", length=20),
            C("active", "bool"),
            C("verified", "bool"),
            C("auth_version", "int"),
            C("failed_logins", "int"),
            C("locked_until", "int"),
            C("created_at", "int"),
            C("deactivated_at", "int", nullable=True),
        ),
        unique=(("email",), ("username",)),
        indexes=(("role",),),
    )
]
