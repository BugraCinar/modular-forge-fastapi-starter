import operator
from contextlib import contextmanager
from typing import Any

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool

from modular_forge.shared.errors import ConflictError
from modular_forge.shared.persistence import Callbacks, Conditions, Record, TableSpec, eq


def metadata_for(specs: list[TableSpec]) -> sa.MetaData:
    metadata = sa.MetaData()
    for spec in specs:
        columns: list[sa.Column] = [
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("revision", sa.Integer, nullable=False),
        ]
        for column in spec.columns:
            kind: Any = {
                "str": sa.String(column.length),
                "text": sa.Text(),
                "int": sa.BigInteger(),
                "bool": sa.Boolean(),
                "json": sa.JSON(),
            }[column.kind]
            columns.append(sa.Column(column.name, kind, nullable=column.nullable))
        table = sa.Table(spec.name, metadata, *columns)
        for fields in spec.unique:
            sa.Index(
                f"uq_{spec.name}_{'_'.join(fields)}", *(table.c[x] for x in fields), unique=True
            )
        for fields in spec.indexes:
            sa.Index(f"ix_{spec.name}_{'_'.join(fields)}", *(table.c[x] for x in fields))
    return metadata


class SQLTransaction(Callbacks):
    def __init__(self, connection, metadata):
        super().__init__()
        self.connection, self.metadata = connection, metadata

    def _table(self, name: str):
        return self.metadata.tables[name]

    def _where(self, table, conditions):
        expressions = []
        for field, op, value in conditions or []:
            column = table.c[field]
            compare = {
                "eq": operator.eq,
                "lt": operator.lt,
                "le": operator.le,
                "gt": operator.gt,
                "ne": operator.ne,
            }[op]
            expressions.append(compare(column, value))
        return sa.and_(sa.true(), *expressions)

    def get(self, table: str, identifier: str, *, lock: bool = False) -> Record | None:
        target = self._table(table)
        query = sa.select(target).where(target.c.id == identifier)
        if lock:
            query = query.with_for_update()
        row = self.connection.execute(query).mappings().first()
        return dict(row) if row else None

    def one(self, table: str, **values) -> Record | None:
        rows = self.find(table, eq(**values), limit=1)
        return rows[0] if rows else None

    def find(
        self,
        table: str,
        conditions: Conditions | None = None,
        *,
        limit=50,
        offset=0,
        order_by="id",
        descending=False,
    ) -> list[Record]:
        target = self._table(table)
        column = target.c[order_by]
        query = (
            sa.select(target)
            .where(self._where(target, conditions))
            .order_by(column.desc() if descending else column.asc())
            .limit(limit)
            .offset(offset)
        )
        return [dict(row) for row in self.connection.execute(query).mappings()]

    def count(self, table: str, conditions: Conditions | None = None) -> int:
        target = self._table(table)
        return (
            self.connection.scalar(
                sa.select(sa.func.count())
                .select_from(target)
                .where(self._where(target, conditions))
            )
            or 0
        )

    def insert(self, table: str, record: Record) -> Record:
        value = {**record, "revision": 0}
        self.connection.execute(sa.insert(self._table(table)).values(**value))
        return value

    def update(self, table: str, identifier: str, changes: Record, *, revision: int) -> bool:
        target = self._table(table)
        result = self.connection.execute(
            sa.update(target)
            .where(target.c.id == identifier, target.c.revision == revision)
            .values(**changes, revision=revision + 1)
        )
        return result.rowcount == 1

    def delete(self, table: str, conditions: Conditions) -> int:
        target = self._table(table)
        return self.connection.execute(
            sa.delete(target).where(self._where(target, conditions))
        ).rowcount


class SQLDatabase:
    def __init__(self, url: str, specs: list[TableSpec]):
        self.specs, self.metadata = specs, metadata_for(specs)
        options: dict[str, Any] = {"pool_pre_ping": True, "hide_parameters": True}
        if url.startswith("sqlite:"):
            options["connect_args"] = {"check_same_thread": False, "timeout": 15}
            if ":memory:" in url:
                options["poolclass"] = StaticPool
        self.engine = sa.create_engine(url, **options)

    @contextmanager
    def transaction(self):
        try:
            with self.engine.begin() as connection:
                transaction = SQLTransaction(connection, self.metadata)
                yield transaction
        except IntegrityError:
            raise ConflictError() from None
        transaction.dispatch()

    def initialize(self, *, create: bool = False):
        if create:
            self.metadata.create_all(self.engine)
        inspector = sa.inspect(self.engine)
        if "two_factor_credentials" not in self.metadata.tables and inspector.has_table(
            "two_factor_credentials"
        ):
            sidecar = sa.Table("two_factor_credentials", sa.MetaData(), autoload_with=self.engine)
            with self.engine.connect() as connection:
                if connection.scalar(
                    sa.select(sa.func.count())
                    .select_from(sidecar)
                    .where(sidecar.c.enabled.is_(True))
                ):
                    raise RuntimeError(
                        "Active TOTP credentials exist. Disable them safely before disabling the module."
                    )
        for table in self.metadata.tables.values():
            if not inspector.has_table(table.name):
                raise RuntimeError("Database schema is missing. Run modular-forge migrate.")
            actual = {column["name"] for column in inspector.get_columns(table.name)}
            if not set(table.columns.keys()).issubset(actual):
                raise RuntimeError("Database schema is outdated. Apply migrations.")

    def healthy(self):
        try:
            with self.engine.connect() as connection:
                connection.execute(sa.text("SELECT 1"))
            return True
        except sa.exc.SQLAlchemyError:
            return False

    def close(self):
        self.engine.dispose()
