from PySide6.QtWidgets import QMessageBox
from plugins.repo_utils.find_unused import find_unused
from plugins.repo_utils.split_asm import split_asm
from tlh.plugin.api import PluginApi


class RepoUtilsPlugin:
    name = 'Repo Utils'
    description = '''Small scripts improving the workflow with the repo'''

    def __init__(self, api: PluginApi) -> None:
        self.api = api

    def load(self) -> None:
        self.action_split_asm = self.api.register_menu_entry('Split Asm', self.slot_split_asm)
        self.action_find_unused = self.api.register_menu_entry('Find Unused Files', self.slot_find_unused)

    def unload(self) -> None:
        self.api.remove_menu_entry(self.action_split_asm)
        self.api.remove_menu_entry(self.action_find_unused)

    def slot_split_asm(self) -> None:
        (text, ok) = self.api.show_text_input(self.name, 'File to split, e.g. object/smallIceBlock')
        if ok:
            split_asm(self.api, text)

    def slot_find_unused(self) -> None:
        find_unused(self.api)
