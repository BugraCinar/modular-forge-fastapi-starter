"""Initial immutable SQL schema, including optional sidecar tables."""

import json
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def snapshot():
    return json.loads(Path(__file__).with_name("0001_schema.json").read_text(encoding="utf-8"))


def upgrade():
    for table in snapshot():
        columns: list[sa.Column] = [
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("revision", sa.Integer(), nullable=False),
        ]
        for field in table["columns"]:
            kind: Any = {
                "str": sa.String(field["length"]),
                "text": sa.Text(),
                "int": sa.BigInteger(),
                "bool": sa.Boolean(),
                "json": sa.JSON(),
            }[field["kind"]]
            columns.append(sa.Column(field["name"], kind, nullable=field["nullable"]))
        op.create_table(table["name"], *columns)
        for fields in table["unique"]:
            op.create_index(
                f"uq_{table['name']}_{'_'.join(fields)}", table["name"], fields, unique=True
            )
        for fields in table["indexes"]:
            op.create_index(f"ix_{table['name']}_{'_'.join(fields)}", table["name"], fields)


def downgrade():
    for table in reversed(snapshot()):
        op.drop_table(table["name"])
