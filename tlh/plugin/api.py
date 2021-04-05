#from tlh.app import MainWindow


from PySide6.QtWidgets import QMainWindow


class PluginApi:
    def __init__(self, main_window: QMainWindow):
        self.main_window = main_window


    def register_menu_entry(self, name: str, callback):
        self.main_window.ui.menuTools.addAction(name, callback)