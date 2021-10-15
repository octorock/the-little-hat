#from tlh.app import MainWindow


from tlh.hexviewer.diff_calculator import LinkedDiffCalculator
from tlh.hexviewer.controller import HexViewerController
from typing import List, Optional
from tlh.const import RomVariant
from tlh.common.ui.progress_dialog import ProgressDialog
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMainWindow, QMessageBox


class PluginApi:
    def __init__(self, main_window: QMainWindow):
        self.main_window = main_window


    def register_menu_entry(self, name: str, callback) -> QAction:
        return self.main_window.ui.menuPlugins.addAction(name, callback)

    def remove_menu_entry(self, menu_entry: QAction) -> None:
        self.main_window.ui.menuPlugins.removeAction(menu_entry)


    def get_progress_dialog(self, title: str, text: str, abortable: bool) -> ProgressDialog:
        return ProgressDialog(self.main_window, title, text, abortable)


    def show_message(self, title: str, text: str) -> None:
        QMessageBox.information(self.main_window, title, text)

    def show_warning(self, title: str, text: str) -> None:
        QMessageBox.warning(self.main_window, title, text)

    def show_error(self, title: str, text: str) -> None:
        QMessageBox.critical(self.main_window, title, text)

    def show_question(self, title: str, text: str) -> bool:
        return QMessageBox.question(self.main_window, title, text) == QMessageBox.Yes


    # Hex Viewer
    def get_hexviewer_controllers(self, rom_variant: RomVariant) -> List[HexViewerController]:
        '''
        Returns the controllers for all hex viewers for a certain rom variant
        '''
        return self.main_window.dock_manager.hex_viewer_manager.get_controllers_for_variant(rom_variant)

    def get_linked_diff_calculator(self) -> LinkedDiffCalculator: # TODO can be None?
        '''
        Returns the calculator to ask for whether the linked hex views are differing for a certain byte
        '''
        return self.main_window.dock_manager.hex_viewer_manager.linked_diff_calculator

    def register_hexview_contextmenu_handler(self, handler) -> None:
        '''
        Register a handler that can add new context menu entries for hex viewers.
        The handler is called when the context menu is about to be opened and will receive the arguments controller: HexViewerController, menu: QMenu and cann add new actions to the QMenu.
        '''
        self.main_window.dock_manager.hex_viewer_manager.add_contextmenu_handler(handler)

    def remove_hexview_contextmenu_handler(self, handler) -> None:
        '''
        Unregister a hexview context menu handler.
        '''
        self.main_window.dock_manager.hex_viewer_manager.remove_contextmenu_handler(handler)