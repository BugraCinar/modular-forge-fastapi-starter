from contextlib import contextmanager
from typing import Any

from pymongo import ASCENDING, MongoClient
from pymongo.errors import DuplicateKeyError, PyMongoError

from modular_forge.shared.errors import ConflictError
from modular_forge.shared.persistence import Callbacks, Conditions, Record, TableSpec, eq


class MongoTransaction(Callbacks):
    def __init__(self, database, session, specs):
        super().__init__()
        self.database, self.session = database, session
        self.fields = {s.name: {"id", "revision", *(c.name for c in s.columns)} for s in specs}

    def _collection(self, name):
        if name not in self.fields:
            raise KeyError(name)
        return self.database[name]

    def _query(self, table, conditions):
        query = []
        for field, op, value in conditions or []:
            if field not in self.fields[table]:
                raise KeyError(field)
            operator = {"eq": "$eq", "lt": "$lt", "le": "$lte", "gt": "$gt", "ne": "$ne"}[op]
            query.append({field: {operator: value}})
        return {"$and": query} if query else {}

    @staticmethod
    def _record(value):
        if value is not None:
            value.pop("_id", None)
        return value

    def get(self, table: str, identifier: str, *, lock: bool = False) -> Record | None:
        return self._record(
            self._collection(table).find_one({"_id": identifier}, session=self.session)
        )

    def one(self, table: str, **values) -> Record | None:
        return self._record(
            self._collection(table).find_one(self._query(table, eq(**values)), session=self.session)
        )

    def find(
        self,
        table: str,
        conditions: Conditions | None = None,
        *,
        limit=50,
        offset=0,
        order_by="id",
        descending=False,
    ):
        if order_by not in self.fields[table]:
            raise KeyError(order_by)
        cursor = (
            self._collection(table)
            .find(self._query(table, conditions), session=self.session)
            .sort(order_by, -1 if descending else 1)
            .skip(offset)
            .limit(limit)
        )
        return [self._record(value) for value in cursor]

    def count(self, table: str, conditions: Conditions | None = None):
        return self._collection(table).count_documents(
            self._query(table, conditions), session=self.session
        )

    def insert(self, table: str, record: Record):
        if not set(record).issubset(self.fields[table]):
            raise KeyError("Unknown field")
        value = {**record, "revision": 0}
        self._collection(table).insert_one({**value, "_id": value["id"]}, session=self.session)
        return value

    def update(self, table, identifier, changes, *, revision):
        if not set(changes).issubset(self.fields[table] - {"id", "revision"}):
            raise KeyError("Unknown field")
        return (
            self._collection(table)
            .update_one(
                {"_id": identifier, "revision": revision},
                {"$set": changes, "$inc": {"revision": 1}},
                session=self.session,
            )
            .modified_count
            == 1
        )

    def delete(self, table, conditions):
        return (
            self._collection(table)
            .delete_many(self._query(table, conditions), session=self.session)
            .deleted_count
        )


class MongoDatabase:
    def __init__(self, url: str, name: str, specs: list[TableSpec]):
        self.specs = specs
        self.client: MongoClient[dict[str, Any]] = MongoClient(
            url, serverSelectionTimeoutMS=5000, tz_aware=True
        )
        self.database = self.client[name]

    @contextmanager
    def transaction(self):
        try:
            with self.client.start_session() as session, session.start_transaction():
                transaction = MongoTransaction(self.database, session, self.specs)
                yield transaction
        except DuplicateKeyError:
            raise ConflictError() from None
        transaction.dispatch()

    def initialize(self, *, create: bool = False):
        hello = self.client.admin.command("hello")
        if not (hello.get("setName") or hello.get("msg") == "isdbgrid"):
            raise RuntimeError(
                "MongoDB requires a replica set or sharded cluster for transactions."
            )
        existing = set(self.database.list_collection_names())
        if (
            "two_factor_credentials" not in {s.name for s in self.specs}
            and "two_factor_credentials" in existing
        ):
            if self.database.two_factor_credentials.find_one({"enabled": True}, {"_id": 1}):
                raise RuntimeError(
                    "Active TOTP credentials exist. Disable them safely before disabling the module."
                )
        for spec in self.specs:
            if create:
                if spec.name not in existing:
                    self.database.create_collection(spec.name)
                for columns in spec.unique:
                    self.database[spec.name].create_index(
                        [(x, ASCENDING) for x in columns],
                        unique=True,
                        name=f"uq_{spec.name}_{'_'.join(columns)}",
                    )
                for columns in spec.indexes:
                    self.database[spec.name].create_index(
                        [(x, ASCENDING) for x in columns],
                        name=f"ix_{spec.name}_{'_'.join(columns)}",
                    )
            elif spec.name not in existing:
                raise RuntimeError("MongoDB schema is missing. Run modular-forge migrate.")

    def healthy(self):
        try:
            self.client.admin.command("ping")
            return True
        except PyMongoError:
            return False

    def close(self):
        self.client.close()
