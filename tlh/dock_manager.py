from tlh.hexeditor.manager import AbstractHexEditorInstance, HexEditorManager, SoloHexEditorInstance
from tlh.hexeditor.ui import HexEditorDock
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDockWidget, QMessageBox
from tlh.const import RomVariant
from dataclasses import dataclass


@dataclass
class Dock:
    object_name: str
    widget: QDockWidget
    rom_variant: RomVariant
    instance: AbstractHexEditorInstance
    linked: bool


class DockManager:

    def __init__(self, parent) -> None:
        self.parent = parent
        self.dock_count = 0
        self.hex_editor_manager = HexEditorManager(parent , {})
        self.docks: dict[str, Dock] = {}

    def add_hex_editor(self, rom_variant: RomVariant):
        '''
        Creates a fresh and unlinked hex editor for a rom variant
        '''
        for i in range(100):
            object_name = f'hex{rom_variant}{i}'
            if object_name not in self.docks:
                self.add_hex_editor_dock(rom_variant, object_name, False)
                return

        assert False # TODO more than 100 of one variant?


    def add_hex_editor_dock(self, rom_variant: RomVariant, object_name: str, linked: bool) -> None:
        '''
        Internally used to add a new or existing hex editor
        '''
        dockWidget = QDockWidget('Hex Editor ' + rom_variant, self.parent)
        dockWidget.setAttribute(Qt.WA_DeleteOnClose) # Not only hide docks on close TODO still remove them here
        dockWidget.setObjectName(object_name)
        self.parent.addDockWidget(Qt.DockWidgetArea.TopDockWidgetArea, dockWidget)
        instance = self.hex_editor_manager.get_hex_editor_instance(rom_variant, linked)
        hexEditorDock = HexEditorDock(self.parent, instance)
        dockWidget.setWidget(hexEditorDock)
        dock = Dock(object_name, dockWidget, rom_variant, instance, linked)
        self.docks[object_name] = dock
        hexEditorDock.toggle_linked.connect(lambda linked: self.toggle_linked(dock, linked))
        dockWidget.destroyed.connect(lambda: self.remove_dock(object_name))

    def toggle_linked(self, dock: Dock, linked: bool) -> None:
        if linked:
            if self.hex_editor_manager.is_already_linked(dock.rom_variant):
                dock.linked = False
                dock.instance.linked_changed.emit(False)
                QMessageBox.warning(dock.widget, 'Link Hex Editor', 'Hex editor cannot be linked, because another hex editor for the same rom variant is already linked.')
                return
            self.hex_editor_manager.link(dock.rom_variant)
            dock.linked = True
            dock.instance.linked_changed.emit(True)
        else:
            if self.hex_editor_manager.is_already_linked(dock.rom_variant):
                # unlink
                dock.linked = False
                self.hex_editor_manager.unlink(dock.rom_variant)
                dock.instance.linked_changed.emit(False)
                pass

    def remove_dock(self, object_name: str) -> None:
        print(f'Remove {object_name}')
        self.docks.pop(object_name)

    def save_state(self) -> str:
        arr = []
        for name in self.docks:
            dock = self.docks[name]
            arr.append(name + ',' + dock.rom_variant + ',' + ('1' if dock.linked else '0') )
        return ';'.join(arr)

    def restore_state(self, state: str) -> None:
        arr = state.split(';')

        to_spawn = {}

        for elem in arr:
            arr2 = elem.split(',')
            if len(arr2) != 3:
                continue
            object_name = arr2[0]
            rom_variant = arr2[1]
            linked = arr2[2] == '1'
            to_spawn[object_name] = {
                'rom_variant': rom_variant,
                'linked': linked
            }

        linked_variants: set[RomVariant] = set()

        for name in to_spawn:
            if to_spawn[name]['linked']:
                linked_variants.add(to_spawn[name]['rom_variant'])

        self.hex_editor_manager.set_linked_variants(linked_variants)

        print(to_spawn)
        # close docks that are no longer open
        for name in self.docks:
            if name not in to_spawn:
                print(f'Removing {name}')
                self.docks[name].widget.close()
            else:
                print(f'Keeping {name}')
                if self.docks[name].linked != to_spawn[name]['linked']:
                    print('set linked to ' + str(to_spawn[name]['linked']))
                    dock = self.docks[name]
                    dock.linked = to_spawn[name]['linked']
                    dock.instance = self.hex_editor_manager.get_hex_editor_instance(dock.rom_variant, dock.linked)
                    dock.instance.linked_changed.emit(to_spawn[name]['linked'])
                # Already open
                to_spawn.pop(name)

        for object_name in to_spawn:
            print(f'Opening {object_name}')
            rom_variant = to_spawn[object_name]['rom_variant']
            linked = to_spawn[object_name]['linked']
            self.add_hex_editor_dock(rom_variant, object_name, linked)
