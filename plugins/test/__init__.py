from PySide6.QtWidgets import QMessageBox
from tlh.plugin.api import PluginApi


class TestPlugin:
    def __init__(self, api: PluginApi) -> None:
        self.api = api
        api.register_menu_entry('Test', self.show_test)    
        
    def show_test(self):
        QMessageBox.information(self.api.main_window, 'Test', 'test plugin loaded successfully')