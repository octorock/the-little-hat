from PySide6.QtWidgets import QMessageBox
from tlh.plugin.api import PluginApi

parent = None
def main(api: PluginApi) -> None:
    global parent
    parent = api.main_window
    api.register_menu_entry('Test', show_test)

def show_test():
    QMessageBox.information(parent, 'Test', 'test plugin loaded successfully')