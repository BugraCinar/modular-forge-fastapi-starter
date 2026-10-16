from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

Record = dict[str, Any]
Conditions = list[tuple[str, str, Any]]


def eq(**values: Any) -> Conditions:
    return [(key, "eq", value) for key, value in values.items()]


@dataclass(frozen=True)
class ColumnSpec:
    name: str
    kind: str = "str"
    length: int = 255
    nullable: bool = False


@dataclass(frozen=True)
class TableSpec:
    name: str
    columns: tuple[ColumnSpec, ...]
    unique: tuple[tuple[str, ...], ...] = ()
    indexes: tuple[tuple[str, ...], ...] = ()


class Transaction(Protocol):
    def get(self, table: str, identifier: str, *, lock: bool = False) -> Record | None: ...
    def one(self, table: str, **values: Any) -> Record | None: ...
    def find(
        self,
        table: str,
        conditions: Conditions | None = None,
        *,
        limit: int = 50,
        offset: int = 0,
        order_by: str = "id",
        descending: bool = False,
    ) -> list[Record]: ...
    def count(self, table: str, conditions: Conditions | None = None) -> int: ...
    def insert(self, table: str, record: Record) -> Record: ...
    def update(self, table: str, identifier: str, changes: Record, *, revision: int) -> bool: ...
    def delete(self, table: str, conditions: Conditions) -> int: ...
    def after_commit(self, callback: Callable[[], None]) -> None: ...


class Database(Protocol):
    specs: list[TableSpec]

    def transaction(self) -> Any: ...
    def initialize(self, *, create: bool = False) -> None: ...
    def healthy(self) -> bool: ...
    def close(self) -> None: ...


@dataclass
class Callbacks:
    callbacks: list[Callable[[], None]] = field(default_factory=list)

    def after_commit(self, callback: Callable[[], None]) -> None:
        self.callbacks.append(callback)

    def dispatch(self) -> None:
        for callback in self.callbacks:
            callback()
