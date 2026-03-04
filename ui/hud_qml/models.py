from __future__ import annotations

from typing import Any, Dict, Iterable, List

from PySide6.QtCore import QByteArray, QAbstractListModel, QModelIndex, Qt, Slot


class DictListModel(QAbstractListModel):
    """Simple list model backed by dict items with fixed role names."""

    def __init__(self, role_names: Iterable[str], parent=None):
        super().__init__(parent)
        self._role_names: List[str] = [str(r) for r in role_names]
        self._items: List[Dict[str, Any]] = []
        self._roles: Dict[int, QByteArray] = {}
        self._rebuild_roles()

    def _rebuild_roles(self) -> None:
        self._roles = {}
        base = Qt.UserRole + 1
        for i, name in enumerate(self._role_names):
            self._roles[base + i] = QByteArray(name.encode("utf-8"))

    def roleNames(self) -> Dict[int, QByteArray]:
        return self._roles

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._items)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid():
            return None
        row = index.row()
        if row < 0 or row >= len(self._items):
            return None
        item = self._items[row]
        if role == Qt.DisplayRole:
            return item
        key = self._roles.get(role)
        if not key:
            return None
        return item.get(bytes(key).decode("utf-8"))

    @Slot(result=int)
    def count(self) -> int:
        return len(self._items)

    @Slot(int, result="QVariant")
    def get(self, row: int):
        if row < 0 or row >= len(self._items):
            return {}
        return dict(self._items[row])

    def set_items(self, items: Iterable[Dict[str, Any]]) -> None:
        self.beginResetModel()
        self._items = [dict(x or {}) for x in items]
        self.endResetModel()

    def append_item(self, item: Dict[str, Any]) -> None:
        row = len(self._items)
        self.beginInsertRows(QModelIndex(), row, row)
        self._items.append(dict(item or {}))
        self.endInsertRows()

    def remove_row(self, row: int) -> None:
        if row < 0 or row >= len(self._items):
            return
        self.beginRemoveRows(QModelIndex(), row, row)
        del self._items[row]
        self.endRemoveRows()

    def clear(self) -> None:
        self.set_items([])

    def update_row(self, row: int, values: Dict[str, Any]) -> None:
        if row < 0 or row >= len(self._items):
            return
        if not isinstance(values, dict):
            return
        self._items[row].update(values)
        idx = self.index(row, 0)
        self.dataChanged.emit(idx, idx)
