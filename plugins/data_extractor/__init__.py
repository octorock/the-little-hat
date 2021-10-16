from dataclasses import dataclass
from enum import Enum
import os
from plugins.data_extractor.read_data import Reader, load_json_files, read_var
from tlh.const import ROM_OFFSET, RomVariant
from tlh.settings import get_repo_location
from PySide6.QtWidgets import QApplication, QMenu
from tlh.hexviewer.controller import HexViewerController
from tlh.plugin.api import PluginApi
from tlh.data.database import get_file_in_database, get_symbol_database
from plugins.data_extractor.incbins import export_incbins
import re
import traceback

@dataclass
class DataType:
    '''
    0: Single data
    1: Arrays of data
    2: Arrays of arrays of data
    3: Arrays of function pointers
    4: Arrays of arrays of puncion pointers
    '''
    regex: int
    name: str
    type: str
    count: int
    count2: int
    params: str


class DataExtractorPlugin:
    name = 'Data Extractor'
    description = 'Extracts data in different formats'

    def __init__(self, api: PluginApi) -> None:
        self.api = api
        self.structs = None
        self.unions = None

    def load(self) -> None:
        self.api.register_hexview_contextmenu_handler(self.contextmenu_handler)
        # TODO remove, only works if context menu entry was used once before to set current_controller
        self.action_incbin = self.api.register_menu_entry('Copy as .incbin', self.slot_copy_as_incbin)
        #self.action_incbin.setShortcut('F2');

        #self.action_many = self.api.register_menu_entry('Many', self.slot_many)
        #self.action_disasm = self.api.register_menu_entry('Export list for disasm', self.slot_disasm)

        self.action_export_incbins = self.api.register_menu_entry('Export Incbins', self.slot_export_incbins)

        load_json_files()

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

        menu.addAction('Extract data for symbol', self.slot_extract_data)


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

    def slot_extract_data(self) -> None:
        if self.current_controller.symbols is None:
            self.api.show_error(self.name, f'No symbols loaded for current editor')
            return
        # symbol = self.current_controller.symbols.get_symbol_at(self.current_controller.address_resolver.to_local(self.current_controller.cursor))


        (type_str, ok) = self.api.show_text_input(self.name, 'Enter data type')
        if not ok:
            return
        print(type_str)

        type = self.parse_type(type_str)

        symbol = self.current_controller.symbols.find_symbol_by_name(type.name)
        if symbol is None:
            self.api.show_error(self.name, f'Could not find symbol {type.name}')
            return

        text = ''

        data = self.current_controller.rom.get_bytes(symbol.address, symbol.address+symbol.length)
        reader = Reader(data)

        if type.regex == 0:
            try:
                res = read_var(reader, type.type)
                text = 'const ' + type.type + ' ' + type.name + ' = ' + self.get_struct_init(res) + ';';
            except Exception as e:
                print(e)
                self.api.show_error(self.name, str(e))
        elif type.regex == 1:
            if type.type == 'u8':
                text = 'const ' + type.type + ' ' + type.name + '[] = {'
                for i in range(symbol.address, symbol.address+symbol.length):
                    text += str(self.current_controller.rom.get_byte(i)) + ', '
                text += '};'
            elif '*' in type.type: # pointers
                if symbol.length % 4 != 0:
                    self.api.show_error(self.name, 'Incorrect data length')

                text = 'const ' + type.type + ' ' + type.name + '[] = {'
                for i in range(symbol.address, symbol.address+symbol.length, 4):
                    pointer = self.current_controller.get_as_pointer(i)
                    pointer_symbol = self.current_controller.symbols.get_symbol_at(pointer - ROM_OFFSET)
                    text += '&' + pointer_symbol.name + ', '
                text += '};'
            else:
                try:
                    res = read_var(reader, type.type + '[]')
                    text = 'const ' + type.type + ' ' + type.name + '[] = ' + self.get_struct_init(res) + ';';
                except Exception as e:
                    traceback.print_exc()
                    self.api.show_error(self.name, str(e))
        elif type.regex == 3:
            if symbol.length % 4 != 0:
                self.api.show_error(self.name, 'Incorrect data length')

            text = 'void (*const ' + type.name + '[])(' + type.params + ') = {'
            for i in range(symbol.address, symbol.address+symbol.length, 4):
                pointer = self.current_controller.get_as_pointer(i)
                pointer_symbol = self.current_controller.symbols.get_symbol_at(pointer - ROM_OFFSET)
                text += pointer_symbol.name + ', '
            text += '};'
        else:
            self.api.show_error(self.name, f'Unimplemented type for regex {type.regex}')
            return


        QApplication.clipboard().setText(text)
        print(text)


    def parse_type(self, type: str) -> DataType:
        match = re.search('(extern )?(const )?(?P<type>\S+) (?P<name>\w+);', type)
        if match is not None:
            return DataType(0, match.group('name'), match.group('type'), 0, 0, '')

        match = re.search('(extern )?(const )?(?P<type>\S+) (const )?(?P<name>\w+)\[(?P<count>\w+)?\];', type)
        if match is not None:
            return DataType(1, match.group('name'), match.group('type'), match.group('count'), 0, '')

        match = re.search('(extern )?(const )?(?P<type>\S+) (?P<name>\w+)\[(?P<count>\w+)?\]\[(?P<count2>\w+)?\];', type)
        if match is not None:
            return DataType(2, match.group('name'), match.group('type'), match.group('count'), match.group('count2'), '')

        match = re.search('(extern )?(const )?void \(\*(const )?(?P<name>\w+)\[(?P<count>\w+)?\]\)\((?P<params>.*)\);', type)
        if match is not None:
            return DataType(3, match.group('name'), '', match.group('count'), 0, match.group('params'))

        match = re.search('(extern )?(const )?void \(\*(const )?(?P<name>\w+)\[(?P<count>\w+)?\]\[(?P<count2>\w+)\]\)\((?P<params>.*)\);', type)
        if match is not None:
            return DataType(4, match.group('name'), '', match.group('count'), match.group('count2'), match.group('params'))

        return None



    def get_struct_init(self, obj: any) -> str:
        text = '{ '
        trailing_comma = False
        if trailing_comma:
            for key in obj:
                if type(obj) is list:
                    if type(key) is list or type(key) is dict:
                        text += self.get_struct_init(key) + ', '
                    else:
                        text += str(key) + ', '
                elif type(obj[key]) is list:
                    text += self.get_struct_init(obj[key]) + ', '
                else:
                    text += str(obj[key]) + ', '
            text += ' }'
        else:
            separator = ''
            for key in obj:
                if type(obj) is list:
                    if type(key) is list or type(key) is dict:
                        text += self.get_struct_init(key) + ', '
                    else:
                        text += separator + str(key)
                elif type(obj[key]) is list:
                    text += separator + self.get_struct_init(obj[key])
                else:
                    text += separator + str(obj[key])
                separator = ', '
            text += ' }'
        return text