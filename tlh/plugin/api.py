#from tlh.app import MainWindow


from tlh.common.ui.progress_dialog import ProgressDialog
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMainWindow


class PluginApi:
    def __init__(self, main_window: QMainWindow):
        self.main_window = main_window


    def register_menu_entry(self, name: str, callback) -> QAction:
        return self.main_window.ui.menuPlugins.addAction(name, callback)

    def remove_menu_entry(self, menu_entry: QAction) -> None:
        self.main_window.ui.menuPlugins.removeAction(menu_entry)


    def get_progress_dialog(self, title: str, text: str, abortable: bool) -> ProgressDialog:
        return ProgressDialog(self.main_window, title, text, abortable)