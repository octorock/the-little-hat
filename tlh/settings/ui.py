import hashlib
from tlh.plugin.loader import disable_plugin, enable_plugin, get_plugins, reload_plugins
import typing

import PySide6
from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox, QFileDialog, QLabel,
                               QListView, QMessageBox, QSizePolicy, QSpacerItem, QTableWidgetItem)
from tlh import settings
from tlh.const import SHA1_DEMO, SHA1_EU, SHA1_JP, SHA1_USA
from tlh.ui.ui_settings import Ui_dialogSettings


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
        # print(f'Missing role {role}')
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

        self.setup_general_tab()
        self.setup_roms_tab()
        self.setup_layouts_tab()
        self.setup_plugins_tab()

    def setup_general_tab(self):
        self.ui.lineEditUserName.setText(settings.get_username())

        self.ui.spinBoxDefaultSelectionSize.setValue(settings.get_default_selection_size())
        self.ui.checkBoxAlwaysLoadSymbols.setChecked(settings.is_always_load_symbols())
        self.ui.checkBoxHighlight8Bytes.setChecked(settings.is_highlight_8_bytes())
        self.ui.spinBoxBytesPerLine.setValue(settings.get_bytes_per_line())
        self.ui.checkBoxAutoSave.setChecked(settings.is_auto_save())

        self.ui.lineEditRepoLocation.setText(settings.get_repo_location())
        self.ui.toolButtonRepoLocation.clicked.connect(self.edit_repo_location)
        self.ui.lineEditBuildCommand.setText(settings.get_build_command())
        self.ui.lineEditTidyCommand.setText(settings.get_tidy_command())

    def edit_repo_location(self):
        dir = QFileDialog.getExistingDirectory(
            self, 'Location of the repository', self.ui.lineEditRepoLocation.text())
        if dir is not None:
            self.ui.lineEditRepoLocation.setText(dir)
        #QFileDialog.getOpenFileName(self, 'Location of the repository', )

    def setup_roms_tab(self):
        self.ui.lineEditRomUsa.setText(settings.get_rom_usa())
        self.ui.toolButtonUsa.clicked.connect(self.edit_rom_usa)
        self.ui.lineEditRomDemo.setText(settings.get_rom_demo())
        self.ui.toolButtonDemo.clicked.connect(self.edit_rom_demo)
        self.ui.lineEditRomEu.setText(settings.get_rom_eu())
        self.ui.toolButtonEu.clicked.connect(self.edit_rom_eu)
        self.ui.lineEditRomJp.setText(settings.get_rom_jp())
        self.ui.toolButtonJp.clicked.connect(self.edit_rom_jp)

    def edit_rom_usa(self):
        self.edit_rom('USA', self.ui.lineEditRomUsa, SHA1_USA)

    def edit_rom_demo(self):
        self.edit_rom('USA (DEMO)', self.ui.lineEditRomDemo, SHA1_DEMO)

    def edit_rom_eu(self):
        self.edit_rom('EU', self.ui.lineEditRomEu, SHA1_EU)

    def edit_rom_jp(self):
        self.edit_rom('JP', self.ui.lineEditRomJp, SHA1_JP)

    def edit_rom(self, name, lineEdit, expected_sha1):
        (rom, _) = QFileDialog.getOpenFileName(
            self, f'Select location of {name} rom', lineEdit.text(), '*.gba')
        if rom is not None:
            sha1 = calculate_sha1(rom)
            if sha1 == expected_sha1:
                lineEdit.setText(rom)
            else:
                QMessageBox.critical(
                    self, 'Wrong sha1', f'The sha1 of file {rom} does not correspond with the sha1 of the {name} rom.\nExpected: {expected_sha1}\nActual: {sha1}')

    def setup_layouts_tab(self):
        layouts = settings.get_layouts()

        self.layouts_model = LayoutModel(layouts, self)
        #layouts_model = MyStringListModel(layouts, self)
        self.ui.listLayouts.setModel(self.layouts_model)

        shortcut_delete = QShortcut(QKeySequence(
            Qt.Key_Delete), self.ui.listLayouts)
        shortcut_delete.activated.connect(self.delete_layout)

        # Need to connect to the signal here instead of on the button box, so we are informed before anyone that is connected to the finish slot
        self.accepted.connect(self.save_settings)
        self.ui.buttonBox.button(
            QDialogButtonBox.Apply).clicked.connect(self.save_settings)

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

    def setup_plugins_tab(self) -> None:

        self.plugins = get_plugins()
        self.plugin_checkboxes = {}

        for plugin in self.plugins:
            checkbox = QCheckBox()
            checkbox.setChecked(plugin.enabled)
            self.plugin_checkboxes[plugin.get_settings_name()] = checkbox
            self.ui.gridLayoutPlugins.addWidget(checkbox)
            self.ui.gridLayoutPlugins.addWidget(QLabel(plugin.name))
            self.ui.gridLayoutPlugins.addWidget(QLabel(plugin.description))

        # Add spacer to fill the remaining space
        self.ui.gridLayoutPlugins.addItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))
        self.ui.pushButtonReloadPlugins.clicked.connect(self.slot_reload_plugins)

    def slot_reload_plugins(self):
        reload_plugins()
        self.close()



    def save_settings(self):
        # General
        settings.set_username(self.ui.lineEditUserName.text())
        settings.set_default_selection_size(self.ui.spinBoxDefaultSelectionSize.value())
        settings.set_always_load_symbols(self.ui.checkBoxAlwaysLoadSymbols.isChecked())
        settings.set_highlight_8_bytes(self.ui.checkBoxHighlight8Bytes.isChecked())
        settings.set_bytes_per_line(self.ui.spinBoxBytesPerLine.value())
        settings.set_auto_save(self.ui.checkBoxAutoSave.isChecked())
        settings.set_repo_location(self.ui.lineEditRepoLocation.text())
        settings.set_build_command(self.ui.lineEditBuildCommand.text())
        settings.set_tidy_command(self.ui.lineEditTidyCommand.text())

        # ROMs
        settings.set_rom_usa(self.ui.lineEditRomUsa.text())
        settings.set_rom_demo(self.ui.lineEditRomDemo.text())
        settings.set_rom_eu(self.ui.lineEditRomEu.text())
        settings.set_rom_jp(self.ui.lineEditRomJp.text())

        # Layouts
        settings.set_layouts(self.layouts_model.layouts)

        # Plugins
        for plugin in self.plugins:
            name = plugin.get_settings_name()
            enabled = self.plugin_checkboxes[name].isChecked()
            if enabled != settings.is_plugin_enabled(name):
                settings.set_plugin_enabled(name, enabled)
                print(enabled)
                if enabled:
                    if not enable_plugin(plugin):
                        self.plugin_checkboxes[name].setChecked(False)
                        QMessageBox.critical(self, 'Load Plugin Failed', f'Unable to load plugin {plugin.name}.\nCheck console output for more information.')
                else:
                    disable_plugin(plugin)


# Returns sha1 for a file path
def calculate_sha1(path) -> str:
    sha1 = hashlib.sha1()

    with open(path, 'rb') as f:
        while True:
            data = f.read(65536)  # BUF_SIZE
            if not data:
                break
            sha1.update(data)
    return sha1.hexdigest()
