import os
from uuid import uuid4

import pytest

from modular_forge.persistence.sql import SQLDatabase
from modular_forge.shared.errors import ConflictError
from modular_forge.shared.persistence import ColumnSpec, TableSpec, eq


@pytest.fixture(params=["sqlite", "external"])
def database(request):
    url = (
        os.environ.get("CONTRACT_DATABASE_URL")
        if request.param == "external"
        else "sqlite:///:memory:"
    )
    if not url:
        pytest.skip("CONTRACT_DATABASE_URL is not configured; CI runs real database contracts.")
    if request.param == "external" and "forge_contract" not in url:
        pytest.fail("Contract tests must use a dedicated forge_contract database.")
    name = "contract_" + uuid4().hex[:12]
    specs = [
        TableSpec(
            name,
            (
                ColumnSpec("name", length=100),
                ColumnSpec("active", "bool"),
                ColumnSpec("created_at", "int"),
                ColumnSpec("context", "json"),
            ),
            unique=(("name",),),
        )
    ]
    if url.startswith(("mongodb://", "mongodb+srv://")):
        from modular_forge.persistence.mongo import MongoDatabase

        db = MongoDatabase(url, "forge_contract", specs)
    else:
        db = SQLDatabase(url, specs)
    db.initialize(create=True)
    try:
        yield db, name
    finally:
        if url.startswith("mongodb"):
            db.database.drop_collection(name)
        else:
            db.metadata.drop_all(db.engine)
        db.close()


def record(identifier="one", name="example"):
    return {
        "id": identifier,
        "name": name,
        "active": True,
        "created_at": 100,
        "context": {"nested": [1, "two"]},
    }


def test_repository_roundtrip_filters_and_optimistic_lock(database):
    db, table = database
    with db.transaction() as tx:
        tx.insert(table, record())
    with db.transaction() as tx:
        value = tx.one(table, name="example")
        assert value["context"] == {"nested": [1, "two"]} and value["active"] is True
        assert tx.update(table, value["id"], {"active": False}, revision=0)
        assert not tx.update(table, value["id"], {"active": True}, revision=0)
        assert tx.count(table, eq(active=False)) == 1
        assert tx.find(table, [("created_at", "lt", 101)])[0]["revision"] == 1


def test_transaction_rollback_does_not_dispatch_events(database):
    db, table = database
    delivered = []
    with pytest.raises(ValueError):
        with db.transaction() as tx:
            tx.insert(table, record())
            tx.after_commit(lambda: delivered.append("bad"))
            raise ValueError("rollback")
    with db.transaction() as tx:
        assert tx.count(table) == 0
        tx.insert(table, record())
        tx.after_commit(lambda: delivered.append("committed"))
    assert delivered == ["committed"]


def test_unique_identity_constraints_and_delete(database):
    db, table = database
    with db.transaction() as tx:
        tx.insert(table, record())
    with pytest.raises(ConflictError):
        with db.transaction() as tx:
            tx.insert(table, record("two"))
    with db.transaction() as tx:
        assert tx.count(table) == 1
        assert tx.delete(table, eq(id="one")) == 1


def test_client_values_are_not_interpreted_as_queries(database):
    db, table = database
    with db.transaction() as tx:
        tx.insert(table, record())
        assert tx.one(table, name="' OR 1=1 --") is None
        if not hasattr(db, "engine"):
            assert tx.one(table, name={"$ne": None}) is None
