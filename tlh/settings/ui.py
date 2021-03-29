from sys import flags
import typing

import PySide6
from PySide6.QtGui import QKeySequence, QShortcut, QStandardItemModel
from tlh import settings
from PySide6.QtCore import QAbstractListModel, QModelIndex, QStringListModel, Qt
from tlh.ui.ui_settings import Ui_dialogSettings
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QListView


class LayoutModel(QAbstractListModel):
    def __init__(self, layouts: list[settings.Layout], parent: typing.Optional[PySide6.QtCore.QObject]) -> None:
        super().__init__(parent=parent)
        self.layouts = layouts

    def rowCount(self, parent: QModelIndex) -> int:
        # print(len(self.layouts))
        return len(self.layouts)

    def data(self, index: PySide6.QtCore.QModelIndex, role: int) -> typing.Any:
        if role == Qt.DisplayRole or role == Qt.EditRole:
            return self.layouts[index.row()].name

        # if role == Qt.ToolTipRole:
            # return 'HEY :)'
        #print(f'Missing role {role}')
        return None

    def flags(self, index: PySide6.QtCore.QModelIndex) -> PySide6.QtCore.Qt.ItemFlags:
        # should not return Qt.ItemIsDropEnabled, see https://www.walletfox.com/course/qtreorderablelist.php
        if index.isValid():
            return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsDragEnabled | Qt.ItemNeverHasChildren
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled | Qt.ItemNeverHasChildren

    # https://github.com/qt/qtbase/blob/7ee682a1ddc259225618b57ff00f4c36ff5e724c/src/corelib/itemmodels/qstringlistmodel.cpp
    def moveRows(self, sourceParent: PySide6.QtCore.QModelIndex, sourceRow: int, count: int, destinationParent: PySide6.QtCore.QModelIndex, destinationChild: int) -> bool:
        if sourceRow < 0 or sourceRow + count - 1 >= self.rowCount(sourceParent) or destinationChild < 0 or destinationChild > self.rowCount(destinationParent) or sourceRow == destinationChild - 1 or count <= 0:
            return False
        if not self.beginMoveRows(QModelIndex(), sourceRow, sourceRow + count - 1, QModelIndex(), destinationChild):
            return False

        fromRow = sourceRow
        if destinationChild < sourceRow:
            fromRow += count - 1
        else:
            destinationChild -= 1
        while count > 0:
            self.layouts.insert(destinationChild, self.layouts.pop(fromRow))
            count -= 1
        self.endMoveRows()

        # fromRow = (sourceRow + count -
        #            1) if destinationChild < sourceRow else sourceRow
        # while count > 0:
        #     count -= 1
        #     print(f'{fromRow} <-> {destinationChild}')
        #     self.layouts.insert(destinationChild, self.layouts.pop(fromRow))

        # self.endMoveRows()
        return True

    def supportedDropActions(self) -> PySide6.QtCore.Qt.DropActions:
        return super().supportedDropActions() | Qt.MoveAction

    def setData(self, index: PySide6.QtCore.QModelIndex, value: typing.Any, role: int) -> bool:
        if index.isValid():
            self.layouts[index.row()].name = value
            return True
        return False

    def removeRows(self, row: int, count: int, parent: PySide6.QtCore.QModelIndex) -> bool:
        if count <= 0 or row < 0 or (row + count) > self.rowCount(parent):
            return False

        if count == 1:
            self.beginRemoveRows(QModelIndex(), row, row + count - 1)
            self.layouts.pop(row)
            self.endRemoveRows()
            return True
        return False


class SettingsDialog(QDialog):
    def __init__(self, parent) -> None:
        super().__init__(parent)
        self.ui = Ui_dialogSettings()
        self.ui.setupUi(self)

        layouts = settings.get_layouts()

        self.layouts_model = LayoutModel(layouts, self)
        #layouts_model = MyStringListModel(layouts, self)
        self.ui.listLayouts.setModel(self.layouts_model)

        shortcut_delete = QShortcut(QKeySequence(
            Qt.Key_Delete), self.ui.listLayouts)
        shortcut_delete.activated.connect(self.delete_layout)

        # Need to connect to the signal here instead of on the button box, so we are informed before anyone that is connected to the finish slot
        self.accepted.connect(self.save_settings)
        self.ui.buttonBox.button(QDialogButtonBox.Apply).clicked.connect(self.save_settings)

        # for layout in layouts:
        #     self.ui.listLayouts.addItem(layout)

        # # Make entries editable
        # for index in range(self.ui.listLayouts.count()):
        #     item = self.ui.listLayouts.item(index)
        #     item.setFlags(item.flags() | Qt.ItemIsEditable | Qt.Delete)

        self.ui.listLayouts.setDragDropMode(
            QListView.DragDropMode.InternalMove)

    def delete_layout(self):
        self.layouts_model.removeRow(self.ui.listLayouts.currentIndex().row())


    def save_settings(self):
        settings.set_layouts(self.layouts_model.layouts)
