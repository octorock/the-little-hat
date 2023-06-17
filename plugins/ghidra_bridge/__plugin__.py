from plugins.ghidra_bridge.export_headers import export_headers
from tlh.plugin.api import PluginApi


class GhidraBridgePlugin:
    name = 'Ghidra Bridge'
    description = 'Connect to Ghidra'

    def __init__(self, api: PluginApi) -> None:
        self.api = api

    def load(self) -> None:
        self.action_export_headers = self.api.register_menu_entry('Export headers for Ghidra', self.slot_export_headers)

    def unload(self) -> None:
        self.api.remove_menu_entry(self.action_export_headers)

    def slot_export_headers(self) -> None:
        export_headers()
        self.api.show_message(self.name, 'Exported headers to tmp/ghidra_types.')
