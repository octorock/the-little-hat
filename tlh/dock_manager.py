from tlh.hexeditor.manager import HexEditorManager, SoloHexEditorInstance
from tlh.hexeditor.ui import HexEditorDock
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDockWidget
from tlh.const import RomVariant
from dataclasses import dataclass


@dataclass
class Dock:
    object_name: str
    widget: QDockWidget
    rom_variant: RomVariant
    #linked: bool


class DockManager:

    def __init__(self, parent) -> None:
        self.parent = parent
        self.dock_count = 0
        self.hex_editor_manager = HexEditorManager(parent)
        self.docks: dict[str, Dock] = {}

    def add_hex_editor(self, rom_variant: RomVariant):
        for i in range(100):
            object_name = f'hex{rom_variant}{i}'
            if object_name not in self.docks:
                self.add_hex_editor_dock(rom_variant, object_name)
                return

        assert False # TODO more than 100 of one variant?


    def add_hex_editor_dock(self, rom_variant: RomVariant, object_name: str) -> None:
        dockWidget = QDockWidget('Hex Editor ' + rom_variant, self.parent)
        dockWidget.setAttribute(Qt.WA_DeleteOnClose) # Not only hide docks on close TODO still remove them here
        dockWidget.setObjectName(object_name)
        self.parent.addDockWidget(Qt.DockWidgetArea.TopDockWidgetArea, dockWidget)
        #instance = self.hex_editor_manager.get_hex_editor_instance(rom_variant)
        instance = SoloHexEditorInstance(self.parent, rom_variant, self.hex_editor_manager.roms[rom_variant])
        dockWidget.setWidget(HexEditorDock(self.parent, instance))
        dock = Dock(object_name, dockWidget, rom_variant)
        self.docks[object_name] = dock
        dockWidget.destroyed.connect(lambda: self.remove_dock(object_name))

    def remove_dock(self, object_name: str) -> None:
        print(f'Remove {object_name}')
        self.docks.pop(object_name)

    def save_state(self) -> str:
        arr = []
        for name in self.docks:
            dock = self.docks[name]
            arr.append(name + ',' + dock.rom_variant)
        return ';'.join(arr)

    def restore_state(self, state: str) -> None:
        arr = state.split(';')

        to_spawn = {}

        for elem in arr:
            arr2 = elem.split(',')
            if len(arr2) != 2:
                continue
            object_name = arr2[0]
            rom_variant = arr2[1]
            to_spawn[object_name] = rom_variant

        print(to_spawn)
        # close docks that are no longer open
        for name in self.docks:
            if name not in to_spawn:
                print(f'Removing {name}')
                self.docks[name].widget.close()
            else:
                print(f'Keeping {name}')
                # Already open
                to_spawn.pop(name)

        for object_name in to_spawn:
            print(f'Opening {object_name}')
            rom_variant = to_spawn[object_name]
            self.add_hex_editor_dock(rom_variant, object_name)
        