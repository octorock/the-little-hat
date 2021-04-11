from PySide6.QtWidgets import QMessageBox
from tlh.plugin.api import PluginApi


class TestPlugin:
    name = 'Test'
    description = '''Description of the test plugin
Descriptions can have multiple lines'''

    def __init__(self, api: PluginApi) -> None:
        self.api = api
        raise RuntimeError('bla')

    def load(self) -> None:
        self.menu_entry = self.api.register_menu_entry('Test', self.show_test)    
        
    def unload(self) -> None:
        self.api.remove_menu_entry(self.menu_entry)
    
    def show_test(self):
        QMessageBox.information(self.api.main_window, 'Test', 'test plugin loaded successfully')