from tlh.plugin.api import PluginApi


class TestPlugin:
    name = 'Test'
    description = '''Description of the test plugin
Descriptions can have multiple lines'''
    hidden = True # Hide this plugin from the settings dialog

    def __init__(self, api: PluginApi) -> None:
        self.api = api

    def load(self) -> None:
        self.menu_entry = self.api.register_menu_entry('Test', self.show_test)

    def unload(self) -> None:
        self.api.remove_menu_entry(self.menu_entry)

    def show_test(self):
        self.api.show_message('Test', 'test plugin loaded successfully')
