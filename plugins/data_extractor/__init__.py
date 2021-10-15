import os
from tlh.const import ROM_OFFSET, RomVariant
from tlh.settings import get_repo_location
from PySide6.QtWidgets import QApplication, QMenu
from tlh.hexviewer.controller import HexViewerController
from tlh.plugin.api import PluginApi
from tlh.data.database import get_symbol_database
from plugins.data_extractor.incbins import export_incbins

class DataExtractorPlugin:
    name = 'Data Extractor'
    description = 'Extracts data in different formats'

    def __init__(self, api: PluginApi) -> None:
        self.api = api

    def load(self) -> None:
        self.api.register_hexview_contextmenu_handler(self.contextmenu_handler)
        # TODO remove, only works if context menu entry was used once before to set current_controller
        self.action_incbin = self.api.register_menu_entry('Copy as .incbin', self.slot_copy_as_incbin)
        #self.action_incbin.setShortcut('F2');

        #self.action_many = self.api.register_menu_entry('Many', self.slot_many)
        #self.action_disasm = self.api.register_menu_entry('Export list for disasm', self.slot_disasm)

        self.action_export_incbins = self.api.register_menu_entry('Export Incbins', self.slot_export_incbins)

    def unload(self) -> None:
        self.api.remove_hexview_contextmenu_handler(self.contextmenu_handler)
        self.api.remove_menu_entry(self.action_incbin)
        self.api.remove_menu_entry(self.action_export_incbins)

    def contextmenu_handler(self, controller: HexViewerController, menu: QMenu) -> None:
        menu.addSeparator()
        self.current_controller = controller
        menu.addAction('Copy as .incbin', self.slot_copy_as_incbin)

        if abs(controller.selected_bytes) % 4 == 0:
            menu.addAction('Copy as pointer list', self.slot_copy_as_pointerlist)


    def slot_copy_as_incbin(self) -> None:
        symbol = self.current_controller.symbols.get_symbol_at(self.current_controller.address_resolver.to_local(self.current_controller.cursor))
        # TODO deduce baserom name from controller's rom_variant
        incbin = f'\t.incbin "baserom_eu.gba", {"{0:#08x}".format(symbol.address).upper().replace("0X", "0x")}, {"{0:#09x}".format(symbol.length).upper().replace("0X", "0x")}\n'
        QApplication.clipboard().setText(incbin)
        #self.api.show_message(self.name, 'Copied .incbin to clipboard.')

    def slot_many(self) -> None:

        print('Many')
        output = []
        with open(os.path.join(get_repo_location(), 'data', 'data_08125104.s'), 'r') as file:
            lines = file.readlines()

        print(len(lines))
        has_ifdef = False
        has_else = False
        has_endif = False

        buffer = []
        comments = []

        for line in lines:
            if '.ifdef EU' in line:
                has_ifdef = True
                buffer.append(line)
            elif has_ifdef and line.strip().startswith('@'):
                buffer.append(line)
                comments.append(line)
            elif has_ifdef and '.else' in line:
                has_else = True
                buffer.append(line)
            elif has_ifdef and has_else and '.endif' in line:
                has_endif = True
                buffer.append(line)
            elif has_ifdef and has_else and has_endif and '.incbin' in line:
                arr = line.split(',')
                location = arr[1].strip()
                size = arr[2].strip()
                print(arr)

                symbol = self.current_controller.symbols.find_symbol_by_name(location.replace('0x', 'gUnk_08'))
                # TODO deduce baserom name from controller's rom_variant
                incbin = f'\t.incbin "baserom_eu.gba", {"{0:#08x}".format(symbol.address).upper().replace("0X", "0x")}, {"{0:#09x}".format(symbol.length).upper().replace("0X", "0x")}\n'

                output.append('.ifdef EU\n')
                output.extend(comments)
                output.append(incbin)
                output.append('.else\n')
                output.append(line)
                output.append('.endif\n')
                has_ifdef = False
                has_else = False
                has_endif = False
                buffer = []
                comments = []
            else:
                if has_ifdef:
                    has_ifdef = False
                    has_else = False
                    has_endif = False
                    output.extend(buffer)
                    buffer = []
                    comments = []
                output.append(line)

        with open(os.path.join(get_repo_location(), 'data', 'data_08125104.s'), 'w') as file:
            file.writelines(output)

    def slot_copy_as_pointerlist(self) -> None:
        address = self.current_controller.cursor
        length = abs(self.current_controller.selected_bytes)
        if self.current_controller.selected_bytes < 0:
            address += self.current_controller.selected_bytes + 1
        result = []
        for i in range(address, address+length, 4):
            pointer = self.current_controller.get_as_pointer(i)
            result.append(hex(pointer))

        QApplication.clipboard().setText(',\n'.join(result))

    def slot_disasm(self) -> None:
        symbol_database = get_symbol_database()
        symbols = symbol_database.get_symbols(RomVariant.CUSTOM)
        with open('/tmp/tmc.cfg', 'w') as file:
            for symbol in symbols.symbols:
                file.write(f'thumb_func {hex(symbol.address+ROM_OFFSET)} {symbol.name}\n')


    def slot_export_incbins(self) -> None:
        export_incbins(self.api)