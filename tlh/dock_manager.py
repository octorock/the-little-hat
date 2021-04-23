from PySide6.QtWidgets import QMessageBox
from tlh.data.rom import get_rom
from tlh.hexviewer.controller import HexViewerController
from tlh.hexviewer.manager import HexViewerManager
from tlh.hexviewer.ui.dock import HexViewerDock
from PySide6.QtCore import Qt
from tlh.const import RomVariant
from dataclasses import dataclass


@dataclass
class Dock:
    object_name: str
    widget: HexViewerDock
    rom_variant: RomVariant
    controller: HexViewerController


class DockManager:

    def __init__(self, parent) -> None:
        self.parent = parent
        self.dock_count = 0
        self.hex_viewer_manager = HexViewerManager(parent)
        self.docks: dict[str, Dock] = {}

    def add_hex_editor(self, rom_variant: RomVariant):
        '''
        Creates a fresh and unlinked hex editor for a rom variant
        '''
        for i in range(100):
            object_name = f'hex{rom_variant}{i}'
            if object_name not in self.docks:
                self.add_hex_editor_dock(rom_variant, object_name)
                return

        assert False  # TODO more than 100 of one variant?

    def add_hex_editor_dock(self, rom_variant: RomVariant, object_name: str) -> HexViewerController:
        '''
        Internally used to add a new or existing hex editor
        '''

        rom = get_rom(rom_variant)
        if rom is None:
            QMessageBox.critical(self.parent, 'Load ROM',
                                 f'Unable to load rom {rom_variant}')
            return None

        dockWidget = HexViewerDock(self.parent, 'Hex Viewer ' + rom_variant)
        # Not only hide docks on close TODO still remove them here
        dockWidget.setAttribute(Qt.WA_DeleteOnClose)
        dockWidget.setObjectName(object_name)
        self.parent.addDockWidget(
            Qt.DockWidgetArea.TopDockWidgetArea, dockWidget)

        controller = HexViewerController(dockWidget, rom_variant, rom)
        self.hex_viewer_manager.register_controller(controller)

        dock = Dock(object_name, dockWidget, rom_variant, controller)
        self.docks[object_name] = dock
        dockWidget.destroyed.connect(lambda: self.remove_dock(object_name))
        return controller

    def remove_dock(self, object_name: str) -> None:
        print(f'Remove {object_name}')
        self.hex_viewer_manager.unregister_controller(
            self.docks[object_name].controller)
        self.docks.pop(object_name)

    def save_state(self) -> str:
        arr = []
        for name in self.docks:
            dock = self.docks[name]
            arr.append(name + ',' + dock.rom_variant + ',' +
                       ('1' if dock.controller.is_linked else '0'))
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

        self.hex_viewer_manager.unlink_all()

        linked_controllers: list[HexViewerController] = []

        print(to_spawn)
        # Close docks that are no longer open
        for name in self.docks:
            if name not in to_spawn:
                print(f'Removing {name}')
                self.docks[name].widget.close()
            else:
                print(f'Keeping {name}')

                if to_spawn[name]['linked']:
                    linked_controllers.append(self.docks[name].controller)

                # Already open
                to_spawn.pop(name)

        for object_name in to_spawn:
            print(f'Opening {object_name}')
            rom_variant = to_spawn[object_name]['rom_variant']
            controller = self.add_hex_editor_dock(rom_variant, object_name)
            if controller is not None and to_spawn[object_name]['linked']:
                linked_controllers.append(controller)

        self.hex_viewer_manager.link_multiple(linked_controllers)
