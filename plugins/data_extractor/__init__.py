from dataclasses import dataclass
from enum import Enum
import os
from pprint import pprint
from typing import Optional

from PySide6.QtGui import QKeySequence
from plugins.data_extractor.assets import get_all_asset_configs, read_assets, write_assets
from plugins.data_extractor.gba_lz77 import GBALZ77, DecompressionError
from plugins.data_extractor.read_data import Reader, load_json_files, read_var
from plugins.data_extractor.structs import generate_struct_definitions
from tlh.const import CUSTOM_ROM_VARIANTS, ROM_OFFSET, RomVariant
from tlh.data.rom import Rom
from tlh.data.symbols import Symbol, SymbolList
from tlh.settings import get_repo_location
from PySide6.QtWidgets import QApplication, QMenu
from tlh.hexviewer.controller import HexViewerController
from tlh.plugin.api import PluginApi
from tlh.data.database import get_file_in_database, get_symbol_database
from plugins.data_extractor.incbins import export_incbins
import re
import traceback
import json

DEV_ACTIONS = False

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
@dataclass
class Asset:
    name: str
    type: str
    offset: int
    size: int
    compressed: bool

def opt_param(name: str, default: str, value: str) -> str:
    if value != default:
        return f', {name}={value}'
    return ''

OBJ_SIZES = {
    0: {
        0: (8, 8),
        1: (16, 16),
        2: (32, 32),
        3: (64, 64),
    },
    1: {
        0: (16, 8),
        1: (32, 8),
        2: (32, 16),
        3: (64, 32),
    },
    2: {
        0: (8, 16),
        1: (8, 32),
        2: (16, 32),
        3: (32, 64),
    },
}

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
        self.action_remove_unused = self.api.register_menu_entry('Remove unused asset entries', self.slot_remove_unused_assets)
        self.action_parse_structs = self.api.register_menu_entry('Parse structs', self.slot_parse_structs)
        load_json_files()

    def unload(self) -> None:
        self.api.remove_hexview_contextmenu_handler(self.contextmenu_handler)
        self.api.remove_menu_entry(self.action_incbin)
        self.api.remove_menu_entry(self.action_export_incbins)
        self.api.remove_menu_entry(self.action_remove_unused)
        self.api.remove_menu_entry(self.action_parse_structs)

    def contextmenu_handler(self, controller: HexViewerController, menu: QMenu) -> None:
        menu.addSeparator()
        self.current_controller = controller
        menu.addAction('Copy as .incbin', self.slot_copy_as_incbin)

        if abs(controller.selected_bytes) % 4 == 0:
            menu.addAction('Copy as pointer list', self.slot_copy_as_pointerlist)

        menu.addAction('Extract data for symbol', self.slot_extract_data)
        if DEV_ACTIONS:
            menu.addAction('Test', self.slot_test)
            menu.addAction('Tmp', self.slot_tmp)
            menu.addAction('Extract current entity list', self.slot_extract_current_entity_list)
            menu.addAction('Extract current tile entity list', self.slot_extract_current_tile_entity_list)
            menu.addAction('Extract current delayed entity list', self.slot_extract_current_delayed_entity_list)
            menu.addAction('Extract current exit region list', self.slot_extract_current_exit_region_list)
            menu.addAction('Extract current exit', self.slot_extract_current_exit)
            menu.addAction('Extract room property by symbol name', self.slot_extract_room_prop_by_symbol)
            menu.addAction('Create asset lists', self.slot_create_asset_lists)
            menu.addAction('tmp remove', self.slot_tmp2)
            menu.addAction('Sprite Test', self.slot_sprite_test)
        menu.addAction('Test modify asset list', self.test_asset_list_modification)


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


    def slot_test(self) -> None:
        #self.extract_figurine_data()
        #self.extract_areas()
        self.extract_area_table()
        #self.extract_gfx_groups()
        #self.extract_sprites()
        #self.extract_frame_obj_lists()
        #self.extract_extra_frame_offsets()


        #self.test_asset_list_modification()
        return
        '''
        symbol_name = 'gUnk_0811EE64'

        symbol = self.current_controller.symbols.find_symbol_by_name(symbol_name)
        if symbol is None:
            self.api.show_error(self.name, f'Could not find symbol {symbol_name}')
            return

        reader = self.get_reader_for_symbol(symbol)
        '''
        '''animations
        end_of_animation = False
        while not end_of_animation:
            frame_index = reader.read_u8()
            keyframe_duration = reader.read_u8()
            bitfield = reader.read_u8()
            bitfield2 = reader.read_u8()

            end_of_animation = bitfield2 & 0x80 != 0
            print(frame_index, keyframe_duration, bitfield, bitfield2 & 0x7F)
        keyframe_count = reader.read_u8()
        print(keyframe_count)
        '''

        # offset_1: 0x800 -> 0x82f4574
        # offset_2: 0xbc08 -> 0x82ff97c
        addr = 0x83163b9 - ROM_OFFSET
        size = 0x100
        data = self.current_controller.rom.get_bytes(addr, addr+size)
        reader = Reader(data, self.current_controller.symbols)

        for i in range(10):
            num_objects = reader.read_u8()
            print(num_objects)
            for i in range(num_objects):
                x_offset = reader.read_s8()
                y_offset = reader.read_s8()
                bitfield = reader.read_u8()
                bitfield2 = reader.read_u16()

                # bitfield
                override_entity_palette_index = (bitfield & 0x01) != 0
                # Bit 02 seems unused.
                h_flip = (bitfield & 0x04) != 0
                v_flip = (bitfield & 0x08) != 0
                size = (bitfield & 0x30) >> 4
                shape = (bitfield & 0xC0) >> 6

                # bitfield2
                first_gfx_tile_offset = bitfield2 & 0x03FF
                priority = (bitfield2 & 0x0C00) >> 10
                palette_index = (bitfield2 & 0xF000) >> 12


                print(x_offset, y_offset, bitfield, bitfield2)
                print(override_entity_palette_index, h_flip, v_flip, size, shape)
                print(first_gfx_tile_offset, priority, palette_index)
                print()


    def extract_frame_obj_lists(self) -> None:
        symbol_name = 'gFrameObjLists'

        symbol = self.current_controller.symbols.find_symbol_by_name(symbol_name)
        if symbol is None:
            self.api.show_error(self.name, f'Could not find symbol {symbol_name}')
            return

        reader = self.get_reader_for_symbol(symbol)

        first_level = []
        second_level = []

        lines = []
        lines.append('gFrameObjLists::\n')
        lines.append('@ First level of offsets\n')
        while True:
            if reader.cursor in first_level:
                print(f'first_level up to: {reader.cursor}')
                break
            pointer = reader.read_u32()
            first_level.append(pointer)
            lines.append(f'\t.4byte {hex(pointer)}\n')

        #print(first_level)
        lines.append('\n@ Second level of offsets\n')
        while True:
            #print(reader.cursor)
            #if reader.cursor >= 24372:
                #print(f'>< second_level up to: {reader.cursor}')
                #
                # break
            if reader.cursor in second_level:
                print(f'second_level up to: {reader.cursor}')
                break
            pointer = reader.read_u32()
            second_level.append(pointer)
            lines.append(f'\t.4byte {hex(pointer)}\n')
        #print(second_level)

        obj_lists = []
        last_second_level = max(second_level)
        lines.append('\n@ Frame obj lists\n')
        while True:
            if reader.cursor > last_second_level:
                print(f'No longer in second level: {reader.cursor}')
                break
            if reader.cursor not in second_level:
                print(f'{reader.cursor} not in second_level')
                next = -1
                for i in second_level:
                    if i > reader.cursor:
                        if next == -1 or i < next:
                            next = i

                diff = next-reader.cursor
                print(f'Skipping forward to {next} (+{diff})')
                lines.append(f'@ Skipping {diff} bytes\n')
                bytes = []
                for i in range(diff):
                    bytes.append(reader.read_u8())
                lines.append('\t.byte ' + ', '.join(str(x) for x in bytes) + '\n')
            num_objects = reader.read_u8()
            lines.append(f'\t.byte {num_objects}\n')
            if num_objects > 200:
                print(f'num_objects: {num_objects} @{reader.cursor}/{last_second_level}')
                break
            list = []
            print(num_objects)
            for i in range(num_objects):
                x_offset = reader.read_s8()
                y_offset = reader.read_s8()
                bitfield = reader.read_u8()
                bitfield2 = reader.read_u16()

                lines.append(f'\t.byte {x_offset}, {y_offset}, {hex(bitfield)}\n')
                lines.append(f'\t.2byte {hex(bitfield2)}\n')

                # bitfield
                override_entity_palette_index = (bitfield & 0x01) != 0
                # Bit 02 seems unused.
                h_flip = (bitfield & 0x04) != 0
                v_flip = (bitfield & 0x08) != 0
                size = (bitfield & 0x30) >> 4
                shape = (bitfield & 0xC0) >> 6

                # bitfield2
                first_gfx_tile_offset = bitfield2 & 0x03FF
                priority = (bitfield2 & 0x0C00) >> 10
                palette_index = (bitfield2 & 0xF000) >> 12


                # print(x_offset, y_offset, bitfield, bitfield2)
                # print(override_entity_palette_index, h_flip, v_flip, size, shape)
                # print(first_gfx_tile_offset, priority, palette_index)
                list.append({})
                # print()
            obj_lists.append(list)
        print(len(obj_lists))

        with open(os.path.join(get_repo_location(), 'build', 'tmc', 'assets', 'sprites', 'frameObjLists.s'), 'w') as file:
            file.writelines(lines)

    def extract_extra_frame_offsets(self) -> None:
        symbol_name = 'gExtraFrameOffsets'

        symbol = self.current_controller.symbols.find_symbol_by_name(symbol_name)
        if symbol is None:
            self.api.show_error(self.name, f'Could not find symbol {symbol_name}')
            return

        reader = self.get_reader_for_symbol(symbol)

        first_level = []
        second_level = []

        lines = []
        lines.append('gExtraFrameOffsets::\n')
        bytes = []
        for i in range(0x10):
            bytes.append(reader.read_u8())
        lines.append('\t.byte ' + ', '.join(str(x) for x in bytes) + '\n')

        lines.append('@ First level of offsets\n')

        while True:
            if reader.cursor in first_level:
                print(f'first_level up to: {reader.cursor}')
                break
            pointer = reader.read_u16()
            first_level.append(pointer)
            lines.append(f'\t.2byte {hex(pointer)}\n')

        #print(first_level)
        print(first_level)
        lines.append('\n@ Second level of offsets\n')
        while True:
            #print(reader.cursor)
            #if reader.cursor >= 24372:
                #print(f'>< second_level up to: {reader.cursor}')
                #
                # break
            if reader.cursor >= 0xD00:
                print(f'second_level up to: {reader.cursor}')
                break
            pointer = reader.read_u8()
            second_level.append(pointer)
            lines.append(f'\t.byte {hex(pointer)}\n')
        obj_lists = []
        lines.append('\n@ Extra frame offsets\n')
        while True:
            print('WH')
            if (reader.cursor-0xD00)/4 not in second_level:
                print(f'{reader.cursor} not in second_level')
                break
                next = -1
                for i in second_level:
                    if i > reader.cursor:
                        if next == -1 or i < next:
                            next = i

                diff = next-reader.cursor
                print(f'Skipping forward to {next} (+{diff})')
                lines.append(f'@ Skipping {diff} bytes\n')
                bytes = []
                for i in range(diff):
                    bytes.append(reader.read_u8())
                lines.append('\t.byte ' + ', '.join(str(x) for x in bytes) + '\n')

            extra_x_off = reader.read_s8()
            extra_y_off = reader.read_s8()
            lines.append(f'\textra_offset x={extra_x_off}, y={extra_y_off}\n')

            extra_x_off = reader.read_s8()
            extra_y_off = reader.read_s8()
            lines.append(f'\textra_offset x={extra_x_off}, y={extra_y_off}\n')

        with open(os.path.join(get_repo_location(), 'build', 'tmc', 'assets', 'sprites', 'extraFrameOffsets.s'), 'w') as file:
            file.writelines(lines)

    def extract_fixed_type_gfx_data(self) -> None:
        symbol_name = 'gFixedTypeGfxData'

        symbol = self.current_controller.symbols.find_symbol_by_name(symbol_name)
        if symbol is None:
            self.api.show_error(self.name, f'Could not find symbol {symbol_name}')
            return

        reader = self.get_reader_for_symbol(symbol)

        lines = []
        lines.append('gFixedTypeGfxData::\n')

        self.assets_symbol = self.current_controller.symbols.find_symbol_by_name('gGlobalGfxAndPalettes')

        index = 0
        while reader.cursor < symbol.length:
            pointer = reader.read_u32()
            gfx_data_ptr = pointer& 0x00FFFFFC
            compressed = pointer& 0x00000001

            maybe_size = ((pointer >> 0x10) & 0x7f00) >> 4

            print( (pointer& 0x7f000000) >> 0x18)
            gfx_data_len = ((pointer & 0x7F000000)>>24) * 0x200

            offset_symbol = self.current_controller.symbols.get_symbol_at(self.assets_symbol.address+gfx_data_ptr)
            if offset_symbol is None or offset_symbol.address != self.assets_symbol.address+gfx_data_ptr:
                print(f'Could not find symbol for offset {hex(gfx_data_ptr)} at {hex(self.assets_symbol.address+gfx_data_ptr)}')
                assert False

            line = f'\tfixed_gfx src={offset_symbol.name}'
            line += opt_param('size', '0x0', hex(gfx_data_len))
            line += opt_param('compressed', '0', str(compressed))
            line += f'\t@ {index}'
            lines.append(line + '\n')
            # lines.append(f'\t.4byte {hex(gfx_data_ptr)} + {compressed} + {hex((gfx_data_len//0x200))}<<24  @{index}\n')
            self.gfx_assets.append(Asset(f'fixedTypeGfx_{index}', 'gfx', gfx_data_ptr, gfx_data_len, compressed))
            index += 1

        with open(os.path.join(get_repo_location(), 'build', 'tmc', 'assets', 'sprites', 'fixedTypeGfxDataPointers.s'), 'w') as file:
            file.writelines(lines)


    def extract_palette_groups(self) -> None:
        symbol_name = 'gPaletteGroups'
        symbol = self.current_controller.symbols.find_symbol_by_name(symbol_name)
        if symbol is None:
            self.api.show_error(self.name, f'Could not find symbol {symbol_name}')
            return

        reader = self.get_reader_for_symbol(symbol)

        lines = []
        lines.append('gPaletteGroups::\n')

        group_lines: list[str] = []
        palette_pointers: set[int] = set()
        palette_offsets: list[int] = []


        i = 0

        replacements = []

        while reader.cursor < symbol.length:
            pointer = reader.read_u32()
            if pointer == 0:
                lines.append('\t.4byte 0\n')
                continue
            group_symbol = self.current_controller.symbols.get_symbol_at(pointer - ROM_OFFSET)
            palette_pointers.add(pointer)
            lines.append(f'\t.4byte {group_symbol.name}\n')
            replacements.append(f'{group_symbol.name},gPaletteGroup_{i}\n')
            i += 1
        with open('/tmp/replacements.s', 'w') as file:
            file.writelines(replacements)

        # Make sure to have them in the correct order as they don't necessary have to be in gPaletteGroups
        for pointer in sorted(list(palette_pointers)):
            print(hex(pointer))
            group_symbol = self.current_controller.symbols.get_symbol_at(pointer - ROM_OFFSET)
            (palette_group_lines, palette_indices) = self.extract_palette_group(pointer, group_symbol)
            group_lines += palette_group_lines
            palette_offsets += palette_indices


        print(set(palette_offsets))

        for palette_index in set(palette_offsets):
            self.gfx_assets.append(Asset(f'gPalette_{palette_index}', 'palette', palette_index * 0x20, 0x20, False))

        with open(os.path.join(get_repo_location(), 'build', 'tmc', 'assets', 'palettes', 'paletteGroups.s'), 'w') as file:
            file.writelines(group_lines)
            file.writelines(lines)

        print('done')

    def extract_palette_group(self, pointer: int, symbol: Symbol) -> tuple[list[str], list[int]]:
        lines: list[str] = []
        palette_indices: list[int] = []
        reader = self.get_reader_for_symbol(symbol)
        continue_loading_palette_sets = True
        lines.append(f'\n{symbol.name}::\n')
        while continue_loading_palette_sets:
            global_palette_index = reader.read_u16()
            palette_load_offset = reader.read_u8()
            bitfield = reader.read_u8()

            num_palettes = bitfield & 0x0F
            if num_palettes == 0:
                num_palettes = 0x10
            continue_loading_palette_sets = (bitfield & 0x80 == 0x80)

            # base = 0x5A2E80
            # pal_offset = global_palette_index * 0x20
            # offset_symbol = self.current_controller.symbols.get_symbol_at(base+pal_offset)
            # if offset_symbol is None or offset_symbol.address != base+pal_offset:
            #     print(f'Could not find symbol for offset {hex(pal_offset)} at {hex(base+pal_offset)}')
            #     assert False

            line = f'\tpalette_set palette={str(global_palette_index)}'
            line += opt_param('offset', '0x0', hex(palette_load_offset))
            line += opt_param('count', '0', str(num_palettes))
            line += opt_param('terminator', '0', str(1-continue_loading_palette_sets))
            lines.append(line + '\n')
            for i in range(num_palettes):
                palette_indices.append(global_palette_index + i)
        return (lines, palette_indices)

    def extract_figurine_data(self) -> None:
        symbol_name = 'gFigurines'
        symbol = self.current_controller.symbols.find_symbol_by_name(symbol_name)
        if symbol is None:
            self.api.show_error(self.name, f'Could not find symbol {symbol_name}')
            return

        reader = self.get_reader_for_symbol(symbol)

        lines = []
        lines.append('@ Figurine Data\n')
        lines.append('@ palette_data_ptr, gfx_data_ptr, gfx_data_len\n')
        lines.append('gFigurines::\n')

        i = 0
        print('RENAMES:')

        while reader.cursor < symbol.length:
            palette_data_ptr = reader.read_u32()
            gfx_data_ptr = reader.read_u32()
            gfx_data_len = reader.read_u32()
            none = reader.read_u32()
            assert none == 0
            palette_symbol = self.current_controller.symbols.get_symbol_at(palette_data_ptr-ROM_OFFSET)
            gfx_data_symbol = self.current_controller.symbols.get_symbol_at(gfx_data_ptr-ROM_OFFSET)
            lines.append(f'\t.4byte {palette_symbol.name}, {gfx_data_symbol.name}, {hex(gfx_data_len)}, 0\n')
            print(f'{palette_symbol.name},gFigurinePal{i}')
            print(f'{gfx_data_symbol.name},gFigurineGfx{i}')
            self.gfx_assets.append(Asset(f'gFigurinePal{i}', 'palette', palette_symbol.address - self.assets_symbol.address, palette_symbol.length, False))
            self.gfx_assets.append(Asset(f'gFigurineGfx{i}', 'gfx', gfx_data_symbol.address - self.assets_symbol.address, gfx_data_symbol.length, False))
            i = i+1

        with open(os.path.join(get_repo_location(), 'build', 'tmc', 'assets', 'figurines', 'figurines.s'), 'w') as file:
            file.writelines(lines)

        print('done')

    def extract_areas(self) -> None:
        symbol_name = 'gAreaMetadata'
        symbol = self.current_controller.symbols.find_symbol_by_name(symbol_name)
        if symbol is None:
            self.api.show_error(self.name, f'Could not find symbol {symbol_name}')
            return

        reader = self.get_reader_for_symbol(symbol)

        lines = []
        lines.append('gAreaMetadata::\n')

        i = 0
        while reader.cursor < symbol.length:
            print(hex(i), end = '  ')
            i += 1
            bitfield =reader.read_u8()
            area_id =reader.read_u8()
            local_flag_offset_index =reader.read_u8()
            unk = reader.read_u8()
            is_dungeon = (bitfield & 0x08) == 0x08
            is_overworld = bitfield == 0x81
            lines.append(f'\t.byte {hex(bitfield)}, {area_id}, {local_flag_offset_index}, {unk}\t@ {hex(i)}\n')
            print(hex(bitfield), area_id, local_flag_offset_index, unk)


        # with open(os.path.join(get_repo_location(), 'build', 'tmc', 'assets', 'areas', 'metadata.s'), 'w') as file:
        #     file.writelines(lines)

        #self.extract_room_properties('Room_MinishWoods_Main')
        #self.extract_room_exit_list(self.current_controller.symbols.find_symbol_by_name('gExitLists_MinishWoods_Main'))
        print('done')

    def extract_area_table(self) -> None:
        symbol_name = 'gAreaTable'
        symbol = self.current_controller.symbols.find_symbol_by_name(symbol_name)
        if symbol is None:
            self.api.show_error(self.name, f'Could not find symbol {symbol_name}')
            return

        reader = self.get_reader_for_symbol(symbol)
        self.area_names = []
        self.room_names = []
        area_index = 0
        self.replacements = []
        while reader.cursor < symbol.length:
            self.room_names.append([])
            area_symbol = self.read_symbol(reader)
            if area_symbol:
                self.area_names.append(area_symbol.name[5:])
                print(area_symbol.name)
                self.extract_area_rooms(area_index, area_symbol)
            else:
                self.area_names.append('NULL')
                print('.4byte 0')
            area_index += 1
        # print(self.area_names)
        # print(self.room_names)
        # Not used in gAreaTable, but in other tables
        self.area_names[0x61] = '61'
        self.room_names[0x61] = ['61_0']
        self.room_names[0x70].append('PalaceOfWinds_51')
        self.room_names[0x70].append('PalaceOfWinds_52')
        for i in range(len(self.room_names[0x88]), 65):
            self.room_names[0x88].append(f'DarkHyruleCastle_{i}')


        # self.extract_room_exit_lists()
        # with open('/tmp/replacements.s', 'w') as file:
        #     file.writelines(self.replacements)

        # Now extract all assets belonging to areas
        self.assets:list[Asset] = []
        self.extract_area_tilesets()
        assets_symbol = self.current_controller.symbols.find_symbol_by_name('gMapData')
        self.print_assets_list(assets_symbol, self.assets)

    def print_assets_list(self, assets_symbol: Symbol, assets:list[Asset]) -> None:
        # Show assets and empty space
        assets.sort(key=lambda x:x.offset)
        last_used_offset = 0
        previous_asset = None

        # TMP fix sizes of fixed_gfx_assets
        for i in range(len(assets)):
            asset = assets[i]
            if asset.offset < last_used_offset:
                if asset.offset == assets[i-1].offset and asset.size == assets[i-1].size:
                    pass
                else:
                    #assets[i-1].type += '_size_changed_from_' + hex(assets[i-1].size)
                    assets[i-1].size = asset.offset-assets[i-1].offset
                    print('Adapted offset of ' + assets[i-1].name)
            last_used_offset = asset.offset+asset.size
        last_used_offset = 0
        align_bytes = 0
        empty_bytes = 0
        with open(f'tmp/asset_log_{self.current_controller.rom_variant}.txt', 'w') as file:
            for asset in assets:
                if asset.offset > last_used_offset:
                    diff = asset.offset-last_used_offset
                    if diff < 4:
#                        file.write(f'  .align 4 ({diff} bytes)\n')
                        align_bytes += diff
                        #print(hex(assets_symbol.address + asset.offset))
                    else:
                        file.write(f'# empty {hex(diff)}\n')#from {hex(assets_symbol.address+previous_asset.offset+previous_asset.size)} to {hex(assets_symbol.address+asset.offset)}\n')
                        empty_bytes += diff
                elif asset.offset < last_used_offset:
                    if asset.offset == previous_asset.offset and asset.size == previous_asset.size:
                        file.write(f'  ^ same as previous: {asset.type} {asset.name}\n')
                        continue
                    file.write(f'%%% error {hex(last_used_offset-asset.offset)} bytes overlap\n')

                file.write(f'  - {asset.type} {asset.name}: {hex(asset.size)} [{"compressed" if asset.compressed else "raw"}]\n')#  @{hex(assets_symbol.address+asset.offset)}\n')
                #file.write(f'  - {asset.type} {asset.name}: {hex(asset.offset)} + {hex(asset.size)} [{"compressed" if asset.compressed else "raw"}]\n')#  @{hex(assets_symbol.address+asset.offset)}\n')

                # Export asset
                if asset.type not in ['palette']:
                    if asset.compressed:
                        with open(f'/tmp/assets/{asset.name}.4bpp.lz', 'wb') as out:
                            out.write(self.current_controller.rom.get_bytes(assets_symbol.address+asset.offset, assets_symbol.address+asset.offset+asset.size))
                    else:
                        with open(f'/tmp/assets/{asset.name}.4bpp', 'wb') as out:
                            out.write(self.current_controller.rom.get_bytes(assets_symbol.address+asset.offset, assets_symbol.address+asset.offset+asset.size))

                last_used_offset = asset.offset+asset.size
                previous_asset = asset
            file.write(f'END: {hex(assets_symbol.address+last_used_offset)} (missing: {hex((assets_symbol.length-last_used_offset))})\n')
            file.write(f'empty: {empty_bytes} align: {align_bytes}\n')


    def extract_area_rooms(self, area_index: int, symbol: Symbol) -> None:
        reader = self.get_reader_for_symbol(symbol)
        room_index = 0
        while reader.cursor < symbol.length:
            room_symbol = self.read_symbol(reader)
            if room_symbol:
                if room_symbol.name.startswith('gUnk_'):
                    self.replacements.append(f'{room_symbol.name},{self.area_names[area_index]}_{room_index}\n')
                self.room_names[area_index].append(room_symbol.name[5:])
                #self.extract_room_properties(room_symbol.name)
            else:
                self.room_names[area_index].append(f'{self.area_names[area_index]}_{room_index}')
                #print('.4byte 0')
            room_index += 1

    def extract_area_tilesets(self) -> None:
        self.extract_asset_lists('gAreaTilesets', 'tileset', True)
        self.extract_asset_lists('gAreaMetatiles', 'metatiles', False)
        self.extract_asset_lists('gAreaRoomMaps', 'map', True)

    def extract_asset_lists(self, symbol_name: str, type: str, second_indirection: bool) -> None:
        symbol = self.current_controller.symbols.find_symbol_by_name(symbol_name)
        if symbol is None:
            self.api.show_error(self.name, f'Could not find symbol {symbol_name}')
            return

        data = self.current_controller.rom.get_bytes(symbol.address, symbol.address+symbol.length )
        reader = Reader(data, self.current_controller.symbols)
        seen_symbols = set()

        while reader.cursor < symbol.length:
            asset_list_symbol = self.read_symbol(reader)
            if asset_list_symbol.name not in seen_symbols:
                seen_symbols.add(asset_list_symbol.name)
                if second_indirection:
                    self.extract_asset_list(asset_list_symbol, type)
                else:
                    self.extract_asset(asset_list_symbol, type)
        print('done')

    def extract_asset_list(self, symbol: Symbol, type: str) -> None:
        data = self.current_controller.rom.get_bytes(symbol.address, symbol.address+symbol.length )
        reader = Reader(data, self.current_controller.symbols)
        while reader.cursor < symbol.length:
            tileset_symbol = self.read_symbol(reader)
            #print(tileset_symbol)
            if tileset_symbol:
                self.extract_asset(tileset_symbol, type)

    def extract_asset(self, symbol: Symbol, type: str) -> None:
        assets_symbol = self.current_controller.symbols.find_symbol_by_name('gMapData')

        reader = self.get_reader_for_symbol(symbol)
        i = 0
        while reader.cursor < symbol.length: # TODO use as general parsing code for asset list
            asset_offset = reader.read_u32() & 0x7FFFFFFF
            ram_address = reader.read_u32()
            property_2 = reader.read_u32()
            data_length = property_2 & 0x7FFFFFFF
            compressed = property_2& 0x80000000

            if ram_address == 0:
                # TODO get palettes?
                pass
                #print('Palette' , asset_offset)
            else:

                if compressed:
                    # Read the compressed size
                    compressed_data = self.current_controller.rom.get_bytes(assets_symbol.address + asset_offset, assets_symbol.address + asset_offset+data_length)
                    # compressed_reader = Reader(compressed_data, self.current_controller.symbols)
                    # value = compressed_reader.read_u32()
                    # bvalue = compressed_reader.read_bu32()
                    # data_length = (value& 0xFFFFFF00) >> 8
                    (decompressed_data, compressed_length) = GBALZ77.decompress(compressed_data)
                    data_length = compressed_length
                    # print(hex(0x08324AE4), hex(assets_symbol.address))
                    # print(hex(assets_symbol.address + asset_offset))

                if 0x06000000 <= ram_address <= 0x0600DFFF: # Tile GFX data
                    actual_type =  type + "_gfx"
                elif ram_address == 0x0200B654: # BG1 layer data
                    actual_type = type + "_layer1"
                elif ram_address == 0x02025EB4: # BG2 layer data
                    actual_type = type + "_layer2"
                elif ram_address == 0x02012654: # BG1 tileset
                    actual_type = type + "_tileset1"
                elif ram_address == 0x0202CEB4: # BG2 tileset
                    actual_type = type + "_tileset2"
                elif ram_address == 0x02002F00: # BG1 8x8 tile mapping
                    actual_type = type + "_mapping1"
                elif ram_address == 0x02019EE0: # BG2 8x8 tile mapping
                    actual_type = type + "_mapping2"
                elif ram_address == 0x0600F000: # BG3 8x8 tile mapping
                    actual_type = type + "_mapping3"
                elif ram_address == 0x02010654: # BG1 tileset tile type data
                    actual_type = type + "_tile_types1"
                elif ram_address == 0x0202AEB4: # BG2 tileset tile type data
                    actual_type = type + "_tile_types2"
                elif ram_address == 0x02027EB4: # BG2 collision layer data
                    actual_type = type + "_collision"
                else:
                    actual_type = type + "_unknown"
                self.assets.append(Asset(symbol.name + '_' + str(i), actual_type, asset_offset, data_length, compressed))
                #print(hex(asset_offset), compressed, hex(ram_address), hex(data_length))
            i += 1

    def extract_room_properties(self, symbol_name: str) -> None:
        symbol = self.current_controller.symbols.find_symbol_by_name(symbol_name)
        if symbol is None:
            self.api.show_error(self.name, f'Could not find symbol {symbol_name}')
            return

        reader = self.get_reader_for_symbol(symbol)

        entity_list_1 = self.read_symbol(reader)
        entity_list_2 = self.read_symbol(reader)
        enemy_list = self.read_symbol(reader)
        tile_entity_list = self.read_symbol(reader)
        unknown_func_1 = self.read_symbol(reader)
        unknown_func_2 = self.read_symbol(reader)
        unknown_func_3 = self.read_symbol(reader)
        state_changing_func = self.read_symbol(reader)


        room_name = symbol_name[5:]
        if entity_list_1:
            self.replacements.append(f'{entity_list_1.name},Entities_{room_name}_0\n')
        if entity_list_2:
            self.replacements.append(f'{entity_list_2.name},Entities_{room_name}_1\n')
        if enemy_list:
            self.replacements.append(f'{enemy_list.name},Enemies_{room_name}\n')
        if tile_entity_list:
            self.replacements.append(f'{tile_entity_list.name},TileEntities_{room_name}\n')

        if unknown_func_1:
            self.replacements.append(f'{unknown_func_1.name},sub_unk1_{room_name}\n')
        if unknown_func_2:
            self.replacements.append(f'{unknown_func_2.name},sub_unk2_{room_name}\n')
        if unknown_func_3:
            self.replacements.append(f'{unknown_func_3.name},sub_unk3_{room_name}\n')
        if state_changing_func:
            self.replacements.append(f'{state_changing_func.name},sub_StateChange_{room_name}\n')
        #print('ETTTT')
        self.extract_entity_list(entity_list_1)
        self.extract_entity_list(entity_list_2)
        self.extract_entity_list(enemy_list)
        #print('TILES')
        self.extract_tile_entity_list(tile_entity_list)

        #print(entity_list_1, entity_list_2, enemy_list, tile_entity_list, unknown_func_1, unknown_func_2, unknown_func_3, state_changing_func)
        add_cnt = 0
        while reader.cursor < symbol.length:
            additional_entity_list = self.read_symbol(reader)
            #print(additional_entity_list)
            if additional_entity_list:
                self.replacements.append(f'{additional_entity_list.name},gUnk_additional{add_cnt}_{room_name}\n')
            # TODO detect delayed entity lists
            # TODO also detect other non-list pointers?
            # self.extract_entity_list(additional_entity_list)
            add_cnt += 1

    def slot_extract_current_entity_list(self) -> None:
        symbol_name = QApplication.clipboard().text()
        symbol = self.current_controller.symbols.find_symbol_by_name(symbol_name)
        #symbol = self.current_controller.symbols.get_symbol_at(self.current_controller.address_resolver.to_local(self.current_controller.cursor))
        try:
            self.extract_entity_list(symbol)
        except Exception:
            traceback.print_exc()
            self.api.show_error(self.name, 'Error in extracting entity list')

    def extract_entity_list(self, symbol: Symbol) -> list[str]:
        if symbol is None:
            return
        #print('entity list ', symbol)
        data = self.current_controller.rom.get_bytes(symbol.address, symbol.address+symbol.length + 0x100)
        reader = Reader(data, self.current_controller.symbols)
        lines = []
        while reader.cursor + 15 < symbol.length:
            type_and_unknowns = reader.read_u8()

            type = type_and_unknowns & 0x0F
            collision = (type_and_unknowns & 0xF0) >> 4
            unknowns = reader.read_u8()
            unknown_2 = unknowns & 0x0F
            unknown_3 = (unknowns & 0xF0) >> 4
            subtype = reader.read_u8()
            params_a = reader.read_u8()
            params_b = reader.read_u32()
            x = reader.read_u16()
            y = reader.read_u16()
            params_c = reader.read_u32()
            if type_and_unknowns == 0xff: # End of list
                lines.append('\tentity_list_end')
                if reader.cursor == symbol.length:
                    break
                else:
                    lines.append('\n')
                    continue

            line = ''

            if type == 9: # manager
                line = f'\tmanager subtype={hex(subtype)}'
                line += opt_param('x', '0x0', hex(x))
                line += opt_param('y', '0x0', hex(y))
                line += opt_param('unknown', '0xf', hex(unknowns))
                line += opt_param('collision', '0', str(collision))
                line += opt_param('paramA', '0x0', hex(params_a))
                line += opt_param('paramB', '0x0', hex(params_b))
                line += opt_param('paramC', '0x0', hex(params_c))
            elif type == 6: # object
                line = f'\tobject_raw subtype={hex(subtype)}'
                line += opt_param('x', '0x0', hex(x))
                line += opt_param('y', '0x0', hex(y))
                line += opt_param('unknown', '0xf', hex(unknowns))
                line += opt_param('collision', '0', str(collision))
                line += opt_param('paramA', '0x0', hex(params_a))
                line += opt_param('paramB', '0x0', hex(params_b))


                script_symbol = self.current_controller.symbols.get_symbol_at(params_c-ROM_OFFSET)
                if script_symbol and script_symbol.address+ROM_OFFSET == params_c:
                    line += f', paramC={script_symbol.name}' # script pointer in object 0x6A
                else:
                    line += opt_param('paramC', '0x0', hex(params_c))
            elif type == 3: # enemy
                line = f'\tenemy_raw subtype={hex(subtype)}'
                line += opt_param('x', '0x0', hex(x))
                line += opt_param('y', '0x0', hex(y))
                line += opt_param('unknown', '0xf', hex(unknowns))
                line += opt_param('collision', '0', str(collision))
                line += opt_param('paramA', '0x0', hex(params_a))
                line += opt_param('paramB', '0x0', hex(params_b))
                line += opt_param('paramC', '0x0', hex(params_c))
            elif type == 7: # npc
                script = hex(params_c)
                script_symbol = self.current_controller.symbols.get_symbol_at(params_c-ROM_OFFSET)
                if script_symbol and script_symbol.address+ROM_OFFSET == params_c:
                    script = script_symbol.name
                line = f'\tnpc_raw subtype={hex(subtype)}'
                line += opt_param('x', '0x0', hex(x))
                line += opt_param('y', '0x0', hex(y))
                line += opt_param('unknown', '0x4f', hex(unknowns))
                line += opt_param('collision', '0', str(collision))
                line += opt_param('paramA', '0x0', hex(params_a))
                line += opt_param('paramB', '0x0', hex(params_b))
                line += f', script={script}'
            else:
                line = f'\tentity_raw type={hex(type)}, subtype={hex(subtype)}'
                line += opt_param('x', '0x0', hex(x))
                line += opt_param('y', '0x0', hex(y))
                line += f', unknown={hex(unknowns)}'
                line += opt_param('collision', '0', str(collision))
                line += opt_param('paramA', '0x0', hex(params_a))
                line += opt_param('paramB', '0x0', hex(params_b))
                line += opt_param('paramC', '0x0', hex(params_c))

            lines.append(line + '\n')

        if reader.cursor < symbol.length:
            lines.append('@ unaccounted bytes\n')
            while reader.cursor < symbol.length:
                lines.append(f'\t.byte {reader.read_u8()}\n')
        # print()
        # print (''.join(lines))
        QApplication.clipboard().setText(''.join(lines))
        return lines

    def slot_extract_current_tile_entity_list(self) -> None:
        symbol = self.current_controller.symbols.get_symbol_at(self.current_controller.address_resolver.to_local(self.current_controller.cursor))
        try:
            self.extract_tile_entity_list(symbol)
        except Exception:
            traceback.print_exc()
            self.api.show_error(self.name, 'Error in extracting tile entity list')

    def extract_tile_entity_list(self, symbol: Symbol) -> list[str]:
        if symbol is None:
            return
        print('tile entity list ', symbol)
        data = self.current_controller.rom.get_bytes(symbol.address, symbol.address+symbol.length + 0x100)
        reader = Reader(data, self.current_controller.symbols)
        lines = []
        while reader.cursor < symbol.length:
            type = reader.read_u8()
            params_a = reader.read_u8()
            params_b = reader.read_u16()
            params_c = reader.read_u16()
            params_d = reader.read_u16()
            if type == 0:
                lines.append('\ttile_entity_list_end')
                break
            line = f'\ttile_entity type={hex(type)}'
            line += opt_param('paramA', '0x0', hex(params_a))
            line += opt_param('paramB', '0x0', hex(params_b))
            line += opt_param('paramC', '0x0', hex(params_c))
            line += opt_param('paramD', '0x0', hex(params_d))
            lines.append(line + '\n')

        if reader.cursor < symbol.length:
            lines.append('@ unaccounted bytes\n')
            while reader.cursor < symbol.length:
                lines.append(f'\t.byte {reader.read_u8()}\n')
        print()
        print (''.join(lines))
        QApplication.clipboard().setText(''.join(lines))
        return lines

    def slot_extract_current_delayed_entity_list(self) -> None:
        symbol = self.current_controller.symbols.get_symbol_at(self.current_controller.address_resolver.to_local(self.current_controller.cursor))
        try:
            self.extract_delayed_entity_list(symbol)
        except Exception:
            traceback.print_exc()
            self.api.show_error(self.name, 'Error in extracting delayed entity list')

    def extract_delayed_entity_list(self, symbol: Symbol) -> list[str]:
        if symbol is None:
            return
        data = self.current_controller.rom.get_bytes(symbol.address, symbol.address+symbol.length + 0x100)
        reader = Reader(data, self.current_controller.symbols)
        lines = []
        while reader.cursor + 15 < symbol.length:

            subtype = reader.read_u8()
            params_a = reader.read_u8()
            params_b = reader.read_u8()
            layer = reader.read_u8()
            x = reader.read_u16()
            y = reader.read_u16()
            params_c = reader.read_u32()
            params_d = reader.read_u16()
            conditions = reader.read_u16()

            if subtype == 0xff: # End of list
                lines.append('\tentity_list_end')
                if reader.cursor == symbol.length:
                    break
                else:
                    lines.append('\n')
                    continue

            line = f'\tdelayed_entity_raw subtype={hex(subtype)}'
            line += opt_param('x', '0x0', hex(x))
            line += opt_param('y', '0x0', hex(y))
            line += opt_param('layer', '0', str(layer))
            line += opt_param('paramA', '0x0', hex(params_a))
            line += opt_param('paramB', '0x0', hex(params_b))
            script_symbol = self.current_controller.symbols.get_symbol_at(params_c-ROM_OFFSET)
            if script_symbol and script_symbol.address+ROM_OFFSET == params_c:
                line += f', paramC={script_symbol.name}' # script pointer in object 0x6A
            else:
                line += opt_param('paramC', '0x0', hex(params_c))
            line += opt_param('paramD', '0x0', hex(params_d))
            line += opt_param('conditions', '0x0', hex(conditions))

            lines.append(line + '\n')

        if reader.cursor < symbol.length:
            lines.append('@ unaccounted bytes\n')
            while reader.cursor < symbol.length:
                lines.append(f'\t.byte {reader.read_u8()}\n')
        print()
        print (''.join(lines))
        QApplication.clipboard().setText(''.join(lines))
        return lines

    def slot_extract_current_exit_region_list(self) -> None:
        symbol_name = QApplication.clipboard().text()
        symbol = self.current_controller.symbols.find_symbol_by_name(symbol_name)
        #symbol = self.current_controller.symbols.get_symbol_at(self.current_controller.address_resolver.to_local(self.current_controller.cursor))
        try:
            self.extract_exit_region_list(symbol)
        except Exception:
            traceback.print_exc()
            self.api.show_error(self.name, 'Error in extracting exit region list')

    def extract_exit_region_list(self, symbol: Symbol) -> list[str]:
        if symbol is None:
            return
        data = self.current_controller.rom.get_bytes(symbol.address, symbol.address+symbol.length + 0x100)
        reader = Reader(data, self.current_controller.symbols)
        lines = []
        while reader.cursor + 7 < symbol.length:

            # minish entrance list just exists once
            # x = reader.read_u16()
            # y = reader.read_u16()
            # unknown = reader.read_u16()
            # actionDelay = reader.read_u16()

            # line = f'\tminish_entrance x={hex(x)}, y={hex(y)}'
            # line += opt_param('unknown', '0x0', hex(unknown))
            # line += opt_param('actionDelay', '0x0', hex(actionDelay))


            center_x = reader.read_u16()
            center_y = reader.read_u16()
            half_width = reader.read_u8()
            half_height = reader.read_u8()
            exit_pointer_property_index = reader.read_u8()
            bitfield = reader.read_u8()

            if center_x == 0xffff: # End of list
                lines.append('\texit_region_list_end')
                if reader.cursor == symbol.length:
                    break
                else:
                    lines.append('\n')
                    continue

            line = f'\texit_region_raw centerX={hex(center_x)}, centerY={hex(center_y)}'
            line += opt_param('halfWidth', '0x0', hex(half_width))
            line += opt_param('halfHeight', '0x0', hex(half_height))
            line += opt_param('exitIndex', '0x0', hex(exit_pointer_property_index))
            line += opt_param('bitfield', '0x0', hex(bitfield))

            lines.append(line + '\n')

        if reader.cursor < symbol.length:
            lines.append('@ unaccounted bytes\n')
            while reader.cursor < symbol.length:
                lines.append(f'\t.byte {reader.read_u8()}\n')
        print()
        print (''.join(lines))
        QApplication.clipboard().setText(''.join(lines))
        return lines

    def slot_extract_current_exit(self) -> None:
        symbol_name = QApplication.clipboard().text()
        symbol = self.current_controller.symbols.find_symbol_by_name(symbol_name)
        #symbol = self.current_controller.symbols.get_symbol_at(self.current_controller.address_resolver.to_local(self.current_controller.cursor))
        try:
            self.extract_exit(symbol)
        except Exception:
            traceback.print_exc()
            self.api.show_error(self.name, 'Error in extracting exit region list')

    def extract_exit(self, symbol: Symbol) -> list[str]:
        if symbol is None:
            return
        data = self.current_controller.rom.get_bytes(symbol.address, symbol.address+symbol.length + 0x100)
        reader = Reader(data, self.current_controller.symbols)
        lines = []
        transition_type = reader.read_u16()
        x_pos = reader.read_u16()
        y_pos = reader.read_u16()
        dest_x = reader.read_u16()
        dest_y = reader.read_u16()
        screen_edge = reader.read_u8()
        dest_area = reader.read_u8()
        dest_room = reader.read_u8()
        unknown_2 = reader.read_u8()
        unknown_3 = reader.read_u8()
        unknown_4 = reader.read_u8()
        unknown_5 = reader.read_u16()
        padding_1 = reader.read_u16()

        assert(padding_1 == 0)

        line = f'\texit_raw transition={hex(transition_type)}'
        line += opt_param('x', '0x0', hex(x_pos))
        line += opt_param('y', '0x0', hex(y_pos))
        line += opt_param('destX', '0x0', hex(dest_x))
        line += opt_param('destY', '0x0', hex(dest_y))
        line += opt_param('screenEdge', '0x0', hex(screen_edge))
        line += opt_param('destArea', '0x0', hex(dest_area))
        line += opt_param('destRoom', '0x0', hex(dest_room))
        line += opt_param('unknownA', '0x0', hex(unknown_2))
        line += opt_param('unknownB', '0x0', hex(unknown_3))
        line += opt_param('unknownC', '0x0', hex(unknown_4))
        line += opt_param('unknownD', '0x0', hex(unknown_5))

        lines.append(line)

        if reader.cursor < symbol.length:
            lines.append('@ unaccounted bytes\n')
            while reader.cursor < symbol.length:
                lines.append(f'\t.byte {reader.read_u8()}\n')
        print()
        print (''.join(lines))
        QApplication.clipboard().setText(''.join(lines))
        return lines


    def slot_extract_room_prop_by_symbol(self) -> None:
        # (symbol_name, ok) = self.api.show_text_input(self.name, 'Enter symbol')
        # if not ok:
        #     return
        symbol_name = QApplication.clipboard().text()
        symbol = self.current_controller.symbols.find_symbol_by_name(symbol_name)
        if symbol is None:
            self.api.show_error(self.name, f'Symbol {symbol_name} not found.')
            return
        if symbol_name.startswith('Entities_') or symbol_name.startswith('Enemies_'):
            self.extract_entity_list(symbol)
        elif symbol_name.startswith('TileEntities_'):
            self.extract_tile_entity_list(symbol)
        else:
            self.api.show_error(self.name, f'Do not know what type {symbol_name} is.')

    def extract_room_exit_lists(self) -> None:
        symbol_name = 'gExitLists'
        symbol = self.current_controller.symbols.find_symbol_by_name(symbol_name)
        if symbol is None:
            self.api.show_error(self.name, f'Could not find symbol {symbol_name}')
            return

        reader = self.get_reader_for_symbol(symbol)
        area_index = 0

        while reader.cursor < symbol.length:
            room_list = self.read_symbol(reader)
            if room_list.name != 'gExitLists_NoExit':
                self.replacements.append(f'{room_list.name},gExitLists_{self.area_names[area_index]}\n')

                room_index = 0
                data2 = self.current_controller.rom.get_bytes(room_list.address, room_list.address+room_list.length)
                reader2 = Reader(data2, self.current_controller.symbols)
                while reader2.cursor < room_list.length:
                    exit_list = self.read_symbol(reader2)
                    if exit_list and exit_list.name != 'gExitLists_NoExitList':
                        print(area_index, room_index)
                        print(self.room_names[area_index][room_index], exit_list)
                        self.replacements.append(f'{exit_list.name},gExitList_{self.room_names[area_index][room_index]}\n')
                    room_index += 1
            area_index += 1

    def extract_room_exit_list(self, symbol: Symbol) -> None:
        if symbol is None:
            return
        data = self.current_controller.rom.get_bytes(symbol.address, symbol.address+symbol.length + 0x100)
        reader = Reader(data, self.current_controller.symbols)
        print('exit list ', symbol)
        while reader.cursor < symbol.length:
            transition_type = reader.read_u16()
            x_pos = reader.read_u16()
            y_pos = reader.read_u16()
            dest_x = reader.read_u16()
            dest_y = reader.read_u16()
            screen_edge = reader.read_u8()
            dest_area = reader.read_u8()
            dest_room = reader.read_u8()
            unknown_2 = reader.read_u8()
            unknown_3 = reader.read_u8()
            unknown_4 = reader.read_u8()
            unknown_5 = reader.read_u16()
            padding_1 = reader.read_u16()
            if transition_type == 0xffff:
                break
            print(transition_type, x_pos, y_pos, dest_x, dest_y, screen_edge, dest_area, dest_room, unknown_2, unknown_3, unknown_4, unknown_5, padding_1)


    def extract_gfx_groups(self) -> None:
        self.assets_symbol = self.current_controller.symbols.find_symbol_by_name('gGlobalGfxAndPalettes')

        symbol_name = 'gGfxGroups'
        symbol = self.current_controller.symbols.find_symbol_by_name(symbol_name)
        if symbol is None:
            self.api.show_error(self.name, f'Could not find symbol {symbol_name}')
            return

        reader = self.get_reader_for_symbol(symbol)

        lines = []
        group_lines = []
        self.replacements = []

        seen_groups = set()
        self.gfx_assets = []
        lines.append(f'{symbol_name}::\n')
        group_index = 0
        while reader.cursor < symbol.length:
            group_ptr = self.read_symbol(reader)
            if group_ptr:
                if group_ptr.name not in seen_groups:
                    group_lines.append((group_ptr.address, self.extract_gfx_group(group_ptr, group_index)))
                    seen_groups.add(group_ptr.name)
                lines.append(f'\t.4byte {group_ptr.name}\n')
            else:
                lines.append(f'\t.4byte 0\n')
            group_index += 1

        with open(os.path.join(get_repo_location(), 'build', 'tmc', 'assets', 'gfx', 'gfxGroups.s'), 'w') as file:
            group_lines.sort(key=lambda x:x[0])
            for (addr,glines) in group_lines:
                file.writelines(glines)
            file.writelines(lines)



        # Extract other gfx in gGlobalGfxAndPalettes
        self.extract_fixed_type_gfx_data()
        self.extract_palette_groups()

        # Add otherwise known gfx assets
        #self.gfx_assets.append(Asset('gFigurinePals', 'palette', 0x13040, 0x7740, False))
        #self.gfx_assets.append(Asset('gFigurineGfx', 'gfx', 0x29cc80, 0x82780-0x8c0, False))




        # print('---------')
        # for replacement in self.replacements:
        #     print(replacement[0]+','+replacement[1])

    def get_compressed_length(self, addr: int, uncompressed_length: int) -> int:
        compressed_data = self.current_controller.rom.get_bytes(addr, addr+uncompressed_length)
        (decompressed_data, compressed_length) = GBALZ77.decompress(compressed_data)
        return compressed_length

    def extract_gfx_group(self, symbol: Symbol, group_index: int) -> list[str]:
        print(symbol)
        reader = self.get_reader_for_symbol(symbol)
        self.replacements.append((symbol.name, f'gGfxGroup_{group_index}'))
        gfx_index = 0
        lines = []
        lines.append(f'\n{symbol.name}::\n')
        while reader.cursor < symbol.length:
            unk0 = reader.read_u32()
            gfx_offset = unk0 & 0xFFFFFF
            dest = reader.read_u32()
            unk8 = reader.read_u32()
            size = unk8 & 0xFFFFFF
            terminator = unk0 & 0x80000000 == 0x80000000

            print(f'gGfx_{group_index}_{gfx_index}')
            compressed = (unk8 & 0x80000000) // 0x80000000
            uncompressed_size = size
            if compressed:
                size = self.get_compressed_length(self.assets_symbol.address + gfx_offset, size)
            #try:
            #except DecompressionError:
                #compressed_size = size
                #compressed = False
            if gfx_offset != 0:
                self.gfx_assets.append(Asset(f'gGfx_{group_index}_{gfx_index}', 'gfx', gfx_offset, size, compressed))
            print(hex(gfx_offset), hex(dest), hex(size))

            base = 0x5A2B18
            offset_symbol = self.current_controller.symbols.get_symbol_at(base+gfx_offset)
            if offset_symbol is None or offset_symbol.address != base+gfx_offset:
                print(f'Could not find symbol for offset {hex(gfx_offset)} at {hex(base+gfx_offset)}')
                assert False

            line = f'\tgfx_raw src={offset_symbol.name}'

            line += opt_param('unknown', '0x0', hex((unk0 & 0xF000000)//0x1000000))
            line += opt_param('dest', '0x0', hex(dest))
            line += opt_param('size', '0x0', hex(uncompressed_size))
            line += opt_param('compressed', '0', str(compressed))
            line += opt_param('terminator', '0', str(1-terminator))

            lines.append(line+'\n')
            #lines.append(f'\t.4byte {hex(gfx_offset)}+{hex(terminator)}+{hex(unk0 & 0xF000000)}, {hex(dest)}, {hex(uncompressed_size)} + {hex(compressed)} @ {gfx_index}\n')
            if not terminator:
                break
            gfx_index += 1
        return lines

    def extract_sprites(self) -> None:
        symbol_name = 'gSpritePtrs'
        symbol = self.current_controller.symbols.find_symbol_by_name(symbol_name)
        if symbol is None:
            self.api.show_error(self.name, f'Could not find symbol {symbol_name}')
            return

        reader = self.get_reader_for_symbol(symbol)

        self.replacements = []

        i = 0
        while reader.cursor < symbol.length:
            animation_ptr = self.read_symbol(reader)
            frame_gfx_data_list_ptr = self.read_symbol(reader)
            gfx_pointer = self.read_symbol(reader)
            pad = reader.read_u32()
            assert(pad == 0)
            if frame_gfx_data_list_ptr:
                self.extract_sprite_frame(frame_gfx_data_list_ptr)
            if animation_ptr:
                self.extract_animation_list(animation_ptr)
            i += 1

        with open('/tmp/replacements.s', 'w') as file:
            file.writelines(self.replacements)

    def extract_sprite_frame(self, symbol: Symbol) -> None:
        reader = self.get_reader_for_symbol(symbol)
        i = 0
        while reader.cursor < symbol.length:
            num_gfx_tiles = reader.read_u8()
            unk = reader.read_u8()
            first_gfx_tile_index = reader.read_u16()
            print(f'\t.byte {num_gfx_tiles}, {hex(unk)} @ frame {i}')
            print(f'\t.2byte {hex(first_gfx_tile_index)}')
            assert(unk == 0 or unk == 1 or unk == 0xff)
            i += 1

    def extract_animation_list(self, symbol: Symbol) -> None:
        reader = self.get_reader_for_symbol(symbol)

        lines = []
        animation_lines = []
        lines.append(symbol.name + '::\n')
        i = 0
        while reader.cursor < symbol.length:
            animation_ptr = self.read_symbol(reader)
            if animation_ptr:
                lines.append(f'\t.4byte {symbol.name}_{i}\n')
                animation_lines += self.extract_animation(animation_ptr, f'{symbol.name}_{i}')
                self.replacements.append(f'{animation_ptr.name},{symbol.name}_{i}\n')
            else:
                lines.append(f'\t.4byte 0\n')
            i += 1

        # with open(os.path.join(get_repo_location(), 'build', 'tmc', 'assets', 'animations', symbol.name+'.s'), 'w') as file:
        #     file.writelines(animation_lines)
        #     file.writelines(lines)

    def extract_animation(self, symbol: Symbol, new_name: str) -> list[str]:
        reader = self.get_reader_for_symbol(symbol)
        lines = []
        print(new_name)
        lines.append(f'{new_name}:: @{symbol.name}\n')
        end_of_animation = False
        while not end_of_animation and reader.cursor+3 < symbol.length:
            frame_index = reader.read_u8()
            keyframe_duration = reader.read_u8()
            bitfield = reader.read_u8()
            bitfield2 = reader.read_u8()

            end_of_animation = bitfield2 & 0x80 != 0
            lines.append(f'\t.byte {frame_index}, {keyframe_duration}, {hex(bitfield)}, {hex(bitfield2)}\n')
            print(frame_index, keyframe_duration, bitfield, bitfield2)
        if not end_of_animation:
            lines.append('@ TODO why no terminator?\n')
        while reader.cursor < symbol.length:
            keyframe_count = reader.read_u8()
            lines.append(f'\t.byte {keyframe_count} @ keyframe count\n')
        return lines

    def read_symbol(self, reader: Reader) -> Symbol:
        ptr = reader.read_u32()
        if ptr == 0:
            return None
        symbol = self.current_controller.symbols.get_symbol_at(ptr - ROM_OFFSET)
        if symbol is None:
            print(f'Could not find symbol for {hex(ptr)}')
        return symbol


    def extract_data(self, code: str, symbols: SymbolList, rom: Rom) -> str:
        type = self.parse_type(code)

        if type is None:
            raise Exception(f'Could not parse type of `{code}`')

        symbol = symbols.find_symbol_by_name(type.name)
        if symbol is None:
            raise Exception(f'Could not find symbol {type.name}')

        text = ''

        data = rom.get_bytes(symbol.address, symbol.address+symbol.length)
        reader = Reader(data, symbols)

        if type.regex == 0:
            res = read_var(reader, type.type)
            text = 'const ' + type.type + ' ' + type.name + ' = ' + self.get_struct_init(res) + ';';
        elif type.regex == 1:
            if type.type == 'u8':
                text = 'const ' + type.type + ' ' + type.name + '[] = {'
                for i in range(symbol.address, symbol.address+symbol.length):
                    text += str(rom.get_byte(i)) + ', '
                text += '};'
            elif '*' in type.type: # pointers
                if symbol.length % 4 != 0:
                    raise Exception('Incorrect data length')

                text = 'const ' + type.type + ' ' + type.name + '[] = {'
                for i in range(symbol.address, symbol.address+symbol.length, 4):
                    pointer = rom.get_pointer(i)
                    pointer_symbol = symbols.get_symbol_at(pointer - ROM_OFFSET)
                    text += '&' + pointer_symbol.name + ', '
                text += '};'
            else:
                res = read_var(reader, type.type + '[]')
                text = 'const ' + type.type + ' ' + type.name + '[] = ' + self.get_struct_init(res) + ';';
        elif type.regex == 3:
            if symbol.length % 4 != 0:
                raise Exception('Incorrect data length')

            text = 'void (*const ' + type.name + '[])(' + type.params + ') = {'
            for i in range(symbol.address, symbol.address+symbol.length, 4):
                pointer = rom.get_pointer(i)
                pointer_symbol = symbols.get_symbol_at(pointer - ROM_OFFSET)
                text += pointer_symbol.name + ', '
            text += '};'
        else:
            raise Exception(f'Unimplemented type for regex {type.regex}')
        return text

    def slot_extract_data(self) -> None:
        if self.current_controller.symbols is None:
            self.api.show_error(self.name, f'No symbols loaded for current editor')
            return
        # symbol = self.current_controller.symbols.get_symbol_at(self.current_controller.address_resolver.to_local(self.current_controller.cursor))


        (type_str, ok) = self.api.show_text_input(self.name, 'Enter data code')
        if not ok:
            return
        print(type_str)

        try:
            text = self.extract_data(type_str, self.current_controller.symbols, self.current_controller.rom)
        except Exception as e:
            traceback.print_exc()
            self.api.show_error(self.name, str(e))
        QApplication.clipboard().setText(text)
        print(text)


    def read_str(self, symbol):
        res = ''
        reader = self.get_reader_for_symbol(symbol)
        while reader.cursor < symbol.length:
            byte = reader.read_u8()
            if byte == 0:
                break
            res += chr(byte)
        return res

    def slot_tmp(self) -> None:
        self.gfx_assets = []
        # self.extract_palette_groups()
        #self.extract_fixed_type_gfx_data()
        #self.extract_extra_frame_offsets()
        #self.extract_frame_obj_lists()

	# .4byte gSpriteAnimation_FileScreenObjects
	# .4byte 00000000
	# .4byte 00000000
	# .4byte 00000000

	# .4byte gSpriteAnimation_ObjectA2
	# .4byte 00000000
	# .4byte 00000000
	# .4byte 00000000

	# .4byte gSpriteAnimation_Object6A_9
	# .4byte 00000000
	# .4byte 00000000
	# .4byte 00000000

	# .4byte gSpriteAnimation_Vaati_1

        self.replacements = []
        animation_ptr = self.current_controller.symbols.find_symbol_by_name('gSpriteAnimation_Vaati_1')
        self.extract_animation_list(animation_ptr)
        with open('/tmp/replacements.s', 'w') as file:
            file.writelines(self.replacements)


        return

        start_symbol = self.current_controller.symbols.find_symbol_by_name('gMapData')
        in_lines = QApplication.clipboard().text().split('\n')
        out_lines = []
        for line in in_lines:
            arr = line.split(' ')
            if len(arr) >= 4 and arr[2] != '0x0,':
                offset = int(arr[1][0:-1], 16)
                addr = start_symbol.address + offset
                symbol = self.current_controller.symbols.get_symbol_at(addr)
                if symbol is None or symbol.address != addr:
                    print(f'Could not find symbol for addr {hex(addr)} (offset: {hex(offset)})')
                    #assert(False)
                else:
                    arr[1] = symbol.name + ','
                    line = ' '.join(arr)
                    print(offset)
            out_lines.append(line)

        print('\n'.join(out_lines))
        QApplication.clipboard().setText('\n'.join(out_lines))

        # Enum extraction

        #ENUM_12AED0
        # USA
        # """
        # ENUM_STARTS = [
        #     0x812aaec,
        #     0x812b20c,
        #     0x812c600,
        #     0x812e60c,
        #     0x812f4a4,
        #     0x812fa3c,
        #     0x812feac,
        #     0x8130378,
        #     0x8130e0c,
        #     0x81316ac
        # ]"""
        # ENUM_STARTS = [
        #     # 0x812b20c #usa
        #     #0x812AED0 # jp
        #     0x812bd8c # demo_jp
        # ]

        # symbol_name = 'ENUM_12'

        # symbol = self.current_controller.symbols.find_symbol_by_name(symbol_name)
        # if symbol is None:
        #     self.api.show_error(self.name, f'Could not find symbol {symbol_name}')
        #     return
        # ptr = symbol.address
        # prefix = 'ENUM_' + hex(ptr)[2:].upper()
        # data = self.current_controller.rom.get_bytes(symbol.address, symbol.address+symbol.length)
        # reader = Reader(data, self.current_controller.symbols)

        # values=[]
        # while reader.cursor < symbol.length:
        #     entry = self.read_symbol(reader)
        #     if entry and entry.length > 0:
        #         print(entry)
        #         values.append(self.read_str(entry))
        #     # entry = bytes_to_u32(baserom_data[ptr:ptr+4])
        #     # if entry < ROM_START or entry-ROM_START > len(baserom_data):
        #     #     break
        #     # values.append(read_str(baserom_data, entry-ROM_START))
        #     # ptr += 4

        # lines = []
        # lines.append(f'{prefix}:\n')
        # for value in values:
        #     lines.append(f'\t.4byte {prefix}_{value}\n')

        # for value in reversed(values):
        #     lines.append(f'{prefix}_{value}:\n')
        #     pad = ''
        #     count = (4 - ((len(value) + 1) % 4)) % 4
        #     for i in range(count):
        #         pad += '\\0'
        #     lines.append(f'\t.ascii "{value}\\0{pad}"\n')

        # print (''.join(lines))
        # QApplication.clipboard().setText(''.join(lines))



        # entity_datas = []
        # # Find all EntityData in room.c
        # with open(os.path.join(get_repo_location(), 'src', 'room.c'), 'r') as file:
        #     for line in file:
        #         match = re.search('EntityData (.*);', line)
        #         if match:
        #             entity_datas.append(match.group(1))
        # in_lines = []
        # with open(os.path.join(get_repo_location(), 'data', 'map', 'entity_headers.s'), 'r') as file:
        #     in_lines = file.readlines()

        # out_lines = []
        # current_symbol = None
        # ignoring = False
        # for line in in_lines:
        #     if '.ifdef' in line or '.else' in line or '.endif' in line:
        #         if ignoring:
        #             out_lines.append('@ FIXME ')
        #         ignoring = False
        #     if ':: @' in line:
        #         arr = line.split(':')
        #         current_symbol = arr[0]
        #         ignoring = False
        #     if ignoring:
        #         continue
        #     if '.incbin' in line:
        #         if current_symbol in entity_datas:
        #             symbol = self.current_controller.symbols.find_symbol_by_name(current_symbol)
        #             out_lines += self.extract_entity_list(symbol)
        #             out_lines.append('\n\n')
        #             ignoring = True
        #             continue
        #         # if 'entity_lists/' in line:
        #         #     symbol = self.current_controller.symbols.find_symbol_by_name(current_symbol)
        #         #     if current_symbol.startswith('Entities_') or current_symbol.startswith('Enemies_'):
        #         #         out_lines += self.extract_entity_list(symbol)
        #         #         out_lines.append('\n\n')
        #         #         ignoring = True
        #         #     elif current_symbol.startswith('TileEntities_'):
        #         #         out_lines += self.extract_tile_entity_list(symbol)
        #         #         out_lines.append('\n\n')
        #         #         ignoring = True
        #         #     else:
        #         #         self.api.show_error(self.name, f'Do not know what type {current_symbol} is.')
        #         #     continue
        #     out_lines.append(line)
        # with open('/tmp/teset.s', 'w') as file:
        #     file.writelines(out_lines)

    def parse_type(self, type: str) -> DataType:
        match = re.search('(extern )?(const )?(?P<type>\S+) (?P<name>\w+);', type)
        if match is not None:
            return DataType(0, match.group('name'), match.group('type'), 0, 0, '')

        match = re.search('(extern )?(const )?(?P<type>\S+) (\*?const )?(?P<name>\w+)\[(?P<count>\w+)?\];', type)
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
                elif type(obj[key]) is dict: # No names for struct initialisation
                    text += separator + self.get_struct_init(obj[key])
                else:
                    if type(obj[key]) != int or obj[key] < 0x1000000:
                        text += separator + str(obj[key])
                    else:
                        text += separator + hex(obj[key])
                separator = ', '
            text += ' }'
        return text


    def test_asset_list_modification(self) -> None:
        # Align map assets
        assets = read_assets('map.json')
        for asset in assets.assets:
            if 'path' in asset:
                start = asset['start']
                if start % 4 != 0:
                    diff = 4 - start % 4;
                    asset['start'] = start + diff;
                    asset['size'] -= diff;

        write_assets('map.json', assets)

        # Add sizes and headerOffsets to the sounds
        #assets = read_assets('sounds.json')
        # offsets = {}
        # for variant in ['EU', 'JP', 'DEMO_USA', 'DEMO_JP']:
        #     offsets[variant] = 0
        # for asset in assets.assets:
        #     if 'offsets' in asset:
        #         for key in asset['offsets']:
        #             offsets[key] = asset['offsets'][key]
        #     if 'path' in asset:
        #         label = asset['path'][7:-4]
        #         print(label)

        #         header_symbol = self.current_controller.symbols.find_symbol_by_name(label)
        #         first_track_symbol = self.current_controller.symbols.find_symbol_by_name(label+'_1')

        #         asset['start'] = first_track_symbol.address
        #         asset['options']['headerOffset'] = header_symbol.address - first_track_symbol.address
        #         asset['size'] = header_symbol.address + header_symbol.length - first_track_symbol.address
        # write_assets('sounds.json', assets)

        # # Find all offsets at a certain path, so that we can move everything after into a different json file
        # target_path = 'programmable_wave_samples/gUnk_08A11BAC.bin'
        # offsets = {}
        # for variant in ['EU', 'JP', 'DEMO_USA', 'DEMO_JP']:
        #     offsets[variant] = 0

        # for asset in assets.assets:
        #     if 'offsets' in asset:
        #         for key in asset['offsets']:
        #             offsets[key] = asset['offsets'][key]
        #     if 'path' in asset:
        #         if asset['path'] == target_path:
        #             print(target_path)
        #             print(json.dumps({'offsets': offsets}, indent=2))
        #             break

        print('done')

        # Find the most and biggest assets
        # stats = {}
        # for asset in assets.assets:
        #     if 'path' in asset:
        #         folder = asset['path'][0:asset['path'].index('/')]
        #         if not folder in stats:
        #             stats[folder] = {
        #                 'count': 0,
        #                 'size': 0
        #             }
        #         stats[folder]['count'] += 1
        #         if 'size' in asset:
        #             stats[folder]['size'] += asset['size']

        # lists = []
        # for key in stats:
        #     stat = stats[key]
        #     lists.append({
        #         'folder': key,
        #         'count': stat['count'],
        #         'size': stat['size']
        #     })

        # lists.sort(key=lambda x:x['count'])
        # #lists.sort(key=lambda x:x['size'])
        # for entry in lists:
        #     print(entry['folder'] + ' ('+str(entry['count'])+') ' + str(entry['size']))





        # for asset in assets.assets:
        #     if 'path' in asset:
        #         if 'entity_lists/' in asset['path']:
        #             asset['type'] = 'entity_list'

        # write_assets(assets)

        # symbol = self.current_controller.symbols.find_symbol_by_name('gPaletteGroups')

        # asset = {
        #     'path': 'palettes/paletteGroups.s',
        #     'start': symbol.address,
        #     'size': symbol.length,
        #     'type': 'palette_groups'
        # }
        # next_asset = assets.get_asset_at_of_after(symbol.address, RomVariant.USA)

        # replacements = []
        # for asset in assets.assets:
        #     if 'path' in asset:
        #         if 'gSpriteAnimations' in asset['path']:
        #             arr = asset['path'].split('gSpriteAnimations_')
        #             new_path = f'animations/gSpriteAnimations_{arr[1]}'
        #             replacements.append(asset['path'] + ',' + new_path + '\n')
        #             asset['path'] = new_path
        #             asset['type'] = 'animation'
        
        # with open('/tmp/replacements.s', 'w') as file:
        #     file.writelines(replacements)
        # #assets.insert_before(asset, next_asset)
        # write_assets(assets)
        # #print(assets)
    def slot_remove_unused_assets(self) -> None:
        used_assets = set()

        used_assets.add('demo/save1')
        used_assets.add('demo/save2')
        used_assets.add('demo/save3')

        # Search all includes in data&asm files
        for folder in ['data', 'asm']:
            for root, dirs, files in os.walk(os.path.join(get_repo_location(), folder)):
                for file in files:
                    if file.endswith('.4bpp') or file.endswith('.lz'):
                        continue
                    with open(os.path.join(root, file), 'r') as f:
                        data = f.read()
                        for match in re.findall(r'\.inc(bin|lude) \"(?P<file>.*)\"', data):
                            asset = match[1][0:match[1].rindex('.')]
                            used_assets.add(asset)

        configs = get_all_asset_configs()
        for config in configs:
            assets = read_assets(config)

            print(len(used_assets), len(assets.assets))

            for i in reversed(range(0, len(assets.assets))):
                asset = assets.assets[i]
                if 'path' in asset:
                    path = asset['path'][0:asset['path'].rindex('.')]
                    if not path in used_assets:
                        del assets.assets[i]
                elif 'offsets' in asset:
                    if 'offsets' in assets.assets[i+1]:
                        # Deduplicate offsets
                        for variant in asset['offsets']:
                            if not variant in assets.assets[i+1]['offsets']:
                                assets.assets[i+1]['offsets'][variant] = asset['offsets'][variant]
                        del assets.assets[i]
            print(len(used_assets), len(assets.assets))

            write_assets(config, assets)







### Creating asset lists

    def slot_create_asset_lists(self) -> None:
        if not hasattr(self, 'all_assets'):
            self.all_assets: dict[str, list[Asset]] = {}
        
        self.extract_gfx_groups()
        self.extract_figurine_data()
        self.extract_sprites()
        self.extract_frame_obj_lists()
        self.extract_extra_frame_offsets()

        # print gfx asset
        self.print_assets_list(self.assets_symbol, self.gfx_assets)
        self.assets = self.gfx_assets

        # TODO fetch palettes from this?
        # -> not needed as those refer to palette groups which already are extracted?
        #self.extract_area_table()

        # Sort the assets and remove duplicates
        # Always the last duplicate will remain in the array
        assets = {}
        for asset in self.assets:
            assets[asset.offset] = asset

        asset_list = []
        last_used_offset = 0
        empty_index = 0
        for key in sorted(assets.keys()):
            asset = assets[key]


            # Handle known asset types
            if asset.type == 'tileset_gfx':
                asset.type = 'tileset'
                if asset.compressed:
                    asset.path = 'tilesets/' + asset.name + '.4bpp.lz'
                else:
                    asset.path = 'tilesets/' + asset.name + '.4bpp'
            elif asset.type == 'gfx':
                if asset.compressed:
                    asset.path = 'gfx/' + asset.name + '.4bpp.lz'
                else:
                    asset.path = 'gfx/' + asset.name + '.4bpp'
            elif asset.type == 'palette':
                asset.path = 'palettes/' + asset.name + '.gbapal'
            else:
                asset.path = 'assets/' + asset.name + '.bin'




            if asset.offset > last_used_offset:
                # Insert assets for the empty space
                size = asset.offset - last_used_offset
                if size < 4:
                    # TODO make sure there are actually 0s
                    asset_list.append(Asset(f'align', 'align', last_used_offset, size, False))
                else:
                    unk_asset = Asset(f'unknown_{empty_index}', 'unknown', last_used_offset, size, False)
                    unk_asset.path = f'assets/unknown_{empty_index}.bin'
                    asset_list.append(unk_asset)
                    empty_index += 1
            # TODO adapt overlapping
            last_used_offset = last_used_offset = asset.offset+asset.size
            asset_list.append(asset)
        self.all_assets[self.current_controller.rom_variant] = asset_list

        missing = []
        for variant in CUSTOM_ROM_VARIANTS:
            if variant not in self.all_assets:
                missing.append(variant)

        if True:
        #if len(missing) == 0:
            if self.api.show_question(self.name, 'Collected assets for all variants. Calculate asset list?'):
                self.calculate_asset_list()
        else:
            self.api.show_message(self.name, f'Collected assets for {self.current_controller.rom_variant}. Still missing for {", ".join(missing)}.')

    def calculate_asset_list(self):

        variant_names = {
            RomVariant.CUSTOM: 'USA',
            RomVariant.CUSTOM_EU: 'EU',
            RomVariant.CUSTOM_JP: 'JP',
            RomVariant.CUSTOM_DEMO_USA: 'DEMO_USA',
            RomVariant.CUSTOM_DEMO_JP: 'DEMO_JP',
        }

        # usa_start_offset = 0x324AE4
        # start_offsets = {
        #     RomVariant.CUSTOM: 0x324AE4,
        #     RomVariant.CUSTOM_EU: 0x323FEC,
        #     RomVariant.CUSTOM_JP: 0x324710,
        #     RomVariant.CUSTOM_DEMO_USA: 0x325514,
        #     RomVariant.CUSTOM_DEMO_JP: 0x324708
        # }

        usa_start_offset = 0x5A2E80
        start_offsets = {
            RomVariant.CUSTOM: 0x5A2E80,
            RomVariant.CUSTOM_EU: 0x5A23D0,
            RomVariant.CUSTOM_JP: 0x5A2B20,
            RomVariant.CUSTOM_DEMO_USA: 0x5A38B0,
            RomVariant.CUSTOM_DEMO_JP: 0x5A2B18
        }

        # Only calculate the asset lists we actually got
        variants = []
        for key in self.all_assets:
            variants.append(key)

        offsets = {}
        indices = {}
        for variant in variants:
            offsets[variant] = 0
            indices[variant] = 0


        assets = []

        while indices[variants[0]] < len(self.all_assets[variants[0]]):
            current_asset = {}
            name = None
            for variant in variants:
                asset = self.all_assets[variant][indices[variant]]
                current_asset[variant] = asset
                if name is None:
                    name = asset.name
                else:
                    assert(name == asset.name)
                    # TODO somehow handle new or missing files

            if asset.type == 'align':
                for variant in variants:
                    indices[variant] += 1
                continue

            print(name)
            # Determine the sizes
            sizes = {}
            for variant in variants:
                asset = current_asset[variant]
                if not asset.size in sizes:
                    sizes[asset.size] = []
                sizes[asset.size].append(variant)

            # Check offsets
            changed_offsets = {}
            for variant in variants:
                if variant == RomVariant.CUSTOM:
                    continue
                offset = current_asset[variant].offset - current_asset[RomVariant.CUSTOM].offset + start_offsets[variant] - usa_start_offset
                if offset != offsets[variant]:
                    offsets[variant] = offset
                    changed_offsets[variant_names[variant]] = offset
                    #print(f'Wrong offset: {offset} {offsets[variant]}')
                    #input()

            if len(changed_offsets.keys()) != 0:
                assets.append({'offsets': changed_offsets})


            print('Sizes: ' + (', '.join(map(lambda x:str(x), sizes.keys()))))

            if len(sizes.keys()) == 1:
                # asset = self.all_assets[variants[0]][indices[variants[0]]]
                asset = self.all_assets[RomVariant.CUSTOM][indices[RomVariant.CUSTOM]]
                # Only one entry
                assets.append({
                    'path': asset.path,
                    'start': usa_start_offset + asset.offset,
                    'size': asset.size,
                    'type': asset.type,
                })
            else:
                for size in sizes:
                    variant = sizes[size][0]
                    asset = self.all_assets[variant][indices[variant]]
                    assets.append({
                        'path': asset.path,
                        'variants': list(map(lambda x: variant_names[x], sizes[size])),
                        'start': start_offsets[variant] + asset.offset - offsets[variant], # TODO need to care for other offsets here?
                        'size': asset.size,
                        'type': asset.type,
                    })
                    print(assets[-1])

                # May need to add new offsets
                # asset = self.all_assets[RomVariant.CUSTOM][indices[RomVariant.CUSTOM]]
                # usa_addr = asset.offset + asset.size
                # changed_offsets = {}
                # for variant in variants:
                #     if variant == RomVariant.CUSTOM:
                #         continue
                #     asset = self.all_assets[variant][indices[variant]]
                #     offset = asset.offset + asset.size - usa_addr + start_offsets[variant] - usa_start_offset
                #     if offset != offsets[variant]:
                #         offsets[variant] = offset
                #         changed_offsets[variant_names[variant]] = offset
                # if len(changed_offsets.keys()) != 0:
                #     assets.append({'offsets': changed_offsets})
                #input()


            for variant in variants:
                indices[variant] += 1


        print(json.dumps(assets, indent=2))

        with open('/tmp/assets.json', 'w') as file:
            json.dump(assets, file, indent=2)
        with open('/tmp/assets.s', 'w') as file:
            variant = variants[0]
            for asset in self.all_assets[variant]:
                if asset.type == 'align':
                    file.write('\t.align 2\n')
                else:
                    file.write(f'{asset.name}::\n')
                    file.write(f'\t.incbin "{asset.path}"\n')
    """

            = 0
            previous_asset = None

            # TMP fix sizes of fixed_gfx_assets
            for i in range(len(assets)):
                asset = assets[i]
                if asset.offset < last_used_offset:
                    if asset.offset == assets[i-1].offset and asset.size == assets[i-1].size:
                        pass
                    else:
                        assets[i-1].type += '_size_changed_from_' + hex(assets[i-1].size)
                        assets[i-1].size = asset.offset-assets[i-1].offset
                        print('Adapted offset of ' + assets[i-1].name)
                last_used_offset = asset.offset+asset.size
            last_used_offset = 0
            align_bytes = 0
            empty_bytes = 0
    """


    def get_reader_for_symbol(self, symbol:Symbol) -> Optional[Reader]:
        data = self.current_controller.rom.get_bytes(symbol.address, symbol.address+symbol.length)
        return Reader(data, self.current_controller.symbols)


####################################### SPRITES


    def iterate_all_sprite_data_a(self, path: str, symbol: Symbol) -> None:
        reader = self.get_reader_for_symbol(symbol)

        replacements = []

        lines = []
        i = 0

        self.continue_extract = True
        while reader.cursor < symbol.length:

            ### SpriteDataA
            bitfield = reader.read_u16()
            object_palette_id = reader.read_u16()
            if bitfield == 0xffff:
                sprite_data_ptr = self.read_symbol(reader)
                # This sprite consists of multiple forms
                self.iterate_all_sprite_data_a(f'{path}_{i}_form', sprite_data_ptr)
            else:
                sprite_data_ptr = reader.read_u32()
            sprite_index = reader.read_u16()
            unk = reader.read_u16()
            another_pointer = reader.read_u32()

            if bitfield != 0xffff:
                print(f'{path}_{i}')

                gfx_type = (bitfield & 0xC000) >> 14
                self.used_sprites.add(sprite_index)

                if sprite_index < 323:
                    # Now go through their animations
                    reader2 = self.get_reader_for_symbol(self.current_controller.symbols.find_symbol_by_name('gSpritePtrs'))
                    reader2.cursor = sprite_index * 16
                    animation_ptr = self.read_symbol(reader2)
                    print(animation_ptr)
                    frame_gfx_data_list_ptr = self.read_symbol(reader2)
                    gfx_pointer = self.read_symbol(reader2)

                    gfx_base = ''
                    if gfx_type == 0:
                        # Fixed
                        fixed_gfx_index = bitfield
                        gfx_base = f'gFixedGfx_{fixed_gfx_index}'
                    elif gfx_type == 1:
                        # Swap
                        swap_gfx_slots_needed = (bitfield & 0x0FF0) >> 4
                        assert(gfx_pointer is not None)
                        gfx_base = gfx_pointer.name
                    elif gfx_type == 2:
                        # Common
                        common_gfx_tile_index = bitfield & 0x03FF
                        gfx_base = f'gGfx_23 + {common_gfx_tile_index*0x20}'
                    else:
                        assert(False)

                    self.current_frames = None
                    if frame_gfx_data_list_ptr:
                        self.iterate_all_frames(f'{path}_{i}_frame', frame_gfx_data_list_ptr)
                        print(f'got frame data {len(self.current_frames)}')
                    if animation_ptr:
                        self.iterate_all_animations(f'{path}_{i}_animation', sprite_index, animation_ptr, gfx_type, gfx_base)

            if not self.continue_extract:
                break
            i += 1

    def iterate_all_frames(self, path: str, symbol: Symbol) -> None:
        reader = self.get_reader_for_symbol(symbol)
        i = 0
        self.current_frames = []
        while reader.cursor < symbol.length:
            num_gfx_tiles = reader.read_u8()
            unk = reader.read_u8()
            first_gfx_tile_index = reader.read_u16()
            self.current_frames.append((first_gfx_tile_index, num_gfx_tiles))
            i += 1

    def iterate_all_animations(self, path: str, sprite_index: int, symbol: Symbol, gfx_type: int, gfx_base: str) -> None:
        reader = self.get_reader_for_symbol(symbol)

        i = 0
        while reader.cursor < symbol.length:
            animation_ptr = self.read_symbol(reader)
            if animation_ptr:
                print(f'{path}_{i}')
                self.iterate_all_animation_frames(f'{path}_{i}_frame', sprite_index, animation_ptr, gfx_type, gfx_base)
            i += 1

    def iterate_all_animation_frames(self, path: str, sprite_index: int, symbol: Symbol, gfx_type: int, gfx_base: str) -> None:
        reader = self.get_reader_for_symbol(symbol)
        lines = []
        end_of_animation = False
        i = 0
        while not end_of_animation and reader.cursor+3 < symbol.length:
            frame_index = reader.read_u8()
            keyframe_duration = reader.read_u8()
            bitfield = reader.read_u8()
            bitfield2 = reader.read_u8()

            end_of_animation = bitfield2 & 0x80 != 0
            # print(frame_index, keyframe_duration, bitfield, bitfield2)
            if frame_index != 255:
                self.get_obj(f'{path}_{i}_obj', sprite_index, frame_index, gfx_type, gfx_base)
            else:
                # TODO what is displayed for this frame index?
                print('Invalid frame index')
            #print(f'{path}_{i}')
            i += 1

        # if not end_of_animation:
        #     lines.append('@ TODO why no terminator?\n')
        while reader.cursor < symbol.length:
            keyframe_count = reader.read_u8()
            # lines.append(f'\t.byte {keyframe_count} @ keyframe count\n')
        return lines

    def get_obj(self, path: str, sprite_index: int, frame_index: int, gfx_type: int, gfx_base: str) -> None:
        symbol = self.current_controller.symbols.find_symbol_by_name('gFrameObjLists')
        addr1 = symbol.address + sprite_index * 4
        data1 = self.current_controller.rom.get_bytes(addr1, addr1+4)
        reader1 = Reader(data1, self.current_controller.symbols)
        offset1 = reader1.read_u32()
        addr2 = symbol.address + offset1 + frame_index * 4
        data2 = self.current_controller.rom.get_bytes(addr2, addr2+4)
        reader2 = Reader(data2, self.current_controller.symbols)
        offset2 = reader2.read_u32()
        addr3 = symbol.address + offset2
        data3 = self.current_controller.rom.get_bytes(addr3, addr3 + 10000) # TODO maybe calculate correct length by number of objects?
        reader = Reader(data3, self.current_controller.symbols)
        num_objects = reader.read_u8()
        if num_objects > 200:
            raise Exception(f'num_objects {num_objects} too big')

        for i in range(num_objects):
            x_offset = reader.read_s8()
            y_offset = reader.read_s8()
            bitfield = reader.read_u8()
            bitfield2 = reader.read_u16()
            # bitfield
            override_entity_palette_index = (bitfield & 0x01) != 0
            # Bit 02 seems unused.
            h_flip = (bitfield & 0x04) != 0
            v_flip = (bitfield & 0x08) != 0
            size = (bitfield & 0x30) >> 4
            shape = (bitfield & 0xC0) >> 6

            # bitfield2
            first_gfx_tile_offset = bitfield2 & 0x03FF
            priority = (bitfield2 & 0x0C00) >> 10
            palette_index = (bitfield2 & 0xF000) >> 12

            (obj_width, obj_height) = OBJ_SIZES[shape][size]
            
            num_gfx_tiles_needed = (obj_width//8) * (obj_height//8)

            if gfx_type == 1:
                # Swap gfx
                print(frame_index)
                if frame_index >= len(self.current_frames):
                    print(f'ERROR: frame_index too big {frame_index} , {len(self.current_frames)}')
                    return
                (first_gfx_tile_index, num_gfx_tiles) = self.current_frames[frame_index]
                first_gfx_tile_offset += first_gfx_tile_index
                #self.continue_extract = False


            print(f'{path}_{i} {gfx_base} + {hex(first_gfx_tile_offset*0x20)} {num_gfx_tiles_needed*0x20}')
            self.add_section(gfx_base, first_gfx_tile_offset*0x20, num_gfx_tiles_needed*0x20, f'{path}_{i}')
            # print(x_offset, y_offset, bitfield, bitfield2)
            # print(override_entity_palette_index, h_flip, v_flip, size, shape)
            # print(first_gfx_tile_offset, priority, palette_index)

    def iterate_all_sprite_data_b(self, path: str, symbol: Symbol) -> None:
        reader = self.get_reader_for_symbol(symbol)

        replacements = []

        lines = []
        i = 0
        print(symbol)
        self.continue_extract = True
        while reader.cursor < symbol.length:
            bitfield = reader.read_u8()
            type = bitfield & 0x03
            unk = reader.read_u8()
            bitfield2 = reader.read_u16()
            if type == 2:
                sprite_data_ptr = self.read_symbol(reader)
                self.iterate_all_sprite_data_b(f'{path}_{i}_form', sprite_data_ptr)
                i += 1
                continue
            else:
                # sprite_data_ptr = reader.read_u32()
                bitfield3 = reader.read_u16()
                bitfield4 = reader.read_u16()

                sprite_index = bitfield4 & 0x3ff
                gfx_type = (bitfield2 & 0x0C00) >> 10

                print(sprite_index)
                self.used_sprites.add(sprite_index)

                if sprite_index < 322: # TODO the few remaining at gSpriteAnimations_322
                    # Now go through their animations
                    reader2 = self.get_reader_for_symbol(self.current_controller.symbols.find_symbol_by_name('gSpritePtrs'))
                    reader2.cursor = sprite_index * 16
                    animation_ptr = self.read_symbol(reader2)
                    frame_gfx_data_list_ptr = self.read_symbol(reader2)
                    gfx_pointer = self.read_symbol(reader2)
                    print(animation_ptr, frame_gfx_data_list_ptr, gfx_pointer)

                    print(gfx_type)
                    gfx_base = ''
                    if gfx_type == 0:
                        # Fixed
                        fixed_gfx_index = bitfield2
                        gfx_base = f'gFixedGfx_{fixed_gfx_index}'
                    elif gfx_type == 1:
                        # Swap
                        swap_gfx_slots_needed = (bitfield2 & 0x0FF0) >> 4
                        if gfx_pointer is None:
                            print('ERROR: missing gfx_pointer for swap gfx')
                            i+=1
                            continue
                        assert(gfx_pointer is not None)
                        gfx_base = gfx_pointer.name
                    elif gfx_type == 2:
                        # Common
                        common_gfx_tile_index = bitfield2 & 0x03FF
                        gfx_base = f'gGfx_23 + {common_gfx_tile_index*0x20}'
                    else:
                        assert(False)

                    self.current_frames = None
                    if frame_gfx_data_list_ptr:
                        self.iterate_all_frames(f'{path}_{i}_frame', frame_gfx_data_list_ptr)
                        print(f'got frame data {len(self.current_frames)}')
                    if animation_ptr:
                        self.iterate_all_animations(f'{path}_{i}_animation', sprite_index, animation_ptr, gfx_type, gfx_base)

            if not self.continue_extract:
                break

            i += 1

    def iterate_all_sprite_data_c(self, path: str, symbol: Symbol) -> None:
        reader = self.get_reader_for_symbol(symbol)

        i = 0
        while reader.cursor < symbol.length:
            bitfield = reader.read_u8()
            unk = reader.read_u32()
            sprite_index = reader.read_u8()
            gfx_load_bitfield = reader.read_u16()
            if bitfield == 0xff:
                # MULTIPLE FORMS TODO
                continue
            self.used_sprites.add(sprite_index)
            i += 1

    def add_section(self, base: str, start: int, size: int, path: str) -> None:
        if not base in self.sections:
            self.sections[base] = []
        self.sections[base].append((start, size, path))

    def slot_sprite_test(self) -> None:
        # Iterate over all entities to see how to split up sprite data

        self.sections = {}
        self.used_sprites = set()

        symbol = self.current_controller.symbols.find_symbol_by_name('gEnemyDefinitions')
        self.iterate_all_sprite_data_a('enemy', symbol)

        symbol = self.current_controller.symbols.find_symbol_by_name('gProjectileDefinitions')
        self.iterate_all_sprite_data_a('projectile', symbol)
        symbol = self.current_controller.symbols.find_symbol_by_name('gObjectDefinitions')
        self.iterate_all_sprite_data_b('object', symbol)
        symbol = self.current_controller.symbols.find_symbol_by_name('gNPCDefinitions')
        self.iterate_all_sprite_data_b('npc', symbol)
        # symbol = self.current_controller.symbols.find_symbol_by_name('gPlayerItemDefinitions')
        # self.iterate_all_sprite_data_c('playerItem', symbol)

        for key in self.sections:
            self.sections[key].sort(key = lambda x:x[0])

        json.dump(self.sections, open('/tmp/sections.json', 'w'), indent=2)


        with open('/tmp/used_sprites.txt', 'w') as file:
            for sprite in self.used_sprites:
                file.write(f'{sprite}\n')
        print('End of sprite test')


####################################### END OF SPRITES


    def slot_parse_structs(self) -> None:
        generate_struct_definitions()
        # Reload structs.json
        load_json_files()
        print('ok')

    def slot_tmp2(self) -> None:
        lines = QApplication.clipboard().text().split('\n')
        out_lines = []
        for line in lines:
            if '{' in line and '}' in line:
                arr = line.split(',')
                print(len(arr))
                '''
                    u8 type;
                    u8 unk;
                    u16 bitfield;
                    union {
                        struct {
                            u16 paletteIndex;
                            u16 spriteIndex;
                '''
                '''
                typedef struct ObjectDefinition {
                    struct {
                        u8 type : 2;
                        u8 flags : 2;
                        u8 unk : 4;
                        u8 hitbox;
                        u16 gfx : 10;
                        u16 gfx_type : 2;
                        u16 unk2 : 4;
                    } PACKED bitfield;
                    union {
                        struct {
                            u16 paletteIndex : 10;
                            u16 unk : 2;
                            u16 shadow : 2;
                            u16 unk2 : 2;
                            u16 spriteIndex : 10;
                            u16 spritePriority : 3;
                            u16 draw : 3;
                        } PACKED sprite;
                        const struct ObjectDefinition* definition;
                    } data;
                } ObjectDefinition;
                '''

                if (len(arr) == 6):
                    print(arr)
                    print(arr[3])

                    _type = int(arr[0].replace('{', ''))
                    _unk = int(arr[1])
                    _bitfield = int(arr[2])
                    _paletteIndex = int(arr[3].replace('{', ''))
                    _spriteIndex = arr[4].replace('}', '').strip()


                    type = _type & 3
                    flags = (_type >> 2) & 3
                    unk = (_type >> 4) & 0xf
                    hitbox = _unk
                    gfx = _bitfield & 0x3ff
                    gfx_type = (_bitfield >> 10) & 3
                    unk2 = (_bitfield >> 12) & 0xf
                    paletteIndex = _paletteIndex & 0x3ff
                    unk3 = (_paletteIndex >> 10) & 3
                    shadow = (_paletteIndex >> 12) & 3
                    unk4 = (_paletteIndex >> 14) & 3
                    if _spriteIndex.isnumeric():
                        _spriteIndex = int(_spriteIndex)
                        spriteIndex = _spriteIndex & 0x3ff
                        spritePriority = (_spriteIndex >> 10) & 7
                        draw = (_spriteIndex >> 13) & 7
                    else:
                        spriteIndex = _spriteIndex
                        spritePriority = 0
                        draw = 0

                    arr[0] = f'{{ {{ {type}, {flags}, {unk}'
                    arr[1] = f' {hitbox}'
                    arr[2] = f' {gfx}, {gfx_type}, {unk2} }}'
                    arr[3] = f' {{ {paletteIndex}, {unk3}, {shadow}, {unk4}'
                    arr[4] = f' {spriteIndex}, {spritePriority}, {draw} }} }}'


                    modified = ','.join(arr)
                    out_lines.append(modified)
                    continue
            out_lines.append(line)
        out = '\n'.join(out_lines)
        print(out)
        QApplication.clipboard().setText(out)


# # u16 unk;
# # u32 unk2;

# # struct {
# #     u8 spritePriority : 3;
# #     u8 unknown : 1;
# #     u8 draw : 2;
# #     u8 shadow : 2;
# # } PACKED spriteFlags;
# # u8 health;
# # s16 speed;
# # u8 damageType;
# # u8 flags2;

# unk = int(arr[4])
# if '0x' in arr[5]:
#     unk2 = int(arr[5][:-2], 16)
# else:
#     unk2 = int(arr[5][:-2])
# print(unk2)

# spritePriority = unk & 7
# unknown = (unk >> 3) & 1
# draw = (unk >> 4) & 3
# shadow = (unk >> 6) & 3
# health = (unk >> 8) & 0xff
# arr[4] = f' {{ {spritePriority}, {unknown}, {draw}, {shadow} }}, {health}'

# speed = unk2 & 0xffff
# damageType = (unk2 >> 16) & 0xff
# flags2 = (unk2 >> 24) & 0xff
# arr[5] = f' {speed}, {damageType}, {flags2}' + ' }'
# modified = ','.join(arr)
# out_lines.append(modified)
# continue#


#     print(len(arr))
# if (len(arr) == 13):


#     print(arr[3])

#     if arr[3].strip().isnumeric():
#         val = int(arr[3])
#         print(val)
#         spriteIndex = val & 0xfff
#         field0x3c = val >> 12
#         print(spriteIndex, field0x3c)
#         arr[3] = f' {spriteIndex}, {field0x3c}'
#     else:
#         arr[3] = arr[3] + ', 0'


#     modified = ','.join(arr)
#     out_lines.append(modified)
#     continue