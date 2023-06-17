from dataclasses import dataclass
import os
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from PySide6.QtGui import QKeySequence
from plugins.data_extractor.assets import Assets, get_all_asset_configs, read_assets, write_assets
from plugins.data_extractor.assets_modification import Asset, insert_new_assets_to_list
from plugins.data_extractor.data_types import parse_type
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
from plugins.tilemap_viewer.asm_data_file import AsmDataFile

DEV_ACTIONS = False



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

@dataclass
class BitmaskValue:
    bits: List[str]

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
            menu.addAction('Extract current entity data (C)', self.slot_extract_current_entity_data_list)
            menu.addAction('Extract current tile entity list', self.slot_extract_current_tile_entity_list)
            menu.addAction('Extract current tile entity list (C)', self.slot_extract_current_tile_entity_list_c)
            menu.addAction('Extract current delayed entity list', self.slot_extract_current_delayed_entity_list)
            menu.addAction('Extract current exit region list', self.slot_extract_current_exit_region_list)
            menu.addAction('Extract current exit', self.slot_extract_current_exit)
            menu.addAction('Extract room property by symbol name', self.slot_extract_room_prop_by_symbol)
            menu.addAction('Create asset lists', self.slot_create_asset_lists)
            menu.addAction('tmp remove', self.slot_tmp2)
            menu.addAction('Sprite Test', self.slot_sprite_test)
            menu.addAction('Test modify asset list', self.test_asset_list_modification)
            menu.addAction('Convert area, room', self.slot_convert_area_room)
            menu.addAction('Convert local bank, flag (USA)', self.slot_convert_local_flags)
            menu.addAction('Data Stats', self.slot_data_stats)
            menu.addAction('Extract Dialog list', self.slot_extract_dialog_list)
            menu.addAction('Extract TextIndex list', self.slot_extract_text_index_list)
            menu.addAction('Extract Coords list', self.slot_extract_coords_list)
            menu.addAction('Extract Dungeon maps', self.slot_extract_dungeon_maps)
            menu.addAction('Extract Area metadata', self.slot_extract_area_metadata)
            menu.addAction('Fix Tilesets', self.slot_fix_tilesets)
#            menu.addAction('Fix paths', self.fix_paths)
            menu.addAction('Export configs', self.slot_export_configs)


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
        self.align_map_data()



        #self.extract_figurine_data()
        #self.extract_areas()
        #self.extract_area_table()
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

        group_lines: List[str] = []
        palette_pointers: Set[int] = set()
        palette_offsets: List[int] = []


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

    def extract_palette_group(self, pointer: int, symbol: Symbol) -> Tuple[List[str], List[int]]:
        lines: List[str] = []
        palette_indices: List[int] = []
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
        self.assets:List[Asset] = []
        self.extract_area_tilesets()
        assets_symbol = self.current_controller.symbols.find_symbol_by_name('gMapData')
        self.print_assets_list(assets_symbol, self.assets)

    def print_assets_list(self, assets_symbol: Symbol, assets:List[Asset]) -> None:
        # Show assets and empty space
        assets.sort(key=lambda x:x.offset)
        last_used_offset = 0
        previous_asset = None

        # TMP fix sizes of fixed_gfx_assets
        '''
        for i in range(len(assets)):
            asset = assets[i]
            if asset.offset < last_used_offset:
                if asset.offset == assets[i-1].offset and asset.size == assets[i-1].size:
                    pass
                else:
                    #assets[i-1].type += '_size_changed_from_' + hex(assets[i-1].size)
                    print(f'Adapted offset of {assets[i-1].name} from {assets[i-1].size} to {asset.offset-assets[i-1].offset}')
                    assets[i-1].size = asset.offset-assets[i-1].offset
            last_used_offset = asset.offset+asset.size
        '''
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

    def extract_entity_list(self, symbol: Symbol) -> List[str]:
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

    def slot_extract_current_entity_data_list(self) -> None:
        symbol_name = QApplication.clipboard().text()
        symbol = self.current_controller.symbols.find_symbol_by_name(symbol_name)
        #symbol = self.current_controller.symbols.get_symbol_at(self.current_controller.address_resolver.to_local(self.current_controller.cursor))
        try:
            self.extract_entity_data_list(symbol)
        except Exception:
            traceback.print_exc()
            self.api.show_error(self.name, 'Error in extracting entity data list')

    object_ids = ['GROUND_ITEM', 'DEATH_FX', 'SHOP_ITEM', 'BUTTON', 'MINISH_EMOTICON', 'POT', 'EZLO_CAP', 'PUSHED_BLOCK', 'LOCKED_DOOR', 'CAMERA_TARGET', 'OBJECT_A', 'LINK_HOLDING_ITEM', 'CHEST_SPAWNER', 'UNUSED_SKULL', 'CRACKING_GROUND', 'SPECIAL_FX', 'PLAYER_CLONE', 'BUSH', 'LIGHT_DOOR', 'RAILTRACK', 'LILYPAD_LARGE', 'CHUCHU_BOSS_PARTICLE', 'FLOATING_PLATFORM', 'GUST_JAR_PARTICLE', 'EVIL_SPIRIT', 'HOUSE_DOOR_EXT', 'RUPEE_OBJECT', 'GREAT_FAIRY', 'HOUSE_SIGN', 'OBJECT_1D', 'MOLE_MITTS_PARTICLE', 'OBJECT_1F', 'SMOKE_PARTICLE', 'DIRT_PARTICLE', 'FIGURINE_DEVICE', 'EYE_SWITCH', 'PRESSURE_PLATE', 'BIG_BARREL', 'BARREL_INSIDE', 'PUSHABLE_STATUE', 'PARALLAX_ROOM_VIEW', 'AMBIENT_CLOUDS', 'FLAME', 'LILYPAD_LARGE_FALLING', 'BEANSTALK', 'SMOKE', 'PUSHABLE_ROCK', 'HITTABLE_LEVER', 'OBJECT_30', 'FROZEN_FLOWER', 'PULLABLE_MUSHROOM', 'BOLLARD', 'WARP_POINT', 'CARLOV_OBJECT', 'BARREL_SPIDERWEB', 'OBJECT_37', 'JAR_PORTAL', 'BOSS_DOOR', 'WHITE_TRIANGLE_EFFECT', 'PORTAL_MUSHROOM_STALKS', 'PORTAL_FALLING_PLAYER', 'MINISH_PORTAL_CLOSEUP', 'MINISH_VILLAGE_OBJECT', 'GIANT_LEAF', 'FAIRY', 'LADDER_UP', 'LINK_FIRE', 'SWORD_PARTICLE', 'ROTATING_TRAPDOOR', 'LAMP_PARTICLE', 'GIANT_BOOK_LADDER', 'HEART_CONTAINER', 'FILE_SCREEN_OBJECTS', 'CHUCHU_BOSS_START_PARTICLE', 'BACKGROUND_CLOUD', 'CHUCHU_BOSS_CUTSCENE', 'PUSHABLE_FURNITURE', 'FURNITURE', 'MINISH_SIZED_ENTRANCE', 'ARCHWAY', 'GIANT_ROCK', 'GIANT_ROCK2', 'SPECIAL_CHEST', 'OBJECT_53', 'PULLABLE_LEVER', 'MINECART', 'THOUGHT_BUBBLE', 'HIDDEN_LADDER_DOWN', 'GENTARI_CURTAIN', 'LAVA_PLATFORM', 'PAPER', 'BED_COVER', 'MASK', 'HOUSE_DOOR_INT', 'WHIRLWIND', 'OBJECT_BLOCKING_STAIRS', 'SWORDSMAN_NEWSLETTER', 'EZLO_CAP_FLYING', 'GIANT_TWIG', 'OBJECT_63', 'THUNDERBOLD', 'LADDER_HOLE', 'WATER_DROP_OBJECT', 'GLEEROK_PARTICLE', 'LINK_EMPTYING_BOTTLE', 'CUTSCENE_ORCHESTRATOR', 'CUTSCENE_MISC_OBJECT', 'CRENEL_BEAN_SPROUT', 'MINECART_DOOR', 'OBJECT_ON_PILLAR', 'MINERAL_WATER_SOURCE', 'MINISH_SIZED_ARCHWAY', 'OBJECT_70', 'PUSHABLE_GRAVE', 'STONE_TABLET', 'LILYPAD_SMALL', 'MINISH_PORTAL_STONE', 'MACRO_CRYSTAL', 'MACRO_LEAF', 'BELL', 'HUGE_DECORATION', 'SHRINKING_HIEROGLYPHS', 'STEAM', 'PUSHABLE_LEVER', 'HUGE_SHOES', 'OBJECT_ON_BEETLE', 'MAZAAL_OBJECT', 'PICO_BLOOM', 'BOARD', 'BENCH', 'BIG_VORTEX', 'BIG_PUSHABLE_LEVER', 'SMALL_ICE_BLOCK', 'BIG_ICE_BLOCK', 'TRAPDOOR', 'OCTOROK_BOSS_OBJECT', 'HUGE_BOOK', 'MAZAAL_BOSS_OBJECT', 'CABIN_FURNITURE', 'DOUBLE_BOOKSHELF', 'BOOK', 'FIREPLACE', 'LIGHT_RAY', 'FROZEN_WATER_ELEMENT', 'WATER_ELEMENT', 'FROZEN_OCTOROK', 'BAKER_OVEN', 'LAMP', 'WIND_TRIBE_FLAG', 'BIRD', 'GRAVEYARD_KEY', 'KEY_STEALING_TAKKURI', 'GURUGURU_BAR', 'HIT_SWITCH', 'HUGE_ACORN', 'VAATI2_PARTICLE', 'TREE_HIDING_PORTAL', 'LIGHTABLE_SWITCH', 'TREE_THORNS', 'FAN', 'ANGRY_STATUE', 'PALACE_ARCHWAY', 'OBJECT_A2', 'CLOUD', 'MINISH_LIGHT', 'FIREBALL_CHAIN', 'SANCTUARY_STONE_TABLET', 'OBJECT_A7', 'OBJECT_A8', 'MULLDOZER_SPAWN_POINT', 'WATERFALL_OPENING', 'VAATI1_PORTAL', 'FOUR_ELEMENTS', 'ELEMENTS_BACKGROUND', 'FLOATING_BLOCK', 'VAATI3_ARM', 'METAL_DOOR', 'JAIL_BARS', 'FAN_WIND', 'KINSTONE_SPARK', 'JAPANESE_SUBTITLE', 'VAATI3_PLAYER_OBJECT', 'VAATI3_DEATH', 'WELL', 'WIND_TRIBE_TELEPORTER', 'CUCCO_MINIGAME', 'GYORG_BOSS_OBJECT', 'WINDCREST', 'LIT_AREA', 'TITLE_SCREEN_OBJECT', 'PINWHEEL', 'OBJECT_BF', 'ENEMY_ITEM', 'LINK_ANIMATION', ]
    npc_ids = ['NPC_NONE_0', 'GENTARI', 'FESTARI', 'FOREST_MINISH', 'POSTMAN', 'NPC_UNK_5', 'TPWNSPERSON', 'KID', 'GUARD', 'NPC_UNK_9', 'STAMP', 'MAID', 'MARCY', 'WHEATON', 'PITA', 'MINISH_EZLO', 'MAILBOX', 'BEEDLE', 'BROCCO', 'SITTING_PERSON', 'PINA', 'GUARD_1', 'MAID_1', 'DIN', 'NAYRU', 'FARORE', 'STURGEON', 'TINGLE_SIBLINGS', 'STOCKWELL', 'TALON', 'MALON', 'EPONA', 'MILK_CART', 'GHOST_BROTHERS', 'SMITH', 'NPC_UNK_23', 'KING_DALTUS', 'MINISTER_POTHO', 'NPC_UNK_26', 'VAATI', 'ZELDA', 'MUTOH', 'CARPENTER', 'CASTOR_WILDS_STATUE', 'CAT', 'MOUNTAIN_MINISH', 'ZELDA_FOLLOWER', 'MELARI', 'BLADE_BROTHERS', 'COW', 'GORON', 'GORON_MERCHANT', 'GORMAN', 'DOG', 'SYRUP', 'REM', 'TOWN_MINISH', 'LIBRARI', 'PERCY', 'VAATI_REBORN', 'MOBLIN_LADY', 'LIBRARIANS', 'FARMERS', 'CARLOV', 'DAMPE', 'DR_LEFT', 'KING_GUSTAF', 'GINA', 'SIMON', 'ANJU', 'MAMA', 'EMMA', 'TEACHERS', 'WIND_TRIBESPEOPLE', 'GREGAL', 'MAYOR_HAGEN', 'BIG_GORON', 'EZLO', 'NPC_UNK_4E', 'NPC_UNK_4F', 'CLOTHES_RACK', 'PICOLYTE_BOTTLE', 'SMALL_TOWN_MINISH', 'HURDY_GURDY_MAN', 'CUCCO', 'CUCCO_CHICK', 'FUSION_MENU_NPC', 'PHONOGRAPH', 'NPC_UNK_58', 'NPC_NONE_1', 'NPC_NONE_2', 'NPC_NONE_3', 'NPC_NONE_4', 'NPC_NONE_5', 'NPC_NONE_6', 'NPC_NONE_7', 'NPC_NONE_8', 'NPC_NONE_9', 'NPC_NONE_10', 'NPC_NONE_11', 'NPC_NONE_12', 'NPC_NONE_13', 'NPC_NONE_14', 'NPC_NONE_15', 'NPC_NONE_16', 'NPC_NONE_17', 'NPC_NONE_18', 'NPC_NONE_19', 'NPC_NONE_20', 'NPC_NONE_21', 'NPC_NONE_22', 'NPC_NONE_23', 'NPC_NONE_24', 'NPC_NONE_25', 'NPC_NONE_26', 'NPC_NONE_27', 'NPC_NONE_28', 'NPC_NONE_29', 'NPC_NONE_30', 'NPC_NONE_31', 'NPC_NONE_32', 'NPC_NONE_33', 'NPC_NONE_34', 'NPC_NONE_35', 'NPC_NONE_36', 'NPC_NONE_37', 'NPC_NONE_38', 'NPC_NONE_39', ]
    manager_ids = ['MANAGER_NONE', 'LIGHT_RAY_MANAGER', 'VERTICAL_MINISH_PATH_BACKGROUND_MANAGER', 'MINISH_PORTAL_MANAGER', 'DIGGING_CAVE_ENTRANCE_MANAGER', 'BRIDGE_MANAGER', 'SPECIAL_WARP_MANAGER', 'MINISH_VILLAGE_MANAGER', 'HORIZONTAL_MINISH_PATH_BACKGROUND_MANAGER', 'MINISH_RAFTERS_BACKGROUND_MANAGER', 'EZLO_HINT_MANAGER', 'FIGHT_MANAGER', 'ROLLING_BARREL_MANAGER', 'TILE_CHANGE_OBSERVE_MANAGER', 'ENTITY_SPAWN_MANAGER', 'MISC_MANAGER', 'WEATHER_CHANGE_MANAGER', 'FLAG_AND_OPERATOR_MANAGER', 'HYRULE_TOWN_TILESET_MANAGER', 'HOUSE_SIGN_MANAGER', 'STEAM_OVERLAY_MANAGER', 'TEMPLE_OF_DROPLETS_MANAGER', 'DELAYED_ENTITY_LOAD_MANAGER', 'FALLING_ITEM_MANAGER', 'CLOUD_OVERLAY_MANAGER', 'POW_BACKGROUND_MANAGER', 'HOLE_MANAGER', 'STATIC_BACKGROUND_MANAGER', 'RAINFALL_MANAGER', 'ANIMATED_BACKGROUND_MANAGER', 'REGION_TRIGGER_MANAGER', 'RAIL_INTERSECTION_MANAGER', 'MOVEABLE_OBJECT_MANAGER', 'MINISH_SIZED_ENTRANCE_MANAGER', 'LIGHT_MANAGER', 'LIGHT_LEVEL_SET_MANAGER', 'BOMBABLE_WALL_MANAGER', 'FLAME_MANAGER', 'PUSHABLE_FURNITURE_MANAGER', 'ARMOS_INTERIOR_MANAGER', 'ENEMY_INTERACTION_MANAGER', 'MANAGER_29', 'DESTRUCTIBLE_TILE_OBSERVE_MANAGER', 'ANGRY_STATUE_MANAGER', 'CLOUD_STAIRCASE_TRANSITION_MANAGER', 'WATERFALL_BOTTOM_MANAGER', 'SECRET_MANAGER', 'VAATI3_BACKGROUND_MANAGER', 'TILE_PUZZLE_MANAGER', 'GORON_MERCHANT_SHOP_MANAGER', 'VAATI_APPARATE_MANAGER', 'HYRULE_TOWN_BELL_MANAGER', 'VAATI3_INSIDE_ARM_MANAGER', 'CAMERA_TARGET_MANAGER', 'REPEATED_SOUND_MANAGER', 'VAATI3_START_MANAGER', 'FLOATING_PLATFORM_MANAGER', 'ENTER_ROOM_TEXTBOX_MANAGER', ]

    def extract_entity_data_list(self, symbol: Symbol) -> None:
        if symbol is None:
            return

        def handle_data(data_array):
            for data in data_array:
                data['xPos'] = hex(data['xPos'])
                data['yPos'] = hex(data['yPos'])
                #data['kind'] = data['kind'] % 16
                if data['kind'] == 3:
                    data['kind'] = 'ENEMY'
                elif data['kind'] == 6:
                    data['kind'] = 'OBJECT'
                    data['id'] = self.object_ids[data['id']]
                elif data['kind'] == 7:
                    data['kind'] = 'NPC'
                    data['id'] = self.npc_ids[data['id']]
                elif data['kind'] == 9:
                    data['kind'] = 'MANAGER'
                    data['id'] = self.manager_ids[data['id']]
                elif data['kind'] == 255:
                    data['kind'] = '0xff'
                else:
                    pass
                    #raise Exception(f'Unknown entity kind {data["kind"]}.')
            return data_array
        result = self.extract_data(f'const EntityData {symbol.name}[];', self.current_controller.symbols, self.current_controller.rom, handle_data)
        QApplication.clipboard().setText(result)
        print('done')

    def slot_extract_current_tile_entity_list(self) -> None:
        symbol = self.current_controller.symbols.get_symbol_at(self.current_controller.address_resolver.to_local(self.current_controller.cursor))
        try:
            self.extract_tile_entity_list(symbol)
        except Exception:
            traceback.print_exc()
            self.api.show_error(self.name, 'Error in extracting tile entity list')

    def extract_tile_entity_list(self, symbol: Symbol) -> List[str]:
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

    def slot_extract_current_tile_entity_list_c(self) -> None:
        symbol_name = QApplication.clipboard().text()
        symbol = self.current_controller.symbols.find_symbol_by_name(symbol_name)
        #symbol = self.current_controller.symbols.get_symbol_at(self.current_controller.address_resolver.to_local(self.current_controller.cursor))
        try:
            self.extract_tile_entity_list_c(symbol)
        except Exception:
            traceback.print_exc()
            self.api.show_error(self.name, 'Error in extracting tile entity list')

    tile_entity_ids = ['NONE', 'ROOM_VISIT_MARKER', 'SMALL_CHEST', 'BIG_CHEST', 'BOMBABLE_WALL', 'SIGN', 'TILE_EZLO_HINT', 'MUSIC_SETTER', 'TILE_ENTITY_8', 'DARKNESS', 'DESTRUCTIBLE_TILE', 'GRASS_DROP_CHANGER', 'LOCATION_CHANGER', 'TILE_ENTITY_D', ]
    def extract_tile_entity_list_c(self, symbol: Symbol) -> None:
        if symbol is None:
            return

        def handle_data(data_array):
            for data in data_array:
                data['type'] = self.tile_entity_ids[data['type']]
                data['tilePos'] = hex(data['tilePos'])
            return data_array
        result = self.extract_data(f'const TileEntity {symbol.name}[];', self.current_controller.symbols, self.current_controller.rom, handle_data)
        QApplication.clipboard().setText(result)
        print('done')

    def slot_extract_current_delayed_entity_list(self) -> None:
        symbol = self.current_controller.symbols.get_symbol_at(self.current_controller.address_resolver.to_local(self.current_controller.cursor))
        try:
            self.extract_delayed_entity_list(symbol)
        except Exception:
            traceback.print_exc()
            self.api.show_error(self.name, 'Error in extracting delayed entity list')

    def extract_delayed_entity_list(self, symbol: Symbol) -> List[str]:
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

    def extract_exit_region_list(self, symbol: Symbol) -> List[str]:
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

    def extract_exit(self, symbol: Symbol) -> List[str]:
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

    def extract_gfx_group(self, symbol: Symbol, group_index: int) -> List[str]:
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

    def extract_animation(self, symbol: Symbol, new_name: str) -> List[str]:
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


    def extract_data(self, code: str, symbols: SymbolList, rom: Rom, modifier = lambda x:x) -> str:
        type = parse_type(code)

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
            res = modifier(res)
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

                text = 'const ' + type.type + (' const' if type.inner_const else '') + ' ' + type.name + '[] = {'
                for i in range(symbol.address, symbol.address+symbol.length, 4):
                    pointer = rom.get_pointer(i)
                    if pointer == 0:
                        text += 'NULL, '
                    else:
                        pointer_symbol = symbols.get_symbol_at(pointer - ROM_OFFSET)
                        text += '&' + pointer_symbol.name + ', '
                text += '};'
            else:
                res = read_var(reader, type.type + '[]')
                res = modifier(res)
                text = 'const ' + type.type + ' ' + type.name + '[] = ' + self.get_struct_init(res) + ';';
        elif type.regex == 3:
            if symbol.length % 4 != 0:
                raise Exception('Incorrect data length')

            text = 'void (*const ' + type.name + '[])(' + type.params + ') = {'
            for i in range(symbol.address, symbol.address+symbol.length, 4):
                pointer = rom.get_pointer(i)
                if pointer == 0:
                    text += 'NULL, '
                else:
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
        text = ''
        try:
            # Split at ; to be able to parse multiple definition lines at once.
            for line in type_str.split(';'):
                line = line.strip()
                if line != "":
                    text += self.extract_data(line + ';', self.current_controller.symbols, self.current_controller.rom) + '\n'
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

        self.replacements = []
        self.gfx_assets = []
        # self.extract_palette_groups()
        #self.extract_fixed_type_gfx_data()
        #self.extract_extra_frame_offsets()
        #self.extract_frame_obj_lists()

        EXTRACT_DATA = False
        if EXTRACT_DATA:
            self.assets_symbol = self.current_controller.symbols.find_symbol_by_name('gGlobalGfxAndPalettes')

            # self.extract_bg_animations()
            self.extract_obj_palettes()

            # self.print_assets_list(self.assets_symbol, self.gfx_assets)
            variant_names = {
                RomVariant.CUSTOM: 'USA',
                RomVariant.CUSTOM_EU: 'EU',
                RomVariant.CUSTOM_JP: 'JP',
                RomVariant.CUSTOM_DEMO_USA: 'DEMO_USA',
                RomVariant.CUSTOM_DEMO_JP: 'DEMO_JP',
            }


            current_assets = read_assets('gfx.json')
            new_assets = insert_new_assets_to_list(current_assets, self.assets_symbol, self.gfx_assets, variant_names[self.current_controller.rom_variant])
            with open('/tmp/assets/assets.json', 'w') as file:
                json.dump(new_assets.assets, file, indent=2)
        else:

            self.assets_symbol = self.current_controller.symbols.find_symbol_by_name('gGlobalGfxAndPalettes')
            # Extract the actual definitions
            #self.extract_bg_animations_code()
            self.extract_obj_palettes_code()

        # TODO Rebuild this in a way where it reads in the existing assets list
        # then adds


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

        # animation_ptr = self.current_controller.symbols.find_symbol_by_name('gSpriteAnimation_Vaati_1')
        # self.extract_animation_list(animation_ptr)
        with open('/tmp/replacements.s', 'w') as file:
            file.writelines(self.replacements)


        print('done')

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


    ######### bg animations #########

    def extract_bg_animations(self) -> None:
        self.count = 0
        self.total_size = 0
        symbol = self.current_controller.symbols.find_symbol_by_name('gUnk_080B7278')
        reader = self.get_reader_for_symbol(symbol)
        bg_anim_count = 0
        while reader.cursor < symbol.length:
            frame_list = self.read_symbol(reader)
            self.extract_bg_frame_list(bg_anim_count, frame_list)
            bg_anim_count += 1

    def extract_bg_frame_list(self, anim_id: int, symbol: Symbol) -> None:
        reader = self.get_reader_for_symbol(symbol)
        bg_frame_count = 0
        while reader.cursor < symbol.length:
            bg_gfx = self.read_symbol(reader)
            unk4_ = reader.read_u32()
            #print(anim_id, bg_frame_count, bg_gfx)
            if bg_gfx:
                self.extract_bg_frame(anim_id, bg_frame_count, bg_gfx)
            bg_frame_count += 1

    def extract_bg_frame(self, anim_id: int, frame_id: int, symbol: Symbol) -> None:
        reader = self.get_reader_for_symbol(symbol)
        entry_count = 0
        while reader.cursor < symbol.length:
            vramOffset = reader.read_u16()
            gfxSize = reader.read_u8()
            unk_3 = reader.read_u8()
            gfxOffset = reader.read_u32()
            if (unk_3 & 16) != 0:
                #print('>>> PALETTE')
                #print(gfxOffset, gfxSize, vramOffset)
                if entry_count > 0:
                    self.gfx_assets.append(Asset(f'bgAnim_{anim_id}_{frame_id}_{entry_count}', 'palette', gfxOffset, gfxSize * 32, False))
                else:
                    self.gfx_assets.append(Asset(f'bgAnim_{anim_id}_{frame_id}', 'palette', gfxOffset, gfxSize * 32, False))
                pass
            else:
                if entry_count > 0:
                    self.gfx_assets.append(Asset(f'bgAnim_{anim_id}_{frame_id}_{entry_count}', 'gfx', gfxOffset, gfxSize * 32, False))
                else:
                    self.gfx_assets.append(Asset(f'bgAnim_{anim_id}_{frame_id}', 'gfx', gfxOffset, gfxSize * 32, False))
                pass
                # self.api.show_error('asdf', f'Unk unk_3 value: {unk_3}')
                #print(gfxOffset, gfxSize, vramOffset, unk_3)
            entry_count += 1
        self.count += 1
        self.total_size += gfxSize
        #print(self.count, self.total_size)



    def extract_bg_animations_code(self) -> None:
        self.count = 0
        self.total_size = 0
        symbol = self.current_controller.symbols.find_symbol_by_name('gUnk_080B7278')
        reader = self.get_reader_for_symbol(symbol)

        self.bg_anim_data = []

        bg_anim_count = 0
        while reader.cursor < symbol.length:
            frame_list = self.read_symbol(reader)
            self.extract_bg_frame_list_code(bg_anim_count, frame_list)
            bg_anim_count += 1

        self.bg_anim_data.sort(key=lambda x:x['symbol'].address)

        self.content = []
        prev_addr = 0
        for data in self.bg_anim_data:
            if data['symbol'].address == prev_addr:
                # Ignore duplicate symbols.
                continue
            prev_addr = data['symbol'].address
            if data['type'] == 'list':
                self.content.append(self.extract_bg_frame_list_actual(data['name'], data['symbol'])+'\n')
            elif data['type'] == 'frame':
                self.content.append(self.extract_bg_frame_actual(data['name'], data['symbol'])+'\n')
            else:
                raise Exception(f'Unknown type {data["type"]}')
        with open('/tmp/assets/anims.c', 'w') as file:
            file.writelines(self.content)

    def extract_bg_frame_list_code(self, anim_id: int, symbol: Symbol) -> None:
        self.bg_anim_data.append({'symbol': symbol, 'name': f'bgAnim_{anim_id}', 'type': 'list'})
        reader = self.get_reader_for_symbol(symbol)
        bg_frame_count = 0
        while reader.cursor < symbol.length:
            bg_gfx = self.read_symbol(reader)
            unk4_ = reader.read_u32()
            #print(anim_id, bg_frame_count, bg_gfx)
            if bg_gfx:
                self.extract_bg_frame_code(anim_id, bg_frame_count, bg_gfx)
            bg_frame_count += 1

    def extract_bg_frame_code(self, anim_id: int, frame_id: int, symbol: Symbol) -> None:
        self.bg_anim_data.append({'symbol': symbol, 'name': f'bgAnimFrame_{anim_id}_{frame_id}', 'type': 'frame'})
    
    def extract_bg_frame_list_actual(self, name: str, symbol: Symbol) -> str:
        def handle_data(data_array):
            for data in data_array:
                if data['gfx'].startswith('&'):
                    data['gfx'] = data['gfx'][1:]
            return data_array
        return self.extract_data(f'const BgAnimationFrame {symbol.name}[];', self.current_controller.symbols, self.current_controller.rom, handle_data)

    def extract_bg_frame_actual(self, name: str, symbol: Symbol) -> str:
        def handle_data(data_array):
            for data in data_array:
                data['vramOffset'] = hex(data['vramOffset'])
                addr = self.assets_symbol.address + data['gfxOffset']
                symbol = self.current_controller.symbols.get_symbol_at(addr)

                if data['unk_3'] == 16:
                    data['unk_3'] = 'BG_ANIM_PALETTE'
                elif data['unk_3'] == 128:
                    data['unk_3'] = 'BG_ANIM_MULTIPLE'
                elif data['unk_3'] == 144:
                    data['unk_3'] = 'BG_ANIM_PALETTE | BG_ANIM_MULTIPLE'
                elif data['unk_3'] == 0:
                    data['unk_3'] = 'BG_ANIM_DEFAULT'
                else:
                    raise Exception(f'Unknown unk_3 {data["unk_3"]}')
                #print(data)
                data['gfxOffset'] = 'offset_' + symbol.name
            return data_array
        result = self.extract_data(f'const BgAnimationGfx {symbol.name}[];', self.current_controller.symbols, self.current_controller.rom, handle_data)
        return result

    ######### bg animations end #########


    def extract_obj_palettes(self) -> None:
        symbol = self.current_controller.symbols.find_symbol_by_name('gUnk_08133368')
        reader = self.get_reader_for_symbol(symbol)
        missing = []
        while reader.cursor < symbol.length:
            data = reader.read_u32()
            offset = data & 0xffffff
            count = (data >> 0x18) & 0xf
            address = self.assets_symbol.address + offset
            pal_symbol = self.current_controller.symbols.get_symbol_at(address)
            for i in range(0, count):
                missing.append(offset//32 + i)
            # if pal_symbol.address != address:
            #     missing.append(offset//32)
            #     print(f'missing {offset//32} at {address}')
            byte3 = data & 0xff000000
            #print(pal_symbol.address - address, pal_symbol.name)
            #print(offset, count)
            # if byte3 != 0 and byte3 >> 0x18 != count:
            #     print(hex(byte3 >> 0x18))
        missing.sort()
        print(missing)
        print('done')

        for i in missing:
            self.gfx_assets.append(Asset(f'gPalette_{i}', 'palette', i*32, 32, False))

    def extract_obj_palettes_code(self) -> None:
        symbol = self.current_controller.symbols.find_symbol_by_name('gUnk_08133368')
        reader = self.get_reader_for_symbol(symbol)
        lines = []
        while reader.cursor < symbol.length:
            data = reader.read_u32()
            offset = data & 0xffffff
            count = (data >> 0x18) & 0xf
            address = self.assets_symbol.address + offset
            pal_symbol = self.current_controller.symbols.get_symbol_at(address)
            if pal_symbol.address != address:
                raise Exception(f'missing {offset//32} at {address}')
            lines.append(f'offset_{pal_symbol.name} | {count} << 0x18,')
        QApplication.clipboard().setText('\n'.join(lines))
    #######

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
                elif isinstance(obj[key], BitmaskValue):
                    if len(obj[key].bits) == 0:
                        text += separator + '0'
                    else:
                        text += separator + '|'.join(obj[key].bits)
                else:
                    if type(obj[key]) != int or obj[key] < 0x1000000:
                        text += separator + str(obj[key])
                    else:
                        text += separator + hex(obj[key])
                separator = ', '
            text += ' }'
        return text


    def test_asset_list_modification(self) -> None:
        # Add figurine layers
        assets = read_assets('gfx.json')
        for asset in assets.assets:
            if 'type' in asset:
                if asset['type'] == 'gfx':
                    match = re.match(r'gfx/figurines/gFigurineGfx(\w*).4bpp', asset['path'])
                    if match:
                        with open(f'/tmp/fig{match.group(1)}.json', 'r') as file:
                            asset['layers'] = json.load(file)
                            asset['type'] = 'metasprite'


        write_assets('gfx.json', assets)

        # # List palettes
        # assets = read_assets('gfx.json')
        # palettes = []
        # for asset in assets.assets:
        #     if 'type' in asset:
        #         if asset['type'] == 'palette':
        #             match = re.match(r'palettes/(\w*).gbapal', asset['path'])
        #             if match:
        #                 palettes.append(match.group(1))
        # with open('/tmp/palettes.txt', 'w') as file:
        #     file.write('[')
        #     for palette in palettes:
        #         file.write('"'+palette+'", ')
        #     file.write(']')


        ## Split up palettes
        # assets = read_assets('gfx.json')
        # out_assets = []
        # includes = []

        # in_palettes = True
        # last_palette_id = 0
        # for asset in assets.assets:
        #     if not in_palettes:
        #         out_assets.append(asset)
        #         continue
        #     if 'path' in asset:

        #         if asset['path'] == 'assets/gfx_unknown_16.bin':
        #             in_palettes = False
        #             out_assets.append(asset)
        #             continue

        #         if asset['size'] != 32:
        #             includes.append(f'> {asset["path"]}"')
        #             print(f'got {asset["size"]//32} palettes')
        #             if asset['type'] == 'palette':
        #                 print(asset['path'])
        #                 for i in range(0, asset["size"]//32):
        #                     path = asset['path'].replace('.gbapal', f'_{i}.gbapal')
        #                     out_assets.append({
        #                         'path': path,
        #                         'start': asset['start'] + i*32,
        #                         'size': 32,
        #                         'type': 'palette'
        #                     })
        #                     includes.append(f'\t.incbin "{path}"')
        #             else:
        #                 for i in range(0, asset["size"]//32):
        #                     last_palette_id += 1
        #                     # print(f'palettes/gPalette_{last_palette_id}.gbapal')
        #                     path = f'palettes/gPalette_{last_palette_id}.gbapal'
        #                     out_assets.append({
        #                         'path': path,
        #                         'start': asset['start'] + i*32,
        #                         'size': 32,
        #                         'type': 'palette'
        #                     })
        #                     includes.append(f'\t.incbin "{path}"')
        #             print(asset['type'])
        #             if asset['size'] % 32 != 0:
        #                 print(asset['path'])
        #                 print(asset['size'])

        #             continue

        #         if asset['type'] == 'palette':
        #             match = re.match(r'palettes/gPalette_(\w*).gbapal', asset['path'])
        #             if match:
        #                 last_palette_id = int(match.group(1))

        #     out_assets.append(asset)
        # write_assets('gfx_mod.json', Assets(out_assets))

        # with open('/tmp/includes.txt', 'w') as file:
        #     for include in includes:
        #         file.write(include+'\n')

        ## Align map assets
        # assets = read_assets('map.json')
        # for asset in assets.assets:
        #     if 'path' in asset:
        #         start = asset['start']
        #         if start % 4 != 0:
        #             diff = 4 - start % 4;
        #             asset['start'] = start + diff;
        #             asset['size'] -= diff;

        # write_assets('map.json', assets)

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
            self.all_assets: Dict[str, List[Asset]] = {}

        self.assets_symbol = self.current_controller.symbols.find_symbol_by_name('gGlobalGfxAndPalettes')
        self.gfx_assets = []

        # self.extract_gfx_groups()
        # self.extract_figurine_data()
        # self.extract_sprites()
        # self.extract_frame_obj_lists()
        # self.extract_extra_frame_offsets()
        self.extract_bg_animations()

        # print gfx asset
        self.print_assets_list(self.assets_symbol, self.gfx_assets)
        self.assets = self.gfx_assets

        # TODO fetch palettes from this?
        # -> not needed as those refer to palette groups which already are extracted?
        #self.extract_area_table()


        # Load already existing assets for this variant.
        # Ignore unknown spaces.
        old_assets = read_assets('gfx.json')


        variant_names = {
            RomVariant.CUSTOM: 'USA',
            RomVariant.CUSTOM_EU: 'EU',
            RomVariant.CUSTOM_JP: 'JP',
            RomVariant.CUSTOM_DEMO_USA: 'DEMO_USA',
            RomVariant.CUSTOM_DEMO_JP: 'DEMO_JP',
        }

        start_offsets = {
            RomVariant.CUSTOM: 0x5A2E80,
            RomVariant.CUSTOM_EU: 0x5A23D0,
            RomVariant.CUSTOM_JP: 0x5A2B20,
            RomVariant.CUSTOM_DEMO_USA: 0x5A38B0,
            RomVariant.CUSTOM_DEMO_JP: 0x5A2B18
        }


        offsets = {}
        for variant in CUSTOM_ROM_VARIANTS:
            offsets[variant_names[variant]] = 0
        for asset in old_assets.assets:
            if 'offsets' in asset:
                for key in asset['offsets']:
                    offsets[key] = asset['offsets'][key]
            if 'path' in asset:
                if asset['path'].startswith('assets/gfx_unknown'):
                    # Ignore completely unknown assets, they will be rebuilt anyways.
                    continue
                if 'variants' in asset:
                    if not variant_names[self.current_controller.rom_variant] in asset['variants']:
                        # This asset is not for the current variant.
                        continue
                self.assets.append(
                    Asset(
                        asset['path'], # TODO needed?
                        asset['type'] if 'type' in asset else 'unknown',
                        # Calculate back to offset from graphics start.
                        offsets[variant_names[self.current_controller.rom_variant]] + asset['start'] - start_offsets[self.current_controller.rom_variant],
                        asset['size'],
                        False, # TODO do we need the compressed state anywhere here?
                        existing=True,
                        path=asset['path']
                    )
                )


        # Sort the assets and remove duplicates
        # Always the last duplicate will remain in the array
        assets = {}
        for asset in self.assets:
            assets[asset.offset] = asset

        asset_list = []
        last_used_offset = 0
        empty_index = 0
        previous_asset_unknown = None
        for key in sorted(assets.keys()):
            asset = assets[key]

            # For new variants, but the path.
            if asset.path is None:
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
                    unk_asset = Asset(f'gfx_unknown_{empty_index}', 'unknown', last_used_offset, size, False)
                    unk_asset.path = f'assets/gfx_unknown_{empty_index}.bin'
                    asset_list.append(unk_asset)
                    empty_index += 1
            elif asset.offset < last_used_offset:
                print(f'Current offset: {asset.offset} last used: {last_used_offset}')
                if not previous_asset_unknown:
                    print(asset_list[-1])
                    raise Exception(f'Overlap for asset {asset.name} where previous asset is not unknown')
                new_size = asset.offset - asset_list[-1].offset
                print(f'!!!! OVERLAP: {asset.name} reduces the size of {asset_list[-1].name} from {asset_list[-1].size} to {new_size}.')
                asset_list[-1].size = new_size

            # TODO adapt overlapping
            last_used_offset = last_used_offset = asset.offset+asset.size
            previous_asset_unknown = asset.type == 'unknown'
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
                    if name != asset.name:
                        print(f'Files are not the same between the variants {name} != {asset.name}')
                        # TODO for now just assume this asset does not exist in this variant.
                        # TODO This currently assumes that USA(CUSTOM) is build first and then the asset list for EU
                        indices[variant] -= 1
                        continue

                        raise Exception(f'Files are not the same between the variants {name} != {asset.name}')
                        assert(name == asset.name)
                        # TODO somehow handle new or missing files

            if asset.type == 'align':
                for variant in variants:
                    indices[variant] += 1
                continue

            #print(name)
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


            #print('Sizes: ' + (', '.join(map(lambda x:str(x), sizes.keys()))))

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
                    #print(assets[-1])

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


        #print(json.dumps(assets, indent=2))

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



    area_ids = ['AREA_MINISH_WOODS', 'AREA_MINISH_VILLAGE', 'AREA_HYRULE_TOWN', 'AREA_HYRULE_FIELD', 'AREA_CASTOR_WILDS', 'AREA_RUINS', 'AREA_MT_CRENEL', 'AREA_CASTLE_GARDEN', 'AREA_CLOUD_TOPS', 'AREA_ROYAL_VALLEY', 'AREA_VEIL_FALLS', 'AREA_LAKE_HYLIA', 'AREA_LAKE_WOODS_CAVE', 'AREA_BEANSTALKS', 'AREA_EMPTY', 'AREA_HYRULE_DIG_CAVES', 'AREA_MELARIS_MINE', 'AREA_MINISH_PATHS', 'AREA_CRENEL_MINISH_PATHS', 'AREA_DIG_CAVES', 'AREA_CRENEL_DIG_CAVE', 'AREA_FESTIVAL_TOWN', 'AREA_VEIL_FALLS_DIG_CAVE', 'AREA_CASTOR_WILDS_DIG_CAVE', 'AREA_OUTER_FORTRESS_OF_WINDS', 'AREA_HYLIA_DIG_CAVES', 'AREA_VEIL_FALLS_TOP', 'AREA_NULL_1B', 'AREA_NULL_1C', 'AREA_NULL_1D', 'AREA_NULL_1E', 'AREA_NULL_1F', 'AREA_MINISH_HOUSE_INTERIORS', 'AREA_HOUSE_INTERIORS_1', 'AREA_HOUSE_INTERIORS_2', 'AREA_HOUSE_INTERIORS_3', 'AREA_TREE_INTERIORS', 'AREA_DOJOS', 'AREA_CRENEL_CAVES', 'AREA_MINISH_CRACKS', 'AREA_HOUSE_INTERIORS_4', 'AREA_GREAT_FAIRIES', 'AREA_CASTOR_CAVES', 'AREA_CASTOR_DARKNUT', 'AREA_ARMOS_INTERIORS', 'AREA_TOWN_MINISH_HOLES', 'AREA_MINISH_RAFTERS', 'AREA_GORON_CAVE', 'AREA_WIND_TRIBE_TOWER', 'AREA_WIND_TRIBE_TOWER_ROOF', 'AREA_CAVES', 'AREA_VEIL_FALLS_CAVES', 'AREA_ROYAL_VALLEY_GRAVES', 'AREA_MINISH_CAVES', 'AREA_CASTLE_GARDEN_MINISH_HOLES', 'AREA_37', 'AREA_EZLO_CUTSCENE', 'AREA_NULL_39', 'AREA_NULL_3A', 'AREA_NULL_3B', 'AREA_NULL_3C', 'AREA_NULL_3D', 'AREA_NULL_3E', 'AREA_NULL_3F', 'AREA_40', 'AREA_HYRULE_TOWN_UNDERGROUND', 'AREA_GARDEN_FOUNTAINS', 'AREA_HYRULE_CASTLE_CELLAR', 'AREA_SIMONS_SIMULATION', 'AREA_45', 'AREA_NULL_46', 'AREA_47', 'AREA_DEEPWOOD_SHRINE', 'AREA_DEEPWOOD_SHRINE_BOSS', 'AREA_DEEPWOOD_SHRINE_ENTRY', 'AREA_NULL_4B', 'AREA_NULL_4C', 'AREA_4D', 'AREA_NULL_4E', 'AREA_NULL_4F', 'AREA_CAVE_OF_FLAMES', 'AREA_CAVE_OF_FLAMES_BOSS', 'AREA_NULL_52', 'AREA_NULL_53', 'AREA_NULL_54', 'AREA_NULL_55', 'AREA_NULL_56', 'AREA_57', 'AREA_FORTRESS_OF_WINDS', 'AREA_FORTRESS_OF_WINDS_TOP', 'AREA_INNER_MAZAAL', 'AREA_NULL_5B', 'AREA_NULL_5C', 'AREA_NULL_5D', 'AREA_NULL_5E', 'AREA_5F', 'AREA_TEMPLE_OF_DROPLETS', 'AREA_NULL_61', 'AREA_HYRULE_TOWN_MINISH_CAVES', 'AREA_NULL_63', 'AREA_NULL_64', 'AREA_NULL_65', 'AREA_NULL_66', 'AREA_67', 'AREA_ROYAL_CRYPT', 'AREA_NULL_69', 'AREA_NULL_6A', 'AREA_NULL_6B', 'AREA_NULL_6C', 'AREA_NULL_6D', 'AREA_NULL_6E', 'AREA_6F', 'AREA_PALACE_OF_WINDS', 'AREA_PALACE_OF_WINDS_BOSS', 'AREA_NULL_72', 'AREA_NULL_73', 'AREA_NULL_74', 'AREA_NULL_75', 'AREA_NULL_76', 'AREA_77', 'AREA_SANCTUARY', 'AREA_NULL_79', 'AREA_NULL_7A', 'AREA_NULL_7B', 'AREA_NULL_7C', 'AREA_NULL_7D', 'AREA_NULL_7E', 'AREA_7F', 'AREA_HYRULE_CASTLE', 'AREA_SANCTUARY_ENTRANCE', 'AREA_NULL_82', 'AREA_NULL_83', 'AREA_NULL_84', 'AREA_NULL_85', 'AREA_NULL_86', 'AREA_87', 'AREA_DARK_HYRULE_CASTLE', 'AREA_DARK_HYRULE_CASTLE_OUTSIDE', 'AREA_VAATIS_ARMS', 'AREA_VAATI_3', 'AREA_VAATI_2', 'AREA_DARK_HYRULE_CASTLE_BRIDGE', 'AREA_NULL_8E', 'AREA_8F']
    room_ids = [
[ 'ROOM_MINISH_WOODS_MAIN' ],
[ 'ROOM_MINISH_VILLAGE_MAIN', 'ROOM_MINISH_VILLAGE_SIDE_HOUSE_AREA', 'ROOM_MINISH_VILLAGE_2', 'ROOM_MINISH_VILLAGE_3' ],
[ 'ROOM_HYRULE_TOWN_MAIN', 'ROOM_HYRULE_TOWN_1' ],
[ 'ROOM_HYRULE_FIELD_WESTERN_WOODS_SOUTH', 'ROOM_HYRULE_FIELD_SOUTH_HYRULE_FIELD', 'ROOM_HYRULE_FIELD_EASTERN_HILLLS_SOUTH', 'ROOM_HYRULE_FIELD_EASTERN_HILLLS_CENTER', 'ROOM_HYRULE_FIELD_EASTERN_HILLLS_NORTH', 'ROOM_HYRULE_FIELD_LON_LON_RANCH', 'ROOM_HYRULE_FIELD_NORTH_HYRULE_FIELD', 'ROOM_HYRULE_FIELD_TRILBY_HIGHLANDS', 'ROOM_HYRULE_FIELD_WESTERN_WOODS_NORTH', 'ROOM_HYRULE_FIELD_WESTERN_WOODS_CENTER' ],
[ 'ROOM_CASTOR_WILDS_MAIN' ],
[ 'ROOM_RUINS_ENTRANCE', 'ROOM_RUINS_BEANSTALK', 'ROOM_RUINS_TEKTITES', 'ROOM_RUINS_LADDER_TO_TEKTITES', 'ROOM_RUINS_FORTRESS_ENTRANCE', 'ROOM_RUINS_BELOW_FORTRESS_ENTRANCE' ],
[ 'ROOM_MT_CRENEL_TOP', 'ROOM_MT_CRENEL_WALL_CLIMB', 'ROOM_MT_CRENEL_CAVERN_OF_FLAMES_ENTRANCE', 'ROOM_MT_CRENEL_CENTER', 'ROOM_MT_CRENEL_ENTRANCE' ],
[ 'ROOM_CASTLE_GARDEN_MAIN' ],
[ 'ROOM_CLOUD_TOPS_CLOUD_TOPS', 'ROOM_CLOUD_TOPS_CLOUD_MIDDLES', 'ROOM_CLOUD_TOPS_CLOUD_BOTTOMS' ],
[ 'ROOM_ROYAL_VALLEY_MAIN', 'ROOM_ROYAL_VALLEY_FOREST_MAZE' ],
[ 'ROOM_VEIL_FALLS_MAIN' ],
[ 'ROOM_LAKE_HYLIA_MAIN', 'ROOM_LAKE_HYLIA_BEANSTALK' ],
[ 'ROOM_LAKE_WOODS_CAVE_MAIN' ],
[ 'ROOM_BEANSTALKS_CRENEL', 'ROOM_BEANSTALKS_LAKE_HYLIA', 'ROOM_BEANSTALKS_RUINS', 'ROOM_BEANSTALKS_EASTERN_HILLS', 'ROOM_BEANSTALKS_WESTERN_WOODS', 'ROOM_BEANSTALKS_5', 'ROOM_BEANSTALKS_6', 'ROOM_BEANSTALKS_7', 'ROOM_BEANSTALKS_8', 'ROOM_BEANSTALKS_9', 'ROOM_BEANSTALKS_a', 'ROOM_BEANSTALKS_b', 'ROOM_BEANSTALKS_c', 'ROOM_BEANSTALKS_d', 'ROOM_BEANSTALKS_e', 'ROOM_BEANSTALKS_f', 'ROOM_BEANSTALKS_CRENEL_CLIMB', 'ROOM_BEANSTALKS_LAKE_HYLIA_CLIMB', 'ROOM_BEANSTALKS_RUINS_CLIMB', 'ROOM_BEANSTALKS_EASTERN_HILLS_CLIMB', 'ROOM_BEANSTALKS_WESTERN_WOODS_CLIMB', 'ROOM_BEANSTALKS_21', 'ROOM_BEANSTALKS_22', 'ROOM_BEANSTALKS_23', 'ROOM_BEANSTALKS_24', 'ROOM_BEANSTALKS_25', 'ROOM_BEANSTALKS_26', 'ROOM_BEANSTALKS_27', 'ROOM_BEANSTALKS_28', 'ROOM_BEANSTALKS_29', 'ROOM_BEANSTALKS_30', 'ROOM_BEANSTALKS_31', ],
[ 'ROOM_EMPTY_0', 'ROOM_EMPTY_1' ],
[ 'ROOM_HYRULE_DIG_CAVES_TOWN' ],
[ 'ROOM_MELARIS_MINE_MAIN' ],
[ 'ROOM_MINISH_PATHS_MINISH_VILLAGE', 'ROOM_MINISH_PATHS_BOW', 'ROOM_MINISH_PATHS_SCHOOLYARD', 'ROOM_MINISH_PATHS_LON_LON_RANCH', 'ROOM_MINISH_PATHS_LAKE_HYLIA' ],
[ 'ROOM_CRENEL_MINISH_PATHS_BEAN', 'ROOM_CRENEL_MINISH_PATHS_SPRING_WATER', 'ROOM_CRENEL_MINISH_PATHS_RAIN', 'ROOM_CRENEL_MINISH_PATHS_MELARI' ],
[ 'ROOM_DIG_CAVES_EASTERN_HILLS', 'ROOM_DIG_CAVES_1', 'ROOM_DIG_CAVES_2', 'ROOM_DIG_CAVES_TRILBY_HIGHLANDS' ],
[ 'ROOM_CRENEL_DIG_CAVE_0' ],
[ 'ROOM_FESTIVAL_TOWN_MAIN' ],
[ 'ROOM_VEIL_FALLS_DIG_CAVE_0' ],
[ 'ROOM_CASTOR_WILDS_DIG_CAVE_0' ],
[ 'ROOM_OUTER_FORTRESS_OF_WINDS_ENTRANCE_HALL', 'ROOM_OUTER_FORTRESS_OF_WINDS_2F', 'ROOM_OUTER_FORTRESS_OF_WINDS_3F', 'ROOM_OUTER_FORTRESS_OF_WINDS_MOLE_MITTS', 'ROOM_OUTER_FORTRESS_OF_WINDS_SMALL_KEY' ],
[ 'ROOM_HYLIA_DIG_CAVES_0', 'ROOM_HYLIA_DIG_CAVES_1' ],
[ 'ROOM_VEIL_FALLS_TOP_0' ],
[ 'ROOM_NULL_1B_0' ],
[ 'ROOM_NULL_1C_0' ],
[ 'ROOM_NULL_1D_0' ],
[ 'ROOM_NULL_1E_0' ],
[ 'ROOM_NULL_1F_0' ],
[ 'ROOM_MINISH_HOUSE_INTERIORS_GENTARI_MAIN', 'ROOM_MINISH_HOUSE_INTERIORS_GENTARI_EXIT', 'ROOM_MINISH_HOUSE_INTERIORS_FESTARI', 'ROOM_MINISH_HOUSE_INTERIORS_RED', 'ROOM_MINISH_HOUSE_INTERIORS_GREEN', 'ROOM_MINISH_HOUSE_INTERIORS_BLUE', 'ROOM_MINISH_HOUSE_INTERIORS_SIDE_AREA', 'ROOM_MINISH_HOUSE_INTERIORS_SHOE_MINISH', 'ROOM_MINISH_HOUSE_INTERIORS_POT_MINISH', 'ROOM_MINISH_HOUSE_INTERIORS_BARREL_MINISH', 'ROOM_MINISH_HOUSE_INTERIORS_NULL1', 'ROOM_MINISH_HOUSE_INTERIORS_NULL2', 'ROOM_MINISH_HOUSE_INTERIORS_c', 'ROOM_MINISH_HOUSE_INTERIORS_d', 'ROOM_MINISH_HOUSE_INTERIORS_e', 'ROOM_MINISH_HOUSE_INTERIORS_f', 'ROOM_MINISH_HOUSE_INTERIORS_MELARI_MINES_SOUTHWEST', 'ROOM_MINISH_HOUSE_INTERIORS_MELARI_MINES_SOUTHEAST', 'ROOM_MINISH_HOUSE_INTERIORS_MELARI_MINES_EAST', 'ROOM_MINISH_HOUSE_INTERIORS_13', 'ROOM_MINISH_HOUSE_INTERIORS_14', 'ROOM_MINISH_HOUSE_INTERIORS_15', 'ROOM_MINISH_HOUSE_INTERIORS_16', 'ROOM_MINISH_HOUSE_INTERIORS_17', 'ROOM_MINISH_HOUSE_INTERIORS_18', 'ROOM_MINISH_HOUSE_INTERIORS_19', 'ROOM_MINISH_HOUSE_INTERIORS_1a', 'ROOM_MINISH_HOUSE_INTERIORS_1b', 'ROOM_MINISH_HOUSE_INTERIORS_1c', 'ROOM_MINISH_HOUSE_INTERIORS_1d', 'ROOM_MINISH_HOUSE_INTERIORS_1e', 'ROOM_MINISH_HOUSE_INTERIORS_1f', 'ROOM_MINISH_HOUSE_INTERIORS_HYRULE_FIELD_SOUTHWEST', 'ROOM_MINISH_HOUSE_INTERIORS_SOUTH_HYRULE_FIELD', 'ROOM_MINISH_HOUSE_INTERIORS_NEXT_TO_KNUCKLE', 'ROOM_MINISH_HOUSE_INTERIORS_LIBRARI', 'ROOM_MINISH_HOUSE_INTERIORS_HYRULE_FIELD_EXIT', 'ROOM_MINISH_HOUSE_INTERIORS_HYRULE_TOWN', 'ROOM_MINISH_HOUSE_INTERIORS_MINISH_WOODS_BOMB', 'ROOM_MINISH_HOUSE_INTERIORS_LAKE_HYLIA_OCARINA' ],
[ 'ROOM_HOUSE_INTERIORS_1_MAYOR', 'ROOM_HOUSE_INTERIORS_1_POST_OFFICE', 'ROOM_HOUSE_INTERIORS_1_LIBRARY_2F', 'ROOM_HOUSE_INTERIORS_1_LIBRARY_1F', 'ROOM_HOUSE_INTERIORS_1_INN_1F', 'ROOM_HOUSE_INTERIORS_1_INN_WEST_ROOM', 'ROOM_HOUSE_INTERIORS_1_INN_MIDDLE_ROOM', 'ROOM_HOUSE_INTERIORS_1_INN_EAST_ROOM', 'ROOM_HOUSE_INTERIORS_1_INN_WEST_2F', 'ROOM_HOUSE_INTERIORS_1_INN_EAST_2F', 'ROOM_HOUSE_INTERIORS_1_INN_MINISH_HEART_PIECE', 'ROOM_HOUSE_INTERIORS_1_SCHOOL_WEST', 'ROOM_HOUSE_INTERIORS_1_SCHOOL_EAST', 'ROOM_HOUSE_INTERIORS_1_d', 'ROOM_HOUSE_INTERIORS_1_e', 'ROOM_HOUSE_INTERIORS_1_f', 'ROOM_HOUSE_INTERIORS_1_10', 'ROOM_HOUSE_INTERIORS_1_11', 'ROOM_HOUSE_INTERIORS_1_12', 'ROOM_HOUSE_INTERIORS_1_13', 'ROOM_HOUSE_INTERIORS_1_14', 'ROOM_HOUSE_INTERIORS_1_15', 'ROOM_HOUSE_INTERIORS_1_16', 'ROOM_HOUSE_INTERIORS_1_17', 'ROOM_HOUSE_INTERIORS_1_18', 'ROOM_HOUSE_INTERIORS_1_19', 'ROOM_HOUSE_INTERIORS_1_1a', 'ROOM_HOUSE_INTERIORS_1_1b', 'ROOM_HOUSE_INTERIORS_1_1c', 'ROOM_HOUSE_INTERIORS_1_1d', 'ROOM_HOUSE_INTERIORS_1_1e', 'ROOM_HOUSE_INTERIORS_1_1f' ],
[ 'ROOM_HOUSE_INTERIORS_2_STRANGER', 'ROOM_HOUSE_INTERIORS_2_WEST_ORACLE', 'ROOM_HOUSE_INTERIORS_2_2', 'ROOM_HOUSE_INTERIORS_2_3', 'ROOM_HOUSE_INTERIORS_2_DR_LEFT', 'ROOM_HOUSE_INTERIORS_2_5', 'ROOM_HOUSE_INTERIORS_2_ROMIO', 'ROOM_HOUSE_INTERIORS_2_JULIETTA', 'ROOM_HOUSE_INTERIORS_2_PERCY', 'ROOM_HOUSE_INTERIORS_2_EAST_ORACLE', 'ROOM_HOUSE_INTERIORS_2_a', 'ROOM_HOUSE_INTERIORS_2_b', 'ROOM_HOUSE_INTERIORS_2_CUCCO', 'ROOM_HOUSE_INTERIORS_2_d', 'ROOM_HOUSE_INTERIORS_2_e', 'ROOM_HOUSE_INTERIORS_2_f', 'ROOM_HOUSE_INTERIORS_2_LINKS_HOUSE_ENTRANCE', 'ROOM_HOUSE_INTERIORS_2_LINKS_HOUSE_SMITH', 'ROOM_HOUSE_INTERIORS_2_DAMPE', 'ROOM_HOUSE_INTERIORS_2_13', 'ROOM_HOUSE_INTERIORS_2_STOCKWELL_LAKE_HOUSE', 'ROOM_HOUSE_INTERIORS_2_LINKS_HOUSE_BEDROOM', 'ROOM_HOUSE_INTERIORS_2_16', 'ROOM_HOUSE_INTERIORS_2_17', 'ROOM_HOUSE_INTERIORS_2_18', 'ROOM_HOUSE_INTERIORS_2_19', 'ROOM_HOUSE_INTERIORS_2_1a', 'ROOM_HOUSE_INTERIORS_2_1b', 'ROOM_HOUSE_INTERIORS_2_1c', 'ROOM_HOUSE_INTERIORS_2_1d', 'ROOM_HOUSE_INTERIORS_2_1e', 'ROOM_HOUSE_INTERIORS_2_1f', 'ROOM_HOUSE_INTERIORS_2_20', 'ROOM_HOUSE_INTERIORS_2_21', 'ROOM_HOUSE_INTERIORS_2_22', 'ROOM_HOUSE_INTERIORS_2_23', 'ROOM_HOUSE_INTERIORS_2_24', 'ROOM_HOUSE_INTERIORS_2_25', 'ROOM_HOUSE_INTERIORS_2_26', 'ROOM_HOUSE_INTERIORS_2_27', 'ROOM_HOUSE_INTERIORS_2_28', 'ROOM_HOUSE_INTERIORS_2_29', 'ROOM_HOUSE_INTERIORS_2_2a', 'ROOM_HOUSE_INTERIORS_2_2b', 'ROOM_HOUSE_INTERIORS_2_2c', 'ROOM_HOUSE_INTERIORS_2_2d', 'ROOM_HOUSE_INTERIORS_2_2e', 'ROOM_HOUSE_INTERIORS_2_2f' ],
[ 'ROOM_HOUSE_INTERIORS_3_STOCKWELL_SHOP', 'ROOM_HOUSE_INTERIORS_3_CAFE', 'ROOM_HOUSE_INTERIORS_3_REM_SHOE_SHOP', 'ROOM_HOUSE_INTERIORS_3_BAKERY', 'ROOM_HOUSE_INTERIORS_3_SIMON', 'ROOM_HOUSE_INTERIORS_3_FIGURINE_HOUSE', 'ROOM_HOUSE_INTERIORS_3_BORLOV_ENTRANCE', 'ROOM_HOUSE_INTERIORS_3_CARLOV', 'ROOM_HOUSE_INTERIORS_3_BORLOV', 'ROOM_HOUSE_INTERIORS_3_9', 'ROOM_HOUSE_INTERIORS_3_a', 'ROOM_HOUSE_INTERIORS_3_b', 'ROOM_HOUSE_INTERIORS_3_c', 'ROOM_HOUSE_INTERIORS_3_d', 'ROOM_HOUSE_INTERIORS_3_e', 'ROOM_HOUSE_INTERIORS_3_f' ],
[ 'ROOM_TREE_INTERIORS_WITCH_HUT', 'ROOM_TREE_INTERIORS_1', 'ROOM_TREE_INTERIORS_2', 'ROOM_TREE_INTERIORS_3', 'ROOM_TREE_INTERIORS_4', 'ROOM_TREE_INTERIORS_5', 'ROOM_TREE_INTERIORS_6', 'ROOM_TREE_INTERIORS_7', 'ROOM_TREE_INTERIORS_8', 'ROOM_TREE_INTERIORS_9', 'ROOM_TREE_INTERIORS_a', 'ROOM_TREE_INTERIORS_b', 'ROOM_TREE_INTERIORS_c', 'ROOM_TREE_INTERIORS_d', 'ROOM_TREE_INTERIORS_e', 'ROOM_TREE_INTERIORS_f', 'ROOM_TREE_INTERIORS_STAIRS_TO_CARLOV', 'ROOM_TREE_INTERIORS_PERCYS_TREEHOUSE', 'ROOM_TREE_INTERIORS_SOUTH_HYRULE_FIELD_HEART_PIECE', 'ROOM_TREE_INTERIORS_WAVEBLADE', 'ROOM_TREE_INTERIORS_14', 'ROOM_TREE_INTERIORS_BOOMERANG_NORTHWEST', 'ROOM_TREE_INTERIORS_BOOMERANG_NORTHEAST', 'ROOM_TREE_INTERIORS_BOOMERANG_SOUTHWEST', 'ROOM_TREE_INTERIORS_BOOMERANG_SOUTHEAST', 'ROOM_TREE_INTERIORS_WESTERN_WOODS_HEART_PIECE', 'ROOM_TREE_INTERIORS_NORTH_HYRULE_FIELD_FAIRY_FOUNTAIN', 'ROOM_TREE_INTERIORS_MINISH_WOODS_GREAT_FAIRY', 'ROOM_TREE_INTERIORS_1c', 'ROOM_TREE_INTERIORS_MINISH_WOODS_BUSINESS_SCRUB', 'ROOM_TREE_INTERIORS_1e', 'ROOM_TREE_INTERIORS_UNUSED_HEART_CONTAINER' ],
[ 'ROOM_DOJOS_GRAYBLADE', 'ROOM_DOJOS_SPLITBLADE', 'ROOM_DOJOS_GREATBLADE', 'ROOM_DOJOS_SCARBLADE', 'ROOM_DOJOS_SWIFTBLADE_I', 'ROOM_DOJOS_GRIMBLADE', 'ROOM_DOJOS_WAVEBLADE', 'ROOM_DOJOS_7', 'ROOM_DOJOS_8', 'ROOM_DOJOS_9', 'ROOM_DOJOS_TO_GRIMBLADE', 'ROOM_DOJOS_TO_SPLITBLADE', 'ROOM_DOJOS_TO_GREATBLADE', 'ROOM_DOJOS_TO_SCARBLADE', 'ROOM_DOJOS_e', 'ROOM_DOJOS_f' ],
[ 'ROOM_CRENEL_CAVES_BLOCK_PUSHING', 'ROOM_CRENEL_CAVES_PILLAR_CAVE', 'ROOM_CRENEL_CAVES_BRIDGE_SWITCH', 'ROOM_CRENEL_CAVES_EXIT_TO_MINES', 'ROOM_CRENEL_CAVES_GRIP_RING', 'ROOM_CRENEL_CAVES_FAIRY_FOUNTAIN', 'ROOM_CRENEL_CAVES_SPINY_CHU_PUZZLE', 'ROOM_CRENEL_CAVES_CHUCHU_POT_CHEST', 'ROOM_CRENEL_CAVES_WATER_HEART_PIECE', 'ROOM_CRENEL_CAVES_RUPEE_FAIRY_FOUINTAIN', 'ROOM_CRENEL_CAVES_HELMASAUR_HALLWAY', 'ROOM_CRENEL_CAVES_MUSHROOM_KEESE', 'ROOM_CRENEL_CAVES_LADDER_TO_SPRING_WATER', 'ROOM_CRENEL_CAVES_BOMB_BUSINESS_SCRUB', 'ROOM_CRENEL_CAVES_HERMIT', 'ROOM_CRENEL_CAVES_HINT_SCRUB', 'ROOM_CRENEL_CAVES_TO_GRAYBLADE' ],
[ 'ROOM_MINISH_CRACKS_LON_LON_RANCH_NORTH', 'ROOM_MINISH_CRACKS_LAKE_HYLIA_EAST', 'ROOM_MINISH_CRACKS_HYRULE_CASTLE_GARDEN', 'ROOM_MINISH_CRACKS_MT_CRENEL', 'ROOM_MINISH_CRACKS_EAST_HYRULE_CASTLE', 'ROOM_MINISH_CRACKS_5', 'ROOM_MINISH_CRACKS_CASTOR_WILDS_BOW', 'ROOM_MINISH_CRACKS_RUINS_ENTRANCE', 'ROOM_MINISH_CRACKS_MINISH_WOODS_SOUTH', 'ROOM_MINISH_CRACKS_CASTOR_WILDS_NORTH', 'ROOM_MINISH_CRACKS_CASTOR_WILDS_WEST', 'ROOM_MINISH_CRACKS_CASTOR_WILDS_MIDDLE', 'ROOM_MINISH_CRACKS_RUINS_TEKTITE', 'ROOM_MINISH_CRACKS_CASTOR_WILDS_NEXT_TO_BOW', 'ROOM_MINISH_CRACKS_e', 'ROOM_MINISH_CRACKS_f', 'ROOM_MINISH_CRACKS_10', 'ROOM_MINISH_CRACKS_11', 'ROOM_MINISH_CRACKS_12', 'ROOM_MINISH_CRACKS_13', 'ROOM_MINISH_CRACKS_14', 'ROOM_MINISH_CRACKS_15', 'ROOM_MINISH_CRACKS_16', 'ROOM_MINISH_CRACKS_17' ],
[ 'ROOM_HOUSE_INTERIORS_4_CARPENTER', 'ROOM_HOUSE_INTERIORS_4_SWIFTBLADE', 'ROOM_HOUSE_INTERIORS_4_RANCH_HOUSE_WEST', 'ROOM_HOUSE_INTERIORS_4_RANCH_HOUSE_EAST', 'ROOM_HOUSE_INTERIORS_4_FARM_HOUSE', 'ROOM_HOUSE_INTERIORS_4_MAYOR_LAKE_CABIN', 'ROOM_HOUSE_INTERIORS_4_6', 'ROOM_HOUSE_INTERIORS_4_7', 'ROOM_HOUSE_INTERIORS_4_8', 'ROOM_HOUSE_INTERIORS_4_9', 'ROOM_HOUSE_INTERIORS_4_a', 'ROOM_HOUSE_INTERIORS_4_b', 'ROOM_HOUSE_INTERIORS_4_c', 'ROOM_HOUSE_INTERIORS_4_d', 'ROOM_HOUSE_INTERIORS_4_e', 'ROOM_HOUSE_INTERIORS_4_f' ],
[ 'ROOM_GREAT_FAIRIES_GRAVEYARD', 'ROOM_GREAT_FAIRIES_MINISH_WOODS', 'ROOM_GREAT_FAIRIES_CRENEL', 'ROOM_GREAT_FAIRIES_NOT_IMPLEMENTED', 'ROOM_GREAT_FAIRIES_4', 'ROOM_GREAT_FAIRIES_5', 'ROOM_GREAT_FAIRIES_6', 'ROOM_GREAT_FAIRIES_7' ],
[ 'ROOM_CASTOR_CAVES_SOUTH', 'ROOM_CASTOR_CAVES_NORTH', 'ROOM_CASTOR_CAVES_WIND_RUINS', 'ROOM_CASTOR_CAVES_DARKNUT', 'ROOM_CASTOR_CAVES_HEART_PIECE', 'ROOM_CASTOR_CAVES_5', 'ROOM_CASTOR_CAVES_6', 'ROOM_CASTOR_CAVES_7' ],
[ 'ROOM_CASTOR_DARKNUT_MAIN', 'ROOM_CASTOR_DARKNUT_HALL' ],
[ 'ROOM_ARMOS_INTERIORS_RUINS_ENTRANCE_NORTH', 'ROOM_ARMOS_INTERIORS_RUINS_ENTRANCE_SOUTH', 'ROOM_ARMOS_INTERIORS_RUINS_LEFT', 'ROOM_ARMOS_INTERIORS_RUINS_MIDDLE_LEFT', 'ROOM_ARMOS_INTERIORS_RUINS_MIDDLE_RIGHT', 'ROOM_ARMOS_INTERIORS_RUINS_RIGHT', 'ROOM_ARMOS_INTERIORS_6', 'ROOM_ARMOS_INTERIORS_RUINS_GRASS_PATH', 'ROOM_ARMOS_INTERIORS_8', 'ROOM_ARMOS_INTERIORS_FORTRESS_LEFT', 'ROOM_ARMOS_INTERIORS_FORTRESS_RIGHT' ],
[ 'ROOM_TOWN_MINISH_HOLES_MAYORS_HOUSE', 'ROOM_TOWN_MINISH_HOLES_WEST_ORACLE', 'ROOM_TOWN_MINISH_HOLES_DR_LEFT', 'ROOM_TOWN_MINISH_HOLES_CARPENTER', 'ROOM_TOWN_MINISH_HOLES_CAFE', 'ROOM_TOWN_MINISH_HOLES_5', 'ROOM_TOWN_MINISH_HOLES_6', 'ROOM_TOWN_MINISH_HOLES_7', 'ROOM_TOWN_MINISH_HOLES_8', 'ROOM_TOWN_MINISH_HOLES_9', 'ROOM_TOWN_MINISH_HOLES_a', 'ROOM_TOWN_MINISH_HOLES_b', 'ROOM_TOWN_MINISH_HOLES_c', 'ROOM_TOWN_MINISH_HOLES_d', 'ROOM_TOWN_MINISH_HOLES_e', 'ROOM_TOWN_MINISH_HOLES_f', 'ROOM_TOWN_MINISH_HOLES_LIBRARY_BOOKSHELF', 'ROOM_TOWN_MINISH_HOLES_LIBRARY_BOOKS_HOUSE', 'ROOM_TOWN_MINISH_HOLES_REM_SHOE_SHOP', 'ROOM_TOWN_MINISH_HOLES_13', 'ROOM_TOWN_MINISH_HOLES_20', 'ROOM_TOWN_MINISH_HOLES_21', 'ROOM_TOWN_MINISH_HOLES_22', 'ROOM_TOWN_MINISH_HOLES_23', 'ROOM_TOWN_MINISH_HOLES_24', 'ROOM_TOWN_MINISH_HOLES_25', 'ROOM_TOWN_MINISH_HOLES_26', 'ROOM_TOWN_MINISH_HOLES_27', 'ROOM_TOWN_MINISH_HOLES_28', 'ROOM_TOWN_MINISH_HOLES_29', 'ROOM_TOWN_MINISH_HOLES_30', 'ROOM_TOWN_MINISH_HOLES_31', 'ROOM_TOWN_MINISH_HOLES_32', 'ROOM_TOWN_MINISH_HOLES_33', 'ROOM_TOWN_MINISH_HOLES_34', 'ROOM_TOWN_MINISH_HOLES_35', 'ROOM_TOWN_MINISH_HOLES_36', 'ROOM_TOWN_MINISH_HOLES_37', 'ROOM_TOWN_MINISH_HOLES_38',  'ROOM_TOWN_MINISH_HOLES_39', 'ROOM_TOWN_MINISH_HOLES_40', 'ROOM_TOWN_MINISH_HOLES_41', 'ROOM_TOWN_MINISH_HOLES_42', 'ROOM_TOWN_MINISH_HOLES_43', 'ROOM_TOWN_MINISH_HOLES_44', 'ROOM_TOWN_MINISH_HOLES_45', 'ROOM_TOWN_MINISH_HOLES_46', 'ROOM_TOWN_MINISH_HOLES_47', ],
[ 'ROOM_MINISH_RAFTERS_CAFE', 'ROOM_MINISH_RAFTERS_STOCKWELL', 'ROOM_MINISH_RAFTERS_DR_LEFT', 'ROOM_MINISH_RAFTERS_BAKERY' ],
[ 'ROOM_GORON_CAVE_STAIRS', 'ROOM_GORON_CAVE_MAIN' ],
[ 'ROOM_WIND_TRIBE_TOWER_ENTRANCE', 'ROOM_WIND_TRIBE_TOWER_FLOOR_1', 'ROOM_WIND_TRIBE_TOWER_FLOOR_2', 'ROOM_WIND_TRIBE_TOWER_FLOOR_3' ],
[ 'ROOM_WIND_TRIBE_TOWER_ROOF_0' ],
[ 'ROOM_CAVES_BOOMERANG', 'ROOM_CAVES_TO_GRAVEYARD', 'ROOM_CAVES_2', 'ROOM_CAVES_3', 'ROOM_CAVES_4', 'ROOM_CAVES_5', 'ROOM_CAVES_6', 'ROOM_CAVES_TRILBY_KEESE_CHEST', 'ROOM_CAVES_TRILBY_FAIRY_FOUNTAIN', 'ROOM_CAVES_SOUTH_HYRULE_FIELD_FAIRY_FOUNTAIN', 'ROOM_CAVES_a', 'ROOM_CAVES_HYRULE_TOWN_WATERFALL', 'ROOM_CAVES_LON_LON_RANCH', 'ROOM_CAVES_LON_LON_RANCH_SECRET', 'ROOM_CAVES_TRILBY_HIGHLANDS', 'ROOM_CAVES_LON_LON_RANCH_WALLET', 'ROOM_CAVES_SOUTH_HYRULE_FIELD_RUPEE', 'ROOM_CAVES_TRILBY_RUPEE', 'ROOM_CAVES_TRILBY_MITTS_FAIRY_FOUNTAIN', 'ROOM_CAVES_HILLS_KEESE_CHEST', 'ROOM_CAVES_BOTTLE_BUSINESS_SCRUB', 'ROOM_CAVES_HEART_PIECE_HALLWAY', 'ROOM_CAVES_NORTH_HYRULE_FIELD_FAIRY_FOUNTAIN', 'ROOM_CAVES_KINSTONE_BUSINESS_SCRUB' ],
[ 'ROOM_VEIL_FALLS_CAVES_HALLWAY_2F', 'ROOM_VEIL_FALLS_CAVES_HALLWAY_1F', 'ROOM_VEIL_FALLS_CAVES_HALLWAY_SECRET_ROOM', 'ROOM_VEIL_FALLS_CAVES_ENTRANCE', 'ROOM_VEIL_FALLS_CAVES_EXIT', 'ROOM_VEIL_FALLS_CAVES_SECRET_CHEST', 'ROOM_VEIL_FALLS_CAVES_HALLWAY_SECRET_STAIRCASE', 'ROOM_VEIL_FALLS_CAVES_HALLWAY_BLOCK_PUZZLE', 'ROOM_VEIL_FALLS_CAVES_HALLWAY_RUPEE_PATH', 'ROOM_VEIL_FALLS_CAVES_HALLWAY_HEART_PIECE', 'ROOM_VEIL_FALLS_CAVES_a', 'ROOM_VEIL_FALLS_CAVES_b', 'ROOM_VEIL_FALLS_CAVES_c', 'ROOM_VEIL_FALLS_CAVES_d', 'ROOM_VEIL_FALLS_CAVES_e', 'ROOM_VEIL_FALLS_CAVES_f' ],
[ 'ROOM_ROYAL_VALLEY_GRAVES_HEART_PIECE', 'ROOM_ROYAL_VALLEY_GRAVES_GINA' ],
[ 'ROOM_MINISH_CAVES_BEAN_PESTO', 'ROOM_MINISH_CAVES_SOUTHEAST_WATER_1', 'ROOM_MINISH_CAVES_2', 'ROOM_MINISH_CAVES_RUINS', 'ROOM_MINISH_CAVES_OUTSIDE_LINKS_HOUSE', 'ROOM_MINISH_CAVES_MINISH_WOODS_NORTH_1', 'ROOM_MINISH_CAVES_6', 'ROOM_MINISH_CAVES_LAKE_HYLIA_NORTH', 'ROOM_MINISH_CAVES_LAKE_HYLIA_LIBRARI', 'ROOM_MINISH_CAVES_MINISH_WOODS_SOUTHWEST' ],
[ 'ROOM_CASTLE_GARDEN_MINISH_HOLES_0', 'ROOM_CASTLE_GARDEN_MINISH_HOLES_1' ],
[ 'ROOM_37_0', 'ROOM_37_1' ],
[ 'ROOM_EZLO_CUTSCENE_0' ],
[ 'ROOM_NULL_39_0' ],
[ 'ROOM_NULL_3A_0' ],
[ 'ROOM_NULL_3B_0' ],
[ 'ROOM_NULL_3C_0' ],
[ 'ROOM_NULL_3D_0' ],
[ 'ROOM_NULL_3E_0' ],
[ 'ROOM_NULL_3F_0' ],
[ 'ROOM_40_0', 'ROOM_40_1', 'ROOM_40_2', 'ROOM_40_3', 'ROOM_40_4', 'ROOM_40_5', 'ROOM_40_6', 'ROOM_40_7', 'ROOM_40_8',],
[ 'ROOM_HYRULE_TOWN_UNDERGROUND_0', 'ROOM_HYRULE_TOWN_UNDERGROUND_1' ],
[ 'ROOM_GARDEN_FOUNTAINS_EAST', 'ROOM_GARDEN_FOUNTAINS_WEST' ],
[ 'ROOM_HYRULE_CASTLE_CELLAR_0', 'ROOM_HYRULE_CASTLE_CELLAR_1' ],
[ 'ROOM_SIMONS_SIMULATION_0' ],
[ 'ROOM_45_0' ],
[ 'ROOM_NULL_46_0', 'AREA_NULL_46_1', 'AREA_NULL_46_2', 'AREA_NULL_46_3', 'AREA_NULL_46_4', 'AREA_NULL_46_5', 'AREA_NULL_46_6', 'AREA_NULL_46_7' ],
[ 'ROOM_47_0', 'ROOM_47_1', 'ROOM_47_2', ],
[ 'ROOM_DEEPWOOD_SHRINE_MADDERPILLAR', 'ROOM_DEEPWOOD_SHRINE_BLUE_PORTAL', 'ROOM_DEEPWOOD_SHRINE_STAIRS_TO_B1', 'ROOM_DEEPWOOD_SHRINE_POT_BRIDGE', 'ROOM_DEEPWOOD_SHRINE_DOUBLE_STATUE', 'ROOM_DEEPWOOD_SHRINE_MAP', 'ROOM_DEEPWOOD_SHRINE_BARREL', 'ROOM_DEEPWOOD_SHRINE_BUTTON', 'ROOM_DEEPWOOD_SHRINE_MULLDOZER', 'ROOM_DEEPWOOD_SHRINE_PILLARS', 'ROOM_DEEPWOOD_SHRINE_LEVER', 'ROOM_DEEPWOOD_SHRINE_ENTRANCE', 'ROOM_DEEPWOOD_SHRINE_c', 'ROOM_DEEPWOOD_SHRINE_d', 'ROOM_DEEPWOOD_SHRINE_e', 'ROOM_DEEPWOOD_SHRINE_f', 'ROOM_DEEPWOOD_SHRINE_TORCHES', 'ROOM_DEEPWOOD_SHRINE_BOSS_KEY', 'ROOM_DEEPWOOD_SHRINE_COMPASS', 'ROOM_DEEPWOOD_SHRINE_13', 'ROOM_DEEPWOOD_SHRINE_LILY_PAD_WEST', 'ROOM_DEEPWOOD_SHRINE_LILY_PAD_EAST', 'ROOM_DEEPWOOD_SHRINE_16', 'ROOM_DEEPWOOD_SHRINE_BOSS_DOOR', 'ROOM_DEEPWOOD_SHRINE_18', 'ROOM_DEEPWOOD_SHRINE_19', 'ROOM_DEEPWOOD_SHRINE_1a', 'ROOM_DEEPWOOD_SHRINE_1b', 'ROOM_DEEPWOOD_SHRINE_1c', 'ROOM_DEEPWOOD_SHRINE_1d', 'ROOM_DEEPWOOD_SHRINE_1e', 'ROOM_DEEPWOOD_SHRINE_1f', 'ROOM_DEEPWOOD_SHRINE_INSIDE_BARREL' ],
[ 'ROOM_DEEPWOOD_SHRINE_BOSS_MAIN' ],
[ 'ROOM_DEEPWOOD_SHRINE_ENTRY_MAIN' ],
[ 'ROOM_NULL_4B_0' ],
[ 'ROOM_NULL_4C_0' ],
[ 'ROOM_4D_0' ],
[ 'ROOM_NULL_4E_0' ],
[ 'ROOM_NULL_4F_0' ],
[ 'ROOM_CAVE_OF_FLAMES_AFTER_CANE', 'ROOM_CAVE_OF_FLAMES_SPINY_CHU', 'ROOM_CAVE_OF_FLAMES_CART_TO_SPINY_CHU', 'ROOM_CAVE_OF_FLAMES_ENTRANCE', 'ROOM_CAVE_OF_FLAMES_MAIN_CART', 'ROOM_CAVE_OF_FLAMES_NORTH_ENTRANCE', 'ROOM_CAVE_OF_FLAMES_CART_WEST', 'ROOM_CAVE_OF_FLAMES_HELMASAUR_FIGHT', 'ROOM_CAVE_OF_FLAMES_ROLLOBITE_LAVA_ROOM', 'ROOM_CAVE_OF_FLAMES_MINISH_LAVA_ROOM', 'ROOM_CAVE_OF_FLAMES_a', 'ROOM_CAVE_OF_FLAMES_b', 'ROOM_CAVE_OF_FLAMES_c', 'ROOM_CAVE_OF_FLAMES_d', 'ROOM_CAVE_OF_FLAMES_e', 'ROOM_CAVE_OF_FLAMES_f', 'ROOM_CAVE_OF_FLAMES_MINISH_SPIKES', 'ROOM_CAVE_OF_FLAMES_TOMPAS_DOOM', 'ROOM_CAVE_OF_FLAMES_BEFORE_GLEEROK', 'ROOM_CAVE_OF_FLAMES_BOSSKEY_PATH1', 'ROOM_CAVE_OF_FLAMES_BOSSKEY_PATH2', 'ROOM_CAVE_OF_FLAMES_COMPASS', 'ROOM_CAVE_OF_FLAMES_BOB_OMB_WALL', 'ROOM_CAVE_OF_FLAMES_BOSS_DOOR', 'ROOM_CAVE_OF_FLAMES_18', 'ROOM_CAVE_OF_FLAMES_19', 'ROOM_CAVE_OF_FLAMES_1a', 'ROOM_CAVE_OF_FLAMES_1b', 'ROOM_CAVE_OF_FLAMES_1c', 'ROOM_CAVE_OF_FLAMES_1d', 'ROOM_CAVE_OF_FLAMES_1e', 'ROOM_CAVE_OF_FLAMES_1f', 'ROOM_CAVE_OF_FLAMES_20' ],
[ 'ROOM_CAVE_OF_FLAMES_BOSS_0' ],
[ 'ROOM_NULL_52_0' ],
[ 'ROOM_NULL_53_0' ],
[ 'ROOM_NULL_54_0' ],
[ 'ROOM_NULL_55_0' ],
[ 'ROOM_NULL_56_0' ],
[ 'ROOM_57_0' ],
[ 'ROOM_FORTRESS_OF_WINDS_DOUBLE_EYEGORE', 'ROOM_FORTRESS_OF_WINDS_BEFORE_MAZAAL', 'ROOM_FORTRESS_OF_WINDS_EAST_KEY_LEVER', 'ROOM_FORTRESS_OF_WINDS_PIT_PLATFORMS', 'ROOM_FORTRESS_OF_WINDS_WEST_KEY_LEVER', 'ROOM_FORTRESS_OF_WINDS_5', 'ROOM_FORTRESS_OF_WINDS_6', 'ROOM_FORTRESS_OF_WINDS_7', 'ROOM_FORTRESS_OF_WINDS_8', 'ROOM_FORTRESS_OF_WINDS_9', 'ROOM_FORTRESS_OF_WINDS_a', 'ROOM_FORTRESS_OF_WINDS_b', 'ROOM_FORTRESS_OF_WINDS_c', 'ROOM_FORTRESS_OF_WINDS_d', 'ROOM_FORTRESS_OF_WINDS_e', 'ROOM_FORTRESS_OF_WINDS_f', 'ROOM_FORTRESS_OF_WINDS_DARKNUT_ROOM', 'ROOM_FORTRESS_OF_WINDS_ARROW_EYE_BRIDGE', 'ROOM_FORTRESS_OF_WINDS_NORTH_SPLIT_PATH_PIT', 'ROOM_FORTRESS_OF_WINDS_WALLMASTER_MINISH_PORTAL', 'ROOM_FORTRESS_OF_WINDS_PILLAR_CLONE_BUTTONS', 'ROOM_FORTRESS_OF_WINDS_ROTATING_SPIKE_TRAPS', 'ROOM_FORTRESS_OF_WINDS_MAZAAL', 'ROOM_FORTRESS_OF_WINDS_STALFOS', 'ROOM_FORTRESS_OF_WINDS_ENTRANCE_MOLE_MITTS', 'ROOM_FORTRESS_OF_WINDS_MAIN_2F', 'ROOM_FORTRESS_OF_WINDS_MINISH_HOLE', 'ROOM_FORTRESS_OF_WINDS_BOSS_KEY', 'ROOM_FORTRESS_OF_WINDS_WEST_STAIRS_2F', 'ROOM_FORTRESS_OF_WINDS_EAST_STAIRS_2F', 'ROOM_FORTRESS_OF_WINDS_1e', 'ROOM_FORTRESS_OF_WINDS_1f', 'ROOM_FORTRESS_OF_WINDS_WEST_STAIRS_1F', 'ROOM_FORTRESS_OF_WINDS_CENTER_STAIRS_1F', 'ROOM_FORTRESS_OF_WINDS_EAST_STAIRS_1F', 'ROOM_FORTRESS_OF_WINDS_WIZZROBE', 'ROOM_FORTRESS_OF_WINDS_HEART_PIECE', 'ROOM_FORTRESS_OF_WINDS_25', 'ROOM_FORTRESS_OF_WINDS_26', 'ROOM_FORTRESS_OF_WINDS_27' ],
[ 'ROOM_FORTRESS_OF_WINDS_TOP_MAIN' ],
[ 'ROOM_INNER_MAZAAL_MAIN', 'ROOM_INNER_MAZAAL_PHASE_1' ],
[ 'ROOM_NULL_5B_0' ],
[ 'ROOM_NULL_5C_0' ],
[ 'ROOM_NULL_5D_0' ],
[ 'ROOM_NULL_5E_0' ],
[ 'ROOM_5F_0' ],
[ 'ROOM_TEMPLE_OF_DROPLETS_WEST_HOLE', 'ROOM_TEMPLE_OF_DROPLETS_NORTH_SPLIT_ROOM', 'ROOM_TEMPLE_OF_DROPLETS_EAST_HOLE', 'ROOM_TEMPLE_OF_DROPLETS_ENTRANCE', 'ROOM_TEMPLE_OF_DROPLETS_NORTHWEST_STAIRS', 'ROOM_TEMPLE_OF_DROPLETS_SCISSORS_MINIBOSS', 'ROOM_TEMPLE_OF_DROPLETS_WATERFALL_NORTHWEST', 'ROOM_TEMPLE_OF_DROPLETS_WATERFALL_NORTHEAST', 'ROOM_TEMPLE_OF_DROPLETS_ELEMENT', 'ROOM_TEMPLE_OF_DROPLETS_ICE_CORNER', 'ROOM_TEMPLE_OF_DROPLETS_ICE_PIT_MAZE', 'ROOM_TEMPLE_OF_DROPLETS_HOLE_TO_BLUE_CHU_KEY', 'ROOM_TEMPLE_OF_DROPLETS_WEST_WATERFALL_SOUTHEAST', 'ROOM_TEMPLE_OF_DROPLETS_WEST_WATERFALL_SOUTHWEST', 'ROOM_TEMPLE_OF_DROPLETS_BIG_OCTO', 'ROOM_TEMPLE_OF_DROPLETS_TO_BLUE_CHU', 'ROOM_TEMPLE_OF_DROPLETS_BLUE_CHU', 'ROOM_TEMPLE_OF_DROPLETS_BLUE_CHU_KEY', 'ROOM_TEMPLE_OF_DROPLETS_12', 'ROOM_TEMPLE_OF_DROPLETS_13', 'ROOM_TEMPLE_OF_DROPLETS_14', 'ROOM_TEMPLE_OF_DROPLETS_15', 'ROOM_TEMPLE_OF_DROPLETS_16', 'ROOM_TEMPLE_OF_DROPLETS_17', 'ROOM_TEMPLE_OF_DROPLETS_18', 'ROOM_TEMPLE_OF_DROPLETS_19', 'ROOM_TEMPLE_OF_DROPLETS_1a', 'ROOM_TEMPLE_OF_DROPLETS_1b', 'ROOM_TEMPLE_OF_DROPLETS_1c', 'ROOM_TEMPLE_OF_DROPLETS_1d', 'ROOM_TEMPLE_OF_DROPLETS_1e', 'ROOM_TEMPLE_OF_DROPLETS_1f', 'ROOM_TEMPLE_OF_DROPLETS_BOSS_KEY', 'ROOM_TEMPLE_OF_DROPLETS_NORTH_SMALL_KEY', 'ROOM_TEMPLE_OF_DROPLETS_BLOCK_CLONE_BUTTON_PUZZLE', 'ROOM_TEMPLE_OF_DROPLETS_BLOCK_CLONE_PUZZLE', 'ROOM_TEMPLE_OF_DROPLETS_BLOCK_CLONE_ICE_BRIDGE', 'ROOM_TEMPLE_OF_DROPLETS_STAIRS_TO_SCISSORS_MINIBOSS', 'ROOM_TEMPLE_OF_DROPLETS_SPIKE_BAR_FLIPPER_ROOM', 'ROOM_TEMPLE_OF_DROPLETS_9_LANTERNS', 'ROOM_TEMPLE_OF_DROPLETS_LILYPAD_ICE_BLOCKS', 'ROOM_TEMPLE_OF_DROPLETS_29', 'ROOM_TEMPLE_OF_DROPLETS_MULLDOZERS_FIRE_BARS', 'ROOM_TEMPLE_OF_DROPLETS_DARK_MAZE', 'ROOM_TEMPLE_OF_DROPLETS_TWIN_MADDERPILLARS', 'ROOM_TEMPLE_OF_DROPLETS_AFTER_TWIN_MADDERPILLARS', 'ROOM_TEMPLE_OF_DROPLETS_BLUE_CHU_KEY_LEVER', 'ROOM_TEMPLE_OF_DROPLETS_MULLDOZER_KEY', 'ROOM_TEMPLE_OF_DROPLETS_BEFORE_TWIN_MADDERPILLARS', 'ROOM_TEMPLE_OF_DROPLETS_LILYPAD_B2_WEST', 'ROOM_TEMPLE_OF_DROPLETS_COMPASS', 'ROOM_TEMPLE_OF_DROPLETS_DARK_SCISSOR_BEETLES', 'ROOM_TEMPLE_OF_DROPLETS_LILYPAD_B2_MIDDLE', 'ROOM_TEMPLE_OF_DROPLETS_ICE_MADDERPILLAR', 'ROOM_TEMPLE_OF_DROPLETS_FLAMEBAR_BLOCK_PUZZLE', 'ROOM_TEMPLE_OF_DROPLETS_37', 'ROOM_TEMPLE_OF_DROPLETS_38', 'ROOM_TEMPLE_OF_DROPLETS_39', 'ROOM_TEMPLE_OF_DROPLETS_3a', 'ROOM_TEMPLE_OF_DROPLETS_3b', 'ROOM_TEMPLE_OF_DROPLETS_3c', 'ROOM_TEMPLE_OF_DROPLETS_3d', 'ROOM_TEMPLE_OF_DROPLETS_3e', 'ROOM_TEMPLE_OF_DROPLETS_3f' ],
[ 'ROOM_NULL_61_0' ],
[ 'ROOM_HYRULE_TOWN_MINISH_CAVES_0', 'ROOM_HYRULE_TOWN_MINISH_CAVES_1', 'ROOM_HYRULE_TOWN_MINISH_CAVES_2', 'ROOM_HYRULE_TOWN_MINISH_CAVES_3', 'ROOM_HYRULE_TOWN_MINISH_CAVES_4', 'ROOM_HYRULE_TOWN_MINISH_CAVES_5', 'ROOM_HYRULE_TOWN_MINISH_CAVES_unused_0', 'ROOM_HYRULE_TOWN_MINISH_CAVES_unused_1', 'ROOM_HYRULE_TOWN_MINISH_CAVES_unused_2', 'ROOM_HYRULE_TOWN_MINISH_CAVES_unused_3', 'ROOM_HYRULE_TOWN_MINISH_CAVES_unused_4', 'ROOM_HYRULE_TOWN_MINISH_CAVES_unused_5', 'ROOM_HYRULE_TOWN_MINISH_CAVES_unused_6', 'ROOM_HYRULE_TOWN_MINISH_CAVES_unused_7', 'ROOM_HYRULE_TOWN_MINISH_CAVES_unused_8', 'ROOM_HYRULE_TOWN_MINISH_CAVES_unused_9', 'ROOM_HYRULE_TOWN_MINISH_CAVES_unused_10', 'ROOM_HYRULE_TOWN_MINISH_CAVES_6', 'ROOM_HYRULE_TOWN_MINISH_CAVES_7', 'ROOM_HYRULE_TOWN_MINISH_CAVES_8', 'ROOM_HYRULE_TOWN_MINISH_CAVES_9', 'ROOM_HYRULE_TOWN_MINISH_CAVES_10',],
[ 'ROOM_NULL_63_0' ],
[ 'ROOM_NULL_64_0' ],
[ 'ROOM_NULL_65_0' ],
[ 'ROOM_NULL_66_0' ],
[ 'ROOM_67_0', 'ROOM_67_1', 'ROOM_67_2', 'ROOM_67_3', 'ROOM_67_4', 'ROOM_67_5',],
[ 'ROOM_ROYAL_CRYPT_0', 'ROOM_ROYAL_CRYPT_WATER_ROPE', 'ROOM_ROYAL_CRYPT_GIBDO', 'ROOM_ROYAL_CRYPT_3', 'ROOM_ROYAL_CRYPT_KEY_BLOCK', 'ROOM_ROYAL_CRYPT_5', 'ROOM_ROYAL_CRYPT_6', 'ROOM_ROYAL_CRYPT_MUSHROOM_PIT', 'ROOM_ROYAL_CRYPT_ENTRANCE' ],
[ 'ROOM_NULL_69_0' ],
[ 'ROOM_NULL_6A_0' ],
[ 'ROOM_NULL_6B_0' ],
[ 'ROOM_NULL_6C_0' ],
[ 'ROOM_NULL_6D_0' ],
[ 'ROOM_NULL_6E_0' ],
[ 'ROOM_6F_0' ],
[ 'ROOM_PALACE_OF_WINDS_GYORG_TORNADO', 'ROOM_PALACE_OF_WINDS_BOSS_KEY', 'ROOM_PALACE_OF_WINDS_BEFORE_BALL_AND_CHAIN_SOLDIERS', 'ROOM_PALACE_OF_WINDS_GYORG_BOSS_DOOR', 'ROOM_PALACE_OF_WINDS_EAST_CHEST_FROM_GYORG_BOSS_DOOR', 'ROOM_PALACE_OF_WINDS_MOBLIN_AND_WIZZROBE_FIGHT', 'ROOM_PALACE_OF_WINDS_FOUR_BUTTON_STALFOS', 'ROOM_PALACE_OF_WINDS_FAN_AND_KEY_TO_BOSS_KEY', 'ROOM_PALACE_OF_WINDS_BALL_AND_CHAIN_SOLDIERS', 'ROOM_PALACE_OF_WINDS_BOMBAROSSA_PATH', 'ROOM_PALACE_OF_WINDS_HOLE_TO_DARKNUT', 'ROOM_PALACE_OF_WINDS_TO_BOMBAROSSA_PATH', 'ROOM_PALACE_OF_WINDS_DARKNUT_MINIBOSS', 'ROOM_PALACE_OF_WINDS_BOMB_WALL_INSIDE', 'ROOM_PALACE_OF_WINDS_BOMB_WALL_OUTSIDE', 'ROOM_PALACE_OF_WINDS_CLOUD_JUMPS', 'ROOM_PALACE_OF_WINDS_BLOCK_MAZE_TO_BOSS_DOOR', 'ROOM_PALACE_OF_WINDS_CRACKED_FLOOR_LAKITU', 'ROOM_PALACE_OF_WINDS_HEART_PIECE_BRIDGE', 'ROOM_PALACE_OF_WINDS_FAN_BRIDGE', 'ROOM_PALACE_OF_WINDS_TO_FAN_BRIDGE', 'ROOM_PALACE_OF_WINDS_RED_WARP_HALL', 'ROOM_PALACE_OF_WINDS_PLATFORM_CLONE_RIDE', 'ROOM_PALACE_OF_WINDS_PIT_CORNER_AFTER_KEY', 'ROOM_PALACE_OF_WINDS_PLATFORM_CROW_RIDE', 'ROOM_PALACE_OF_WINDS_GRATE_PLATFORM_RIDE', 'ROOM_PALACE_OF_WINDS_POT_PUSH', 'ROOM_PALACE_OF_WINDS_FLOORMASTER_LEVER', 'ROOM_PALACE_OF_WINDS_MAP', 'ROOM_PALACE_OF_WINDS_CORNER_TO_MAP', 'ROOM_PALACE_OF_WINDS_STAIRS_AFTER_FLOORMASTER', 'ROOM_PALACE_OF_WINDS_HOLE_TO_KINSTONE_WIZZROBE', 'ROOM_PALACE_OF_WINDS_KEY_ARROW_BUTTON', 'ROOM_PALACE_OF_WINDS_GRATES_TO_3F', 'ROOM_PALACE_OF_WINDS_SPINY_FIGHT', 'ROOM_PALACE_OF_WINDS_PEAHAT_SWITCH', 'ROOM_PALACE_OF_WINDS_WHIRLWIND_BOMBAROSSA', 'ROOM_PALACE_OF_WINDS_DOOR_TO_STALFOS_FIREBAR', 'ROOM_PALACE_OF_WINDS_STALFOS_FIREBAR_HOLE', 'ROOM_PALACE_OF_WINDS_SHORTCUT_DOOR_BUTTONS', 'ROOM_PALACE_OF_WINDS_TO_PEAHAT_SWITCH', 'ROOM_PALACE_OF_WINDS_KINSTONE_WIZZROBE_FIGHT', 'ROOM_PALACE_OF_WINDS_GIBDO_STAIRS', 'ROOM_PALACE_OF_WINDS_SPIKE_BAR_SMALL_KEY', 'ROOM_PALACE_OF_WINDS_ROC_CAPE', 'ROOM_PALACE_OF_WINDS_FIRE_BAR_GRATES', 'ROOM_PALACE_OF_WINDS_PLATFORM_RIDE_BOMBAROSSAS', 'ROOM_PALACE_OF_WINDS_BRIDGE_AFTER_DARKNUT', 'ROOM_PALACE_OF_WINDS_BRIDGE_SWITCHES_CLONE_BLOCK', 'ROOM_PALACE_OF_WINDS_ENTRANCE_ROOM', 'ROOM_PALACE_OF_WINDS_DARK_COMPASS_HALL', 'ROOM_PALACE_OF_WINDS_33' ],
[ 'ROOM_PALACE_OF_WINDS_BOSS_0' ],
[ 'ROOM_NULL_72_0' ],
[ 'ROOM_NULL_73_0' ],
[ 'ROOM_NULL_74_0' ],
[ 'ROOM_NULL_75_0' ],
[ 'ROOM_NULL_76_0' ],
[ 'ROOM_77_0' ],
[ 'ROOM_SANCTUARY_HALL', 'ROOM_SANCTUARY_MAIN', 'ROOM_SANCTUARY_STAINED_GLASS' ],
[ 'ROOM_NULL_79_0' ],
[ 'ROOM_NULL_7A_0' ],
[ 'ROOM_NULL_7B_0' ],
[ 'ROOM_NULL_7C_0' ],
[ 'ROOM_NULL_7D_0' ],
[ 'ROOM_NULL_7E_0' ],
[ 'ROOM_7F_0' ],
[ 'ROOM_HYRULE_CASTLE_0', 'ROOM_HYRULE_CASTLE_1', 'ROOM_HYRULE_CASTLE_2', 'ROOM_HYRULE_CASTLE_3', 'ROOM_HYRULE_CASTLE_4', 'ROOM_HYRULE_CASTLE_5', 'ROOM_HYRULE_CASTLE_6', 'ROOM_HYRULE_CASTLE_7' ],
[ 'ROOM_SANCTUARY_ENTRANCE_MAIN' ],
[ 'ROOM_NULL_82_0' ],
[ 'ROOM_NULL_83_0' ],
[ 'ROOM_NULL_84_0' ],
[ 'ROOM_NULL_85_0' ],
[ 'ROOM_NULL_86_0' ],
[ 'ROOM_87_0' ],
[ 'ROOM_DARK_HYRULE_CASTLE_1F_ENTRANCE', 'ROOM_DARK_HYRULE_CASTLE_3F_TOP_LEFT_TOWER', 'ROOM_DARK_HYRULE_CASTLE_3F_TOP_RIGHT_TOWER', 'ROOM_DARK_HYRULE_CASTLE_3F_BOTTOM_LEFT_TOWER', 'ROOM_DARK_HYRULE_CASTLE_3F_BOTTOM_RIGHT_TOWER', 'ROOM_DARK_HYRULE_CASTLE_3F_KEATON_HALL_TO_VAATI', 'ROOM_DARK_HYRULE_CASTLE_3F_TRIPLE_DARKNUT', 'ROOM_DARK_HYRULE_CASTLE_2F_TOP_LEFT_TOWER', 'ROOM_DARK_HYRULE_CASTLE_2F_TOP_LEFT_CORNER', 'ROOM_DARK_HYRULE_CASTLE_2F_BOSS_KEY', 'ROOM_DARK_HYRULE_CASTLE_2F_BLUE_WARP', 'ROOM_DARK_HYRULE_CASTLE_2F_TOP_RIGHT_CORNER_GHINI', 'ROOM_DARK_HYRULE_CASTLE_2F_TOP_RIGHT_CORNER_TORCHES', 'ROOM_DARK_HYRULE_CASTLE_2F_TOP_RIGHT_TOWER', 'ROOM_DARK_HYRULE_CASTLE_2F_TOP_LEFT_DARKNUT', 'ROOM_DARK_HYRULE_CASTLE_2F_SPARKS', 'ROOM_DARK_HYRULE_CASTLE_2F_TOP_RIGHT_DARKNUTS', 'ROOM_DARK_HYRULE_CASTLE_2F_LEFT', 'ROOM_DARK_HYRULE_CASTLE_2F_RIGHT', 'ROOM_DARK_HYRULE_CASTLE_2F_BOTTOM_LEFT_DARKNUTS', 'ROOM_DARK_HYRULE_CASTLE_2F_BOSS_DOOR', 'ROOM_DARK_HYRULE_CASTLE_2F_BOTTOM_RIGHT_DARKNUT', 'ROOM_DARK_HYRULE_CASTLE_2F_BOTTOM_LEFT_CORNER_PUZZLE', 'ROOM_DARK_HYRULE_CASTLE_2F_ENTRANCE', 'ROOM_DARK_HYRULE_CASTLE_2F_BOTTOM_RIGHT_CORNER', 'ROOM_DARK_HYRULE_CASTLE_2F_BOTTOM_LEFT_TOWER', 'ROOM_DARK_HYRULE_CASTLE_2F_BOTTOM_LEFT_GHINI', 'ROOM_DARK_HYRULE_CASTLE_1b', 'ROOM_DARK_HYRULE_CASTLE_B1_ENTRANCE', 'ROOM_DARK_HYRULE_CASTLE_2F_BOTTOM_RIGHT_TOWER', 'ROOM_DARK_HYRULE_CASTLE_1F_TOP_LEFT_TOWER', 'ROOM_DARK_HYRULE_CASTLE_1F_THRONE_ROOM', 'ROOM_DARK_HYRULE_CASTLE_1F_COMPASS', 'ROOM_DARK_HYRULE_CASTLE_1F_TOP_RIGHT_TOWER', 'ROOM_DARK_HYRULE_CASTLE_1F_BEFORE_THRONE', 'ROOM_DARK_HYRULE_CASTLE_1F_LOOP_TOP_LEFT', 'ROOM_DARK_HYRULE_CASTLE_1F_LOOP_TOP', 'ROOM_DARK_HYRULE_CASTLE_1F_LOOP_TOP_RIGHT', 'ROOM_DARK_HYRULE_CASTLE_1F_LOOP_LEFT', 'ROOM_DARK_HYRULE_CASTLE_1F_LOOP_RIGHT', 'ROOM_DARK_HYRULE_CASTLE_1F_LOOP_BOTTOM_LEFT', 'ROOM_DARK_HYRULE_CASTLE_1F_LOOP_BOTTOM', 'ROOM_DARK_HYRULE_CASTLE_1F_LOOP_BOTTOM_RIGHT', 'ROOM_DARK_HYRULE_CASTLE_1F_BOTTOM_LEFT_TOWER', 'ROOM_DARK_HYRULE_CASTLE_1F_BOTTOM_RIGHT_TOWER', 'ROOM_DARK_HYRULE_CASTLE_B1_BELOW_THRONE', 'ROOM_DARK_HYRULE_CASTLE_B1_BELOW_COMPASS', 'ROOM_DARK_HYRULE_CASTLE_B1_BEFORE_THRONE', 'ROOM_DARK_HYRULE_CASTLE_B1_TO_PRISON', 'ROOM_DARK_HYRULE_CASTLE_B1_BOMB_WALL', 'ROOM_DARK_HYRULE_CASTLE_B1_KEATONS', 'ROOM_DARK_HYRULE_CASTLE_B1_TO_PRISON_FIREBAR', 'ROOM_DARK_HYRULE_CASTLE_B1_CANNONS', 'ROOM_DARK_HYRULE_CASTLE_B1_LEFT', 'ROOM_DARK_HYRULE_CASTLE_B1_RIGHT', 'ROOM_DARK_HYRULE_CASTLE_B1_MAP', 'ROOM_DARK_HYRULE_CASTLE_B2_TO_PRISON', 'ROOM_DARK_HYRULE_CASTLE_B2_PRISON', 'ROOM_DARK_HYRULE_CASTLE_B2_DROPDOWN', 'ROOM_DARK_HYRULE_CASTLE_3b', 'ROOM_DARK_HYRULE_CASTLE_3c', 'ROOM_DARK_HYRULE_CASTLE_3d', 'ROOM_DARK_HYRULE_CASTLE_3e', 'ROOM_DARK_HYRULE_CASTLE_3f' ],
[ 'ROOM_DARK_HYRULE_CASTLE_OUTSIDE_ZELDA_STATUE_PLATFORM', 'ROOM_DARK_HYRULE_CASTLE_OUTSIDE_GARDEN', 'ROOM_DARK_HYRULE_CASTLE_OUTSIDE_NORTHWEST', 'ROOM_DARK_HYRULE_CASTLE_OUTSIDE_NORTHEAST', 'ROOM_DARK_HYRULE_CASTLE_OUTSIDE_EAST', 'ROOM_DARK_HYRULE_CASTLE_OUTSIDE_SOUTHWEST', 'ROOM_DARK_HYRULE_CASTLE_OUTSIDE_SOUTH', 'ROOM_DARK_HYRULE_CASTLE_OUTSIDE_SOUTHEAST', 'ROOM_DARK_HYRULE_CASTLE_OUTSIDE_8' ],
[ 'ROOM_VAATIS_ARMS_FIRST', 'ROOM_VAATIS_ARMS_SECOND', 'ROOM_VAATIS_ARMS_3' ],
[ 'ROOM_VAATI_3_0', 'ROOM_VAATI_3_1' ],
[ 'ROOM_VAATI_2_0' ],
[ 'ROOM_DARK_HYRULE_CASTLE_BRIDGE_MAIN' ],
[ 'ROOM_NULL_8E_0' ],
[ 'ROOM_8F_0' ]
]
    def slot_convert_area_room(self) -> None:
        text = QApplication.clipboard().text()
        lines = text.split('\n')
        result = []
        for line in lines:
            arr = line.split(',')
            if len(arr) != 2:
                print('Needs to be: area, room')
                return
            area = int(arr[0], 0)
            room = int(arr[1], 0)
            result.append(f'{self.area_ids[area]}, {self.room_ids[area][room]}')
        result_str = '\n'.join(result)
        QApplication.clipboard().setText(result_str)
        print(result_str)

    bank_ids = ['LOCAL_BANK_G', 'LOCAL_BANK_0', 'LOCAL_BANK_1', 'LOCAL_BANK_2', 'LOCAL_BANK_3', 'LOCAL_BANK_4', 'LOCAL_BANK_5', 'LOCAL_BANK_6', 'LOCAL_BANK_7', 'LOCAL_BANK_8', 'LOCAL_BANK_9', 'LOCAL_BANK_10', 'LOCAL_BANK_11', 'LOCAL_BANK_12', ]
    flag_ids = [
        ['BEGIN', 'LV0_CLEAR', 'LV1_CLEAR', 'LV2_CLEAR', 'LV3_CLEAR', 'LV4_CLEAR', 'LV5_CLEAR', 'LV6_CLEAR', 'LV7_CLEAR', 'LV8_CLEAR', 'MACHI_SET_1', 'MACHI_SET_2', 'MACHI_SET_3', 'MACHI_SET_4', 'MACHI_SET_5', 'MACHI_SET_6', 'MACHI_SET_7', 'MACHI_SET_8', 'MACHI_MACHIHOKORI', 'START', 'EZERO_1ST', 'TABIDACHI', 'LV1TARU', 'LV1TARU_OPEN', 'TATEKAKE_HOUSE', 'TATEKAKE_TOCHU', 'WATERBEAN_OUT', 'WATERBEAN_PUT', 'ZELDA_CHASE', 'INLOCK', 'DASHBOOTS', 'LEFT_DOOR_OPEN', 'HAKA_KEY_LOST', 'HAKA_KEY_FOUND', 'ENTRANCE_OK', 'TATSUMAKI', 'KUMOTATSUMAKI', 'KAITENGIRI', 'DAIKAITENGIRI', 'GATOTSU', 'KABUTOWARI', 'MIZUKAKI_START', 'MIZUKAKI_HARIFALL', 'RENTED_HOUSE_DIN', 'RENTED_HOUSE_NAYRU', 'RENTED_HOUSE_FARORE', 'NEW_HOUSE_DIN', 'NEW_HOUSE_NAYRU', 'NEW_HOUSE_FARORE', 'OUGONTEKI_A', 'OUGONTEKI_B', 'OUGONTEKI_C', 'OUGONTEKI_D', 'OUGONTEKI_E', 'OUGONTEKI_F', 'OUGONTEKI_G', 'OUGONTEKI_H', 'OUGONTEKI_I', 'KAKERA_COMPLETE', 'DRUG_1', 'DRUG_2', 'DRUG_3', 'GORON_KAKERA_LV2', 'GORON_KAKERA_LV3', 'GORON_KAKERA_LV4', 'GORON_KAKERA_LV5', 'GORON_KAKERA_L', 'GORON_KAKERA_M', 'GORON_KAKERA_R', 'CHIKATSURO_SHUTTER', 'ENTRANCE_USED', 'GOMAN_RENTED_HOUSE', 'GOMAN_NEW_HOUSE', 'OUTDOOR', 'POWERGLOVE_HINT', 'ANJU_LV_BIT0', 'ANJU_LV_BIT1', 'ANJU_LV_BIT2', 'ANJU_LV_BIT3', 'ANJU_HEART', 'MAROYA_WAKEUP', 'ENDING', 'WARP_1ST', 'WARP_MONUMENT', 'DRUG_COUNT', 'GAMECLEAR', 'WHITE_SWORD_END', 'SOUGEN_06_HASHIGO', 'WARP_EVENT_END', 'FIGURE_ALLCOMP', 'AKINDO_BOTTLE_SELL', 'BIN_DOGFOOD', 'TINGLE_TALK1ST', 'SEIIKI_BGM', 'ENTRANCE_0', 'ENTRANCE_1', 'ENTRANCE_2', 'MIZUKAKI_NECHAN', 'MAZE_CLEAR', 'TINY_ENTRANCE', 'CASTLE_BGM', ],
        ['BEGIN_1', 'LV1_CLEAR_MES', 'LV2_CLEAR_MES', 'LV3_CLEAR_MES', 'LV4_CLEAR_MES', 'LV5_CLEAR_MES', 'MIZUUMI_00_BENT', 'MIZUUMI_00_00', 'MIZUUMI_00_H00', 'MIZUUMI_00_H01', 'MIZUUMI_00_H02', 'MIZUUMI_00_CAP_0', 'MAENIWA_00_00', 'MAENIWA_00_01', 'MAENIWA_00_02', 'MAENIWA_00_BENT', 'MAENIWA_00_WARP', 'MAENIWA_00_T0', 'MAENIWA_00_T1', 'MAENIWA_00_CAP_0', 'NAKANIWA_00_EZERO', 'HIKYOU_00_00', 'HIKYOU_00_01', 'HIKYOU_00_02', 'HIKYOU_00_03', 'HIKYOU_00_04', 'HIKYOU_00_CAP_0', 'HIKYOU_00_CAP_1', 'HIKYOU_00_CAP_2', 'HIKYOU_00_SEKIZOU', 'HIKYOU_00_14', 'HIKYOU_00_BOSEKI', 'HIKYOU_00_M0', 'HIKYOU_00_M1', 'HIKYOU_00_M2', 'HIKYOU_00_T1', 'LOST_00_ENTER', 'LOST_00_00', 'LOST_00_01', 'LOST_02_00', 'LOST_03_00', 'LOST_03_T0', 'LOST_04_00', 'LOST_04_SIBA0', 'LOST_04_SIBA1', 'LOST_04_SIBA2', 'LOST_04_SIBA3', 'LOST_04_SIBA4', 'LOST_05_00', 'LOST_05_01', 'LOST_05_02', 'LOST_05_03', 'LOST_05_T0', 'LOST_05_T1', 'MORI_00_HIBI_0', 'MORI_00_HIBI_1', 'MORI_00_HIBI_2', 'MORI_00_HIBI_3', 'MORI_00_HIBI_4', 'MORI_00_KOBITO', 'MORI_00_H0', 'MORI_00_H1', 'MORI_ENTRANCE_1ST', 'YAMA_00_00', 'YAMA_00_01', 'YAMA_01_BW00', 'YAMA_02_00', 'YAMA_03_00', 'YAMA_03_01', 'YAMA_03_02', 'YAMA_03_DOKU_0', 'YAMA_03_DOKU_1', 'YAMA_03_DOKU_2', 'YAMA_04_CAP_0', 'YAMA_04_CAP_1', 'YAMA_04_R00', 'YAMA_04_HIBI_0', 'YAMA_04_HIBI_1', 'YAMA_04_00', 'YAMA_04_01', 'YAMA_04_04', 'YAMA_04_05', 'YAMA_04_06', 'YAMA_04_ENTHOUSHI', 'YAMA_04_ANAHOUSHI', 'YAMA_04_BOMBWALL0', 'HAKA_BUNSHIN_00', 'HAKA_BOSEKI_00', 'HAKA_BOSEKI_01', 'HAKA_BOSEKI_02', 'HAKA_00_CAP_0', 'HAKA_00_BW00', 'HAKA_01_T0', 'HAKA_KEY_GET', 'SOUGEN_01_WAKAGI_0', 'SOUGEN_01_WAKAGI_1', 'SOUGEN_01_WAKAGI_2', 'SOUGEN_01_WAKAGI_3', 'SOUGEN_01_WAKAGI_4', 'SOUGEN_01_WAKAGI_5', 'SOUGEN_01_WAKAGI_6', 'SOUGEN_01_WAKAGI_7', 'SOUGEN_01_WAKAGI_8', 'SOUGEN_01_WAKAGI_9', 'SOUGEN_01_WAKAGI_10', 'SOUGEN_01_WAKAGI_11', 'SOUGEN_01_WAKAGI_12', 'SOUGEN_01_00', 'SOUGEN_01_BENT', 'SOUGEN_01_ZELDA', 'SOUGEN_02_HIBI_0', 'SOUGEN_02_HIBI_1', 'SOUGEN_03_BOMBWALL', 'SOUGEN_04_HIBI_0', 'SOUGEN_04_HIBI_1', 'SOUGEN_04_HIBI_2', 'SOUGEN_04_HIBI_3', 'SOUGEN_05_HIBI_0', 'SOUGEN_05_HIBI_1', 'SOUGEN_05_HIBI_2', 'SOUGEN_05_HIBI_3', 'SOUGEN_05_BOMB_00', 'SOUGEN_05_00', 'SOUGEN_05_01', 'SOUGEN_05_IWA02', 'SOUGEN_05_BENT', 'SOUGEN_05_H00', 'SOUGEN_05_R0', 'SOUGEN_05_CAP_0', 'SOUGEN_06_WAKAGI_0', 'SOUGEN_06_WAKAGI_1', 'SOUGEN_06_WAKAGI_2', 'SOUGEN_06_WAKAGI_3', 'SOUGEN_06_HIBI_0', 'SOUGEN_06_HIBI_1', 'SOUGEN_06_HIBI_2', 'SOUGEN_06_HIBI_3', 'SOUGEN_06_HIBI_4', 'SOUGEN_06_IWA_0', 'SOUGEN_06_AKINDO', 'SOUGEN_06_SAIKAI', 'SOUGEN_06_BENT', 'SOUGEN_06_SLIDE', 'SOUGEN_06_R1', 'SOUGEN_07_00', 'SOUGEN_07_01', 'SOUGEN_07_02', 'SOUGEN_08_00', 'SOUGEN_08_01', 'SOUGEN_08_02', 'SOUGEN_08_03', 'SOUGEN_08_04', 'SOUGEN_08_05', 'SOUGEN_08_06', 'SOUGEN_08_07', 'SOUGEN_08_08', 'SOUGEN_08_TORITSUKI', 'SOUGEN_08_T00', 'CASTLE_00_00', 'CASTLE_04_MEZAME', 'CASTLE_04_MAID_TALK', 'SUIGEN_00_h0', 'SUIGEN_00_T0', 'SUIGEN_00_r0', 'SUIGEN_00_r1', 'SUIGEN_00_r2', 'SUIGEN_00_CAP_0', 'SUIGEN_00_CAP_1', 'SUIGEN_00_R0', 'SUIGEN_00_R1', 'SUIGEN_00_R2', 'SUIGEN_00_h1', 'SUIGENGORON_00_CAP_0', 'DAIGORON_SHIELD', 'DAIGORON_EXCHG', 'BEANDEMO_00', 'BEANDEMO_01', 'BEANDEMO_02', 'BEANDEMO_03', 'BEANDEMO_04', 'KAKERA_TAKARA_A', 'KAKERA_TAKARA_E', 'KAKERA_TAKARA_J', 'KAKERA_TAKARA_K', 'KAKERA_TAKARA_L', 'KAKERA_TAKARA_M', 'KAKERA_TAKARA_N', 'KAKERA_TAKARA_O', 'KAKERA_TAKARA_P', 'KAKERA_TAKARA_Q', 'KAKERA_TAKARA_R', 'KAKERA_TAKARA_S', 'KAKERA_TAKARA_T', 'KAKERA_TAKARA_U', 'KAKERA_TAKARA_V', 'KAKERA_TAKARA_W', 'KAKERA_TAKARA_X', 'KAKERA_TAKARA_Y', 'KAKERA_TAKARA_Z', 'MACHI_02_HEISHI_TALK', 'MACHI00_00', 'MACHI00_02', 'MACHI00_03', 'MACHI_00_T00', 'MACHI_00_T01', 'MACHI_01_DEMO', 'MACHI_02_HEISHI', 'MACHI_02_DOG', 'MACHI_07_BELL', 'SHOP05_OPEN', 'MACHI_MES_20', 'MACHI_MES_21', 'MACHI_MES_22', 'MACHI_MES_23', 'MACHI_MES_24', 'MACHI_MES_30', 'MACHI_MES_40', 'MACHI_MES_60', 'MACHI_MES_50', 'MACHI_DOG_C', 'KUMOUE_00_CAP_0', 'KUMOUE_01_CAP_0', 'KUMOUE_01_T0', 'KUMOUE_01_T1', 'KUMOUE_01_T2', 'KUMOUE_01_T3', 'KUMOUE_01_T4', 'KUMOUE_01_T5', 'KUMOUE_01_T6', 'KUMOUR_01_K0', 'KUMOUR_01_K1', 'KUMOUR_01_K2', 'KUMOUR_01_K3', 'KUMOUR_01_K4', 'KUMOUR_01_K5', 'KUMOUR_01_K6', 'KUMONOUE_01_KAKERA', 'KUMOUE_02_CAP_0', 'KUMOUE_02_AWASE_01', 'KUMOUE_02_AWASE_02', 'KUMOUE_02_AWASE_03', 'KUMOUE_02_AWASE_04', 'KUMOUE_02_AWASE_05', 'KUMOUE_02_00', 'KUMOUE_02_01', 'KUMOUE_02_02', 'KUMOUE_02_03', 'KUMOUE_UNCLE_TALK', 'KUMOUE_GIRL_TALK', 'KS_A06', 'KS_B18', 'KS_C21', 'KS_C25', 'END_1', ],
        ['BEGIN_2', 'BILL05_YADO1F_MATSU_T0', 'BILL06_YADO1F_TAKE_T0', 'BILL07_YADO1F_UME_T0', 'BILL0A_YADO_TAKARA_T0', 'SHOUSE_00_T0', 'SHOUSE_00_T1', 'SHOUSE_01_T0', 'SHOUSE_02_T0', 'SHOUSE_02_T1', 'SHOUSE_02_T2', 'SHOUSE_02_XXXX0', 'SHOUSE_02_XXXX1', 'SHOUSE_02_XXXX2', 'SHOUSE_03_T0', 'SHOUSE_03_T1', 'KOBITOANA_06_T0', 'KOBITOANA_03_T0', 'KOBITOANA_07_T0', 'KOBITOANA_09_T0', 'KOBITOANA_0A_T0', 'KOBITOANA_0B_T0', 'MHOUSE11_T0', 'URO_08_T0', 'URO_0A_T0', 'URO_0B_T0', 'BILL00_SHICHOU_00', 'BILL00_SHICHOU_01', 'BILL00_SHICHOU_02', 'BILL00_SHICHOU_03', 'BILL00_SHICHOU_04', 'BILL01_TESSIN_1', 'BILL01_TESSIN_2', 'BILL01_TESSIN_3', 'BILL01_TESSIN_4', 'BILL01_TESSIN_5', 'BILL01_TESSIN_6', 'BILL01_TESSIN_7', 'BILL01_TESSIN_8', 'BILL09_YADO2F_POEMN', 'BILL0A_YADO_TAKARA_00', 'BILL0B_SCHOOLL_00', 'BILL0C_SCHOOLR_00', 'MHOUSE00_00', 'MHOUSE00_01', 'MHOUSE00_02', 'MHOUSE00_03', 'MHOUSE00_04', 'MHOUSE00_05', 'MHOUSE01_00', 'MHOUSE01_01', 'MHOUSE01_02', 'MHOUSE01_03', 'MHOUSE03_00', 'MHOUSE03_01', 'MHOUSE04_00', 'MHOUSE04_01', 'MHOUSE04_02', 'MHOUSE04_03', 'MHOUSE04_04', 'MHOUSE06_00', 'MHOUSE07_00', 'MHOUSE07_01', 'MHOUSE08_00', 'MHOUSE08_01', 'MHOUSE08_02', 'MHOUSE08_03', 'MHOUSE08_04', 'MHOUSE0C_00', 'MHOUSE14_00', 'MHOUSE15_OP1ST', 'MHOUSE2_00_00', 'MHOUSE2_00_01', 'MHOUSE2_00_02', 'MHOUSE2_00_03', 'MHOUSE2_01_T0', 'MHOUSE2_02_KAME', 'MHOUSE2_02_KEY', 'MHOUSE2_03_00', 'MHOUSE2_05_00', 'SHOP00_ITEM_00', 'SHOP00_ITEM_01', 'SHOP00_ITEM_02', 'SHOP00_ITEM_03', 'SHOP00_ITEM_04', 'SHOP00_SAIFU', 'SHOP00_YAZUTSU', 'SHOP01_CAFE_00', 'SHOP01_CAFE_01', 'SHOP01_TALK', 'HOUSE_XXXXX', 'SHOP03_PAN_1ST', 'SHOP07_TALK1ST', 'SHOP07_GACHAPON', 'SHOP07_TANA', 'SHOP07_COMPLETE', 'SHOP02_KUTSU_00', 'NPC37_REM_TALK1ST', 'NPC37_REM_SLEEP', 'SORA_ELDER_RECOVER', 'SORA_CHIEF_TALK', 'SORA_ELDER_TALK1ST', 'SORA_ELDER_TALK2ND', 'NPC06_19GUY_QUESTION', 'NPC06_19GUY_ANSWER', 'DANPEI_TALK1ST', 'MIZUKAKI_KOBITO', 'MIZUKAKI_HINT1', 'MIZUKAKI_BOOK1_FALL', 'MIZUKAKI_HINT2', 'MIZUKAKI_HINT2_2ND', 'MIZUKAKI_BOOK2_FALL', 'MIZUKAKI_HINT3', 'MIZUKAKI_HINT3_MAYOR', 'MIZUKAKI_BOOK3_FALL', 'MIZUKAKI_BOOK_ALLBACK', 'MIZUKAKI_STAIR', 'MIZUKAKI_STAIR_WARP_OK', 'KHOUSE27_00', 'NO_USE_00', 'KHOUSE51_00', 'NO_USE_01', 'KHOUSE51_02', 'KHOUSE42_00', 'NO_USE_02', 'NO_USE_03', 'OYAKATA_DEMO', 'YAMAKOBITO_OPEN', 'M_PRIEST_TALK', 'M_ELDER_TALK1ST', 'M_PRIEST_MOVE', 'M_ELDER_TALK2ND', 'MHOUSE04_DANRO', 'MHOUSE06_DANRO', 'URO_POEMN_TALK', 'MHOUSE06_MES_20', 'MHOUSE07_MES_20', 'MAYOR_2_TALK1ST', 'MAYOR_4_TALK1ST', 'BILL01_TESSIN_RESERVED', 'BILL01_TESSIN_BRANDNEW', 'KOBITO_MORI_1ST', 'KOBITO_YAMA_ENTER', 'KHOUSE52_KINOKO', 'SORA_YAKATA_ENTER', 'YADO_CHECKIN', 'MINIGAME_GAMEEND', 'MINIGAME_LEVEL2', 'MHOUSE_DIN_TALK', 'MHOUSE_NAYRU_TALK', 'MHOUSE_FARORE_TALK', 'URO_12_H0', 'URO_19_H0', 'URO_1F_H0', 'BILL09_TSW0', 'BILL09_TSW1', 'KHOUSE41_TALK1ST', 'TAIMA_SAIBAI_1ST', 'IZUMI_00_FAIRY', 'IZUMI_01_FAIRY', 'IZUMI_02_FAIRY', 'BILL0B_DOUZOU_L', 'BILL0B_DOUZOU_R', 'KOBITOANA_08_T0', 'KOBITOANA_0C_T0', 'KOBITOANA_0D_T0', 'KOBITOHOUSE_23_H0', 'MHOUSE08_DANRO', 'MHOUSE09_DANRO', 'MHOUSE0A_DANRO', 'MHOUSE0B_DANRO', 'MHOUSE0C_DANRO', 'MHOUSE12_DANRO', 'SORA_DANRO', 'MIZUKAKI_HINT3_MAP', 'LEFT_TALK', 'KHOUSE26_REMOCON', 'SORA_KIDS_MOVE', 'KOBITOANA_00_T0', 'KHOUSE23_TALK1ST', 'SHOP05_ELEMENT_H00', 'SHOP05_ELEMENT_T00', 'SHOP05_ELEMENT_T01', 'SHOP05_ELEMENT_T02', 'BILL0a_YADO_TAKARA_H00', 'KOBITOYAMA_00_R00', 'KOBITOYAMA_00_R01', 'KOBITOYAMA_00_R02', 'KOBITOYAMA_00_R03', 'KOBITOYAMA_00_R04', 'KOBITOYAMA_00_R05', 'KOBITOYAMA_00_R06', 'KOBITOYAMA_00_R07', 'KOBITO_MORI_00_H00', 'KOBITO_MORI_00_H0', 'CAFE_01_CAP_0', 'BILL_00_CAP_0', 'BILL_02_CAP_0', 'MHOUSE_07_CAP_0', 'MHOUSE_07_CAP_1', 'MHOUSE_10_CAP_0', 'MHOUSE_15_CAP_0', 'MHOUSE_15_CAP_1', 'SHOP_03_CAP_0', 'MHOUSE_07_CAP_2', 'SHOP00_BOMBBAG', 'CAFE_01_CAP_1', 'KS_A02', 'KS_A09', 'KS_A18', 'KS_B07', 'KS_B16', 'END_2', ],
        ['BEGIN_3', 'MAROYA_TAKARA', 'MACHI_CHIKA_00_00', 'MACHI_CHIKA_00_01', 'MACHI_CHIKA_00_02', 'MACHI_CHIKA_00_03', 'MACHI_CHIKA_00_T0', 'MACHI_CHIKA_00_T1', 'MACHI_CHIKA_00_T2', 'MACHI_CHIKA_00_T3', 'MACHI_CHIKA_00_T4', 'MACHI_CHIKA2_00_T0', 'MACHI_CHIKA2_01_T0', 'MACHI_CHIKA2_03_00', 'MACHI_CHIKA2_03_01', 'MACHI_CHIKA2_03_T0', 'MACHI_CHIKA2_04_T0', 'MACHI_CHIKA2_10_00', 'MACHI_CHIKA2_10_01', 'MACHI_CHIKA2_10_02', 'MACHI_CHIKA2_10_T0', 'MACHI_CHIKA2_12_T0', 'LV4_HAKA_05_T0', 'LV4_HAKA_04_T0', 'LV4_HAKA_04_T1', 'LV4_HAKA_01_00', 'LV4_HAKA_01_01', 'LV4_HAKA_03_00', 'LV4_HAKA_04_R0', 'LV4_HAKA_04_R1', 'LV4_HAKA_04_R2', 'LV4_HAKA_04_R3', 'LV4_HAKA_04_R4', 'LV4_HAKA_04_R5', 'LV4_HAKA_04_R6', 'LV4_HAKA_04_R8', 'LV4_HAKA_04_R9', 'LV4_HAKA_04_R10', 'LV4_HAKA_04_R11', 'LV4_HAKA_04_KB0', 'LV4_HAKA_04_KB1', 'LV4_HAKA_05_H0', 'LV4_HAKA_05_H1', 'LV4_HAKA_05_H2', 'LV4_HAKA_05_H3', 'OUBO_02_BW0', 'OUBO_02_BW1', 'OUBO_06_BW0', 'OUBO_06_BW1', 'OUBO_07_ENTER', 'OUBO_KAKERA', 'MOGURA_00_T0', 'MOGURA_00_T1', 'MOGURA_00_T2', 'MOGURA_01_T0', 'MOGURA_02_T0', 'MOGURA_02_T1', 'MOGURA_02_T2', 'MOGURA_02_T3', 'MOGURA_02_T4', 'MOGURA_02_T5', 'MOGURA_02_T6', 'MOGURA_02_T7', 'MOGURA_02_T8', 'MOGURA_09_T0', 'MOGURA_09_T1', 'MOGURA_10_T0', 'MOGURA_10_T1', 'MOGURA_10_T2', 'MOGURA_1c_T0', 'MOGURA_21_r0', 'MOGURA_27_T0', 'MOGURA_27_T1', 'MOGURA_27_T2', 'MOGURA_41_T0', 'MOGURA_41_T1', 'MOGURA_41_T2', 'MOGURA_41_T3', 'MOGURA_50_00', 'MOGURA_50_T0', 'MOGURA_51_T0', 'MOGURA_51_T1', 'MOGURA_51_T2', 'MOGURA_51_00', 'MOGURA_51_01', 'MOGURA_51_02', 'MOGURA_51_03', 'MOGURA_51_04', 'MOGURA_51_05', 'MOGURA_51_06', 'MOGURA_51_07', 'MOGURA_51_08', 'MOGURA_52_00', 'MOGURA_52_T0', 'MOGURA_52_T1', 'MOGURA_53_00', 'MOGURA_53_T0', 'MOGURA_53_T1', 'MOGURA_53_WALK', 'MOGURA_54_00', 'MOGURA_54_01', 'MOGURA_54_02', 'MOGURA_54_WALK', 'AMOS_00_00', 'AMOS_01_00', 'AMOS_02_00', 'AMOS_03_00', 'AMOS_04_00', 'AMOS_05_00', 'AMOS_06_00', 'AMOS_07_00', 'AMOS_08_00', 'AMOS_09_00', 'AMOS_0A_00', 'AMOS_0B_00', 'AMOS_0C_00', 'AMOS_0D_00', 'AMOS_0E_00', 'AMOS_0F_00', 'HARI_01_T0', 'SEIIKI_STAINED_GLASS', 'SEIIKI_ENTER', 'SEIIKI_SWORD_1ST', 'SEIIKI_SWORD_2ND', 'SEIIKI_SWORD_3RD', 'SEIIKI_BUNSHIN', 'BAGUZU_MORI_02_00', 'BAGUZU_MORI_02_T0', 'BAGUZU_MORI_02_T1', 'BAGUZU_MORI_02_T2', 'CHIKATSURO_01_BW00', 'SORA_10_H00', 'SORA_11_H00', 'SORA_11_T00', 'SORA_11_T01', 'SORA_12_T00', 'SORA_13_H00', 'SORA_13_T00', 'SORA_13_T01', 'SORA_14_T00', 'SORA_14_R00', 'SORA_14_R01', 'SORA_14_R02', 'SORA_14_R03', 'SORA_14_R04', 'SORA_14_R05', 'SORA_14_R06', 'SORA_14_R07', 'IZUMIGARE_00_H00', 'IZUMIGARE_00_H01', 'SORA_10_R00', 'SORA_10_R01', 'SORA_10_R02', 'SORA_10_R03', 'SORA_10_R04', 'SORA_10_R05', 'SORA_10_R06', 'SORA_10_R07', 'SORA_14_R08', 'SORA_14_R09', 'SORA_14_R0a', 'SORA_14_R0b', 'SORA_14_R0c', 'SORA_14_R0d', 'SORA_14_R0e', 'SORA_14_R0f', 'KAKERA_TAKARA_B', 'KAKERA_TAKARA_C', 'KAKERA_TAKARA_D', 'KAKERA_TAKARA_F', 'KAKERA_TAKARA_G', 'KAKERA_TAKARA_H', 'KAKERA_TAKARA_I', 'KAKERA_TAKARA_XXXX', 'TESTMAP00_00', 'TESTMAP01_00', 'TESTMAP01_01', 'TESTMAP02_00', 'LV4_HAKA_08_T0', 'LV4_HAKA_07_00', 'LV4_HAKA_04_00', 'LV4_HAKA_04_01', 'LV4_HAKA_04_K0', 'LV4_HAKA_04_K1', 'LV4_HAKA_01_02', 'LV4_HAKA_08_XX', 'BAGUZU_MORI_03_H00', 'MOGURAU_00_H00', 'HARI_01_H00', 'HARI_03_T00', 'MACHI_CHIKA2_00_CAP_0', 'MACHI_CHIKA2_11_CAP_0', 'LV4_HAKA_08_CAP_0', 'BAGUZUIWA_02_CAP_0', 'MACHI_CHIKA2_01_CAP_0', 'MACHI_CHIKA2_01_HK', 'LV4_HAKA_08_B0', 'LV4_HAKA_08_K0', 'MAROYA_1ST', 'MACHI_CHIKA2_10_CAP_0', 'KS_C02', 'END_3', ],
        ['BEGIN_4', 'DOUKUTU_00_T0', 'DOUKUTU_00_T1', 'DOUKUTU_05_EVENT', 'SOUGEN_DOUKUTU_00_T0', 'SOUGEN_DOUKUTU_00_T1', 'SOUGEN_DOUKUTU_00_T2', 'SOUGEN_DOUKUTU_00_T3', 'SOUGEN_DOUKUTU_00_T4', 'SOUGEN_DOUKUTU_00_SW0', 'SOUGEN_DOUKUTU_00_SW1', 'SOUGEN_DOUKUTU_00_SW2', 'SOUGEN_DOUKUTU_00_SW3', 'SOUGEN_DOUKUTU_07_T0', 'SOUGEN_DOUKUTU_0B_T0', 'SOUGEN_DOUKUTU_0C_T0', 'SOUGEN_DOUKUTU_0C_BW00', 'SOUGEN_DOUKUTU_0D_00', 'SOUGEN_DOUKUTU_0D_T0', 'SOUGEN_DOUKUTU_0E_BW00', 'SOUGEN_DOUKUTU_0F_T00', 'SOUGEN_DOUKUTU_10_R00', 'SOUGEN_DOUKUTU_10_R01', 'SOUGEN_DOUKUTU_10_R02', 'SOUGEN_DOUKUTU_10_R03', 'SOUGEN_DOUKUTU_10_R04', 'SOUGEN_DOUKUTU_10_R05', 'SOUGEN_DOUKUTU_10_R06', 'SOUGEN_DOUKUTU_10_R07', 'SOUGEN_DOUKUTU_10_R08', 'SOUGEN_DOUKUTU_10_R09', 'SOUGEN_DOUKUTU_10_R0A', 'SOUGEN_DOUKUTU_10_R0B', 'SOUGEN_DOUKUTU_10_R0C', 'SOUGEN_DOUKUTU_10_R0D', 'SOUGEN_DOUKUTU_10_R0E', 'SOUGEN_DOUKUTU_11_R00', 'SOUGEN_DOUKUTU_11_R01', 'SOUGEN_DOUKUTU_11_R02', 'SOUGEN_DOUKUTU_11_R03', 'SOUGEN_DOUKUTU_11_R04', 'SOUGEN_DOUKUTU_11_R05', 'SOUGEN_DOUKUTU_11_R06', 'SOUGEN_DOUKUTU_11_R07', 'SOUGEN_DOUKUTU_11_R08', 'SOUGEN_DOUKUTU_11_R09', 'SOUGEN_DOUKUTU_11_R0A', 'SOUGEN_DOUKUTU_11_R0B', 'SOUGEN_DOUKUTU_11_R0C', 'SOUGEN_DOUKUTU_11_R0D', 'SOUGEN_DOUKUTU_11_R0E', 'SOUGEN_DOUKUTU_13_T0', 'HIKYOU_DOUKUTU0_00_T0', 'HIKYOU_DOUKUTU0_01_T0', 'HIKYOU_DOUKUTU0_01_T1', 'HIKYOU_DOUKUTU0_02_KAIGARA', 'HIKYOU_DOUKUTU0_04_H00', 'HIKYOU_DOUKUTU1_00_00', 'HIKYOU_DOUKUTU1_00_T0', 'YAMADOUKUTU_01_00', 'YAMADOUKUTU_02_00', 'YAMADOUKUTU_03_T0', 'YAMADOUKUTU_06_H0', 'YAMADOUKUTU_07_T0', 'YAMADOUKUTU_08_h0', 'YAMADOUKUTU_08_h1', 'YAMADOUKUTU_08_h2', 'YAMADOUKUTU_09_r0', 'YAMADOUKUTU_09_r1', 'YAMADOUKUTU_09_r2', 'YAMADOUKUTU_0F_00', 'YAMADOUKUTU_10_00', 'SUIGEN_DOUKUTU_00_T0', 'SUIGEN_DOUKUTU_01_BW00', 'SUIGEN_DOUKUTU_02_T0', 'SUIGEN_DOUKUTU_04_BW00', 'SUIGEN_DOUKUTU_05_T0', 'SUIGEN_DOUKUTU_08_R0', 'SUIGEN_DOUKUTU_08_R1', 'SUIGEN_DOUKUTU_08_R2', 'SUIGEN_DOUKUTU_08_R3', 'SUIGEN_DOUKUTU_08_R4', 'SUIGEN_DOUKUTU_08_R5', 'SUIGEN_DOUKUTU_08_R6', 'SUIGEN_DOUKUTU_08_R7', 'SUIGEN_DOUKUTU_08_R8', 'SUIGEN_DOUKUTU_08_R9', 'SUIGEN_DOUKUTU_08_R10', 'SUIGEN_DOUKUTU_08_R11', 'SUIGEN_DOUKUTU_08_R12', 'SUIGEN_DOUKUTU_08_R13', 'SUIGEN_DOUKUTU_08_R14', 'SUIGEN_DOUKUTU_09_H00', 'HAKA_DOUKUTU_00_H0', 'HAKA_DOUKUTU_01_T0', 'HAKA_DOUKUTU_01_GEENE', 'KOBITO_DOUKUTU_00_T0', 'KOBITO_DOUKUTU_02_T0', 'KOBITO_DOUKUTU_05_T0', 'KOBITO_SHIRO_DOUKUTU_00_H0', 'KOBITO_SHIRO_DOUKUTU_00_T0', 'KOBITO_SHIRO_DOUKUTU_01_T0', 'KOBITO_URA_DOUKUTU_00_T0', 'KOBITO_URA_DOUKUTU_01_T0', 'GORON_DOUKUTU_APPEAR', 'KOBITO_DOUKUTU_03_T0', 'HIKYOU_DOUKUTU0_01_AKINDO', 'SOUGEN_DOUKUTU_14_AKINDO', 'SOUGEN_DOUKUTU_17_AKINDO', 'YAMADOUKUTU_04_AKINDO', 'YAMADOUKUTU_0D_AKINDO', 'YAMADOUKUTU_0F_AKINDO', 'YAMADOUKUTU_0E_SENNIN', 'KOBITO_DOUKUTU_04_T0', 'KOBITO_DOUKUTU_07_T0', 'KOBITO_DOUKUTU_09_T0', 'KOBITO_DOUKUTU_09_T1', 'KOBITO_DOUKUTU_09_T2', 'GORON_DOUKUTU_01_T0', 'GORON_DOUKUTU_01_T1', 'GORON_DOUKUTU_01_T2', 'GORON_DOUKUTU_01_T3', 'KOBITO_DOUKUTU_09_H0', 'SOUGEN_DOUKUTU_15_H0', 'KOBITO_DOUKUTU_01_H00', 'YAMADOUKUTU_05_H00', 'KOBITO_DOUKUTU_03_H00', 'DOUKUTU_04_H00', 'DOUKUTU_00_H00', 'KOBITO_DOUKUTU_04_H00', 'DOUKUTU_06_H00', 'DOUKUTU_05_H00', 'KOBITO_DOUKUTU_02_H00', 'KOBITO_DOUKUTU_01_T0', 'YAMADOUKUTU_04_CAP_0', 'KS_B06', 'KS_B15', 'KS_B01', 'KS_B12', 'KS_C12', 'KS_C37', 'END_4',],
    ]
    def slot_convert_local_flags(self) -> None:
        text = QApplication.clipboard().text()
        lines = text.split('\n')
        result = []
        for line in lines:
            arr = line.split(',')
            if len(arr) != 2:
                print('Needs to be: bank (gLocalFlags), flag')
                return
            bank = int(arr[0], 0)
            flag = int(arr[1], 0)
            if bank == 0:
                raise Exception('Bank 0 not used? Usually index 1 is provided?')
            result.append(f'{self.bank_ids[bank]}, {self.flag_ids[bank-1][flag]}')
        result_str = '\n'.join(result)
        QApplication.clipboard().setText(result_str)
        print(result_str)

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
    def slot_data_stats(self) -> None:
        print('\nStats:\n')
        gfx_length = 0
        animations_length = 0
        sound_length = 0
        map_length = 0
        strings_length = 0
        scripts_length = 0
        lengths = {}
        for symbol in self.current_controller.symbols.symbols:
            if symbol.file.startswith('data/'):
                if symbol.file.startswith('data/gfx'):
                    gfx_length += symbol.length
                    continue
                if symbol.file.startswith('data/animations'):
                    animations_length += symbol.length
                    continue
                if symbol.file.startswith('data/sound'):
                    sound_length += symbol.length
                    continue
                if symbol.file.startswith('data/map'):
                    map_length += symbol.length
                    continue
                if symbol.file.startswith('data/strings'):
                    strings_length += symbol.length
                    continue
                if symbol.file.startswith('data/scripts'):
                    scripts_length += symbol.length
                    continue

                if not symbol.file in lengths:
                    lengths[symbol.file] = 0
                lengths[symbol.file] += symbol.length

        print(f'gfx: {gfx_length}')
        print(f'animations: {animations_length}')
        print(f'sound: {sound_length}')
        print(f'map: {map_length}')
        print(f'strings: {strings_length}')
        print(f'scripts: {scripts_length}')
        remaining_length = 0
        for key in lengths:
            remaining_length += lengths[key]
        print(f'remaining: {remaining_length}')
        print('---')

        for file, length in sorted(lengths.items(), key=lambda x: x[1]):
            print(f'{file}: {length}')

    def slot_extract_dialog_list(self) -> None:
        symbol_name = QApplication.clipboard().text()
        symbol = self.current_controller.symbols.find_symbol_by_name(symbol_name)
        print(symbol_name, symbol)
        try:
            self.extract_dialog_list(symbol)
        except Exception:
            traceback.print_exc()
            self.api.show_error(self.name, 'Error in extracting dialog list')

    dialog_flag_types = ['DIALOG_ROOM_FLAG', 'DIALOG_LOCAL_FLAG', 'DIALOG_GLOBAL_FLAG', 'DIALOG_KINSTONE', 'DIALOG_INVENTORY']
    dialog_types = ['DIALOG_NONE', 'DIALOG_NORMAL', 'DIALOG_SET_FLAG', 'DIALOG_TOGGLE_FLAG', 'DIALOG_CHECK_FLAG', 'DIALOG_CALL_FUNC', 'DIALOG_MINISH']

    item_ids = ['ITEM_NONE', 'ITEM_SMITH_SWORD', 'ITEM_GREEN_SWORD', 'ITEM_RED_SWORD', 'ITEM_BLUE_SWORD', 'ITEM_UNUSED_SWORD', 'ITEM_FOURSWORD', 'ITEM_BOMBS', 'ITEM_REMOTE_BOMBS', 'ITEM_BOW', 'ITEM_LIGHT_ARROW', 'ITEM_BOOMERANG', 'ITEM_MAGIC_BOOMERANG', 'ITEM_SHIELD', 'ITEM_MIRROR_SHIELD', 'ITEM_LANTERN_OFF', 'ITEM_LANTERN_ON', 'ITEM_GUST_JAR', 'ITEM_PACCI_CANE', 'ITEM_MOLE_MITTS', 'ITEM_ROCS_CAPE', 'ITEM_PEGASUS_BOOTS', 'ITEM_FIRE_ROD', 'ITEM_OCARINA', 'ITEM_ORB_GREEN', 'ITEM_ORB_BLUE', 'ITEM_ORB_RED', 'ITEM_TRY_PICKUP_OBJECT', 'ITEM_BOTTLE1', 'ITEM_BOTTLE2', 'ITEM_BOTTLE3', 'ITEM_BOTTLE4', 'ITEM_BOTTLE_EMPTY', 'ITEM_BOTTLE_BUTTER', 'ITEM_BOTTLE_MILK', 'ITEM_BOTTLE_HALF_MILK', 'ITEM_BOTTLE_RED_POTION', 'ITEM_BOTTLE_BLUE_POTION', 'ITEM_BOTTLE_WATER', 'ITEM_BOTTLE_MINERAL_WATER', 'ITEM_BOTTLE_FAIRY', 'ITEM_BOTTLE_PICOLYTE_RED', 'ITEM_BOTTLE_PICOLYTE_ORANGE', 'ITEM_BOTTLE_PICOLYTE_YELLOW', 'ITEM_BOTTLE_PICOLYTE_GREEN', 'ITEM_BOTTLE_PICOLYTE_BLUE', 'ITEM_BOTTLE_PICOLYTE_WHITE', 'BOTTLE_CHARM_NAYRU', 'BOTTLE_CHARM_FARORE', 'BOTTLE_CHARM_DIN', 'ITEM_32', 'ITEM_33', 'ITEM_QST_SWORD', 'ITEM_QST_BROKEN_SWORD', 'ITEM_QST_DOGFOOD', 'ITEM_QST_LONLON_KEY', 'ITEM_QST_MUSHROOM', 'ITEM_QST_BOOK1', 'ITEM_QST_BOOK2', 'ITEM_QST_BOOK3', 'ITEM_QST_GRAVEYARD_KEY', 'ITEM_QST_TINGLE_TROPHY', 'ITEM_QST_CARLOV_MEDAL', 'ITEM_SHELLS', 'ITEM_EARTH_ELEMENT', 'ITEM_FIRE_ELEMENT', 'ITEM_WATER_ELEMENT', 'ITEM_WIND_ELEMENT', 'ITEM_GRIP_RING', 'ITEM_POWER_BRACELETS', 'ITEM_FLIPPERS', 'ITEM_MAP', 'ITEM_SKILL_SPIN_ATTACK', 'ITEM_SKILL_ROLL_ATTACK', 'ITEM_SKILL_DASH_ATTACK', 'ITEM_SKILL_ROCK_BREAKER', 'ITEM_SKILL_SWORD_BEAM', 'ITEM_SKILL_GREAT_SPIN', 'ITEM_SKILL_DOWN_THRUST', 'ITEM_SKILL_PERIL_BEAM', 'ITEM_DUNGEON_MAP', 'ITEM_COMPASS', 'ITEM_BIG_KEY', 'ITEM_SMALL_KEY', 'ITEM_RUPEE1', 'ITEM_RUPEE5', 'ITEM_RUPEE20', 'ITEM_RUPEE50', 'ITEM_RUPEE100', 'ITEM_RUPEE200', 'ITEM_5A', 'ITEM_JABBERNUT', 'ITEM_KINSTONE', 'ITEM_BOMBS5', 'ITEM_ARROWS5', 'ITEM_HEART', 'ITEM_FAIRY', 'ITEM_SHELLS30', 'ITEM_HEART_CONTAINER', 'ITEM_HEART_PIECE', 'ITEM_WALLET', 'ITEM_BOMBBAG', 'ITEM_LARGE_QUIVER', 'ITEM_KINSTONE_BAG', 'ITEM_BRIOCHE', 'ITEM_CROISSANT', 'ITEM_PIE', 'ITEM_CAKE', 'ITEM_BOMBS10', 'ITEM_BOMBS30', 'ITEM_ARROWS10', 'ITEM_ARROWS30', 'ITEM_ARROW_BUTTERFLY', 'ITEM_DIG_BUTTERFLY', 'ITEM_SWIM_BUTTERFLY', 'ITEM_SKILL_FAST_SPIN', 'ITEM_SKILL_FAST_SPLIT', 'ITEM_SKILL_LONG_SPIN']
    kinstone_ids = ['KINSTONE_0', 'KINSTONE_1', 'KINSTONE_2', 'KINSTONE_3', 'KINSTONE_4', 'KINSTONE_5', 'KINSTONE_CASTOR_WILDS_STATUE_LEFT', 'KINSTONE_CASTOR_WILDS_STATUE_MIDDLE', 'KINSTONE_CASTOR_WILDS_STATUE_RIGHT', 'KINSTONE_9', 'KINSTONE_A', 'KINSTONE_B', 'KINSTONE_C', 'KINSTONE_D', 'KINSTONE_E', 'KINSTONE_F', 'KINSTONE_10', 'KINSTONE_11', 'KINSTONE_12', 'KINSTONE_13', 'KINSTONE_14', 'KINSTONE_15', 'KINSTONE_16', 'KINSTONE_17', 'KINSTONE_18', 'KINSTONE_19', 'KINSTONE_1A', 'KINSTONE_1B', 'KINSTONE_1C', 'KINSTONE_1D', 'KINSTONE_1E', 'KINSTONE_1F', 'KINSTONE_20', 'KINSTONE_21', 'KINSTONE_22', 'KINSTONE_23', 'KINSTONE_24', 'KINSTONE_25', 'KINSTONE_26', 'KINSTONE_27', 'KINSTONE_28', 'KINSTONE_29', 'KINSTONE_2A', 'KINSTONE_2B', 'KINSTONE_2C', 'KINSTONE_2D', 'KINSTONE_2E', 'KINSTONE_2F', 'KINSTONE_30', 'KINSTONE_31', 'KINSTONE_32', 'KINSTONE_33', 'KINSTONE_34', 'KINSTONE_35', 'KINSTONE_36', 'KINSTONE_37', 'KINSTONE_38', 'KINSTONE_39', 'KINSTONE_3A', 'KINSTONE_3B', 'KINSTONE_3C', 'KINSTONE_3D', 'KINSTONE_3E', 'KINSTONE_3F', 'KINSTONE_40', 'KINSTONE_41', 'KINSTONE_42', 'KINSTONE_43', 'KINSTONE_44', 'KINSTONE_45', 'KINSTONE_46', 'KINSTONE_47', 'KINSTONE_48', 'KINSTONE_49', 'KINSTONE_4A', 'KINSTONE_4B', 'KINSTONE_4C', 'KINSTONE_4D', 'KINSTONE_4E', 'KINSTONE_4F', 'KINSTONE_50', 'KINSTONE_51', 'KINSTONE_52', 'KINSTONE_53', 'KINSTONE_54', 'KINSTONE_55', 'KINSTONE_56', 'KINSTONE_57', 'KINSTONE_58', 'KINSTONE_59', 'KINSTONE_5A', 'KINSTONE_5B', 'KINSTONE_5C', 'KINSTONE_5D', 'KINSTONE_5E', 'KINSTONE_5F']
    def extract_dialog_list(self, symbol: Symbol) -> None:
        reader = self.get_reader_for_symbol(symbol)
        result = f'const Dialog {symbol.name}[] = {{\n'
        while reader.cursor < symbol.length:
            result += '{ '
            data = reader.read_u32()
            flag = self.get_bits(data, 0, 12)
            flag_type = self.get_bits(data, 12, 4)
            type = self.get_bits(data, 16, 4)
            from_self = self.get_bits(data, 20, 1)
            if flag == 0 and flag_type == 0:
                result += '0, 0, '
            else:
                if flag_type == 2: # DIALOG_GLOBAL_FLAG
                    #local_flag = self.get_bits(flag, 0, 8)
                    #bank = self.get_bits(flag, 8,8 )
                    if flag > len(self.flag_ids[0]):
                        flag = hex(flag) + '/*TODO*/'
                        #raise Exception(f'Unknown global flag {hex(flag)}')
                    else:
                        flag = self.flag_ids[0][flag]
                    # flag = self.flag_ids[bank][local_flag]
                elif flag_type == 3: # DIALOG_KINSTONE
                    flag = self.kinstone_ids[flag]
                elif flag_type == 4: # DIALOG_INVENTORY
                    flag = self.item_ids[flag]

                result += f'{flag}, {self.dialog_flag_types[flag_type]}, '
            result += f'{self.dialog_types[type]}, {from_self}, '
            data = reader.read_u32()
            print(hex(data))
            ptr = self.current_controller.symbols.get_symbol_at(data-1-ROM_OFFSET)
            if ptr is not None and ptr.address != 0 and ptr.length > 0:
                result += '{ .func = '+ ptr.name + ' } '
                #print(ptr)
            else:
                a = self.get_bits(data, 0, 16)
                b = self.get_bits(data, 16, 16)
                result += f'{{ {self.get_text_index(a)}, {self.get_text_index(b)} }} '

                #print(hex(a), hex(b))
            #print(reader.read_u32())
            result += '},\n'
        result += '};'
        print(result)
        QApplication.clipboard().setText(result)

    def get_bits(self, data: int, start: int, bits: int) -> int:
        data >>= start
        return data & (2**bits-1)


    text_categories = ['TEXT_SAVE', 'TEXT_CREDITS', 'TEXT_NAMES', 'TEXT_NEWSLETTER', 'TEXT_ITEMS', 'TEXT_ITEM_GET', 'TEXT_LOCATIONS', 'TEXT_WINDCRESTS', 'TEXT_FIGURINE_NAMES', 'TEXT_FIGURINE_DESCRIPTIONS', 'TEXT_EMPTY', 'TEXT_EZLO', 'TEXT_EZLO2', 'TEXT_MINISH', 'TEXT_KINSTONE', 'TEXT_PICORI', 'TEXT_PROLOGUE', 'TEXT_FINDING_EZLO', 'TEXT_MINISH2', 'TEXT_VAATI', 'TEXT_GUSTAF', 'TEXT_PANEL_TUTORIAL', 'TEXT_VAATI2', 'TEXT_GUSTAF2', 'TEXT_EMPTY2', 'TEXT_EMPTY3', 'TEXT_FARMERS', 'TEXT_CARPENTERS', 'TEXT_EZLO_ELEMENTS_DONE', 'TEXT_GORONS', 'TEXT_EMPTY4', 'TEXT_BELARI', 'TEXT_LON_LON', 'TEXT_FOREST_MINISH', 'TEXT_EZLO_PORTAL', 'TEXT_PERCY', 'TEXT_BREAK_VAATI_CURSE', 'TEXT_FESTIVAL', 'TEXT_EMPTY5', 'TEXT_TREASURE_GUARDIAN', 'TEXT_DAMPE', 'TEXT_BUSINESS_SCRUB', 'TEXT_EMPTY6', 'TEXT_PICOLYTE', 'TEXT_STOCKWELL', 'TEXT_SYRUP', 'TEXT_ITEM_PRICES', 'TEXT_WIND_TRIBE', 'TEXT_ANJU', 'TEXT_GORMAN_ORACLES', 'TEXT_SMITH', 'TEXT_PHONOGRAPH', 'TEXT_TOWN', 'TEXT_TOWN2', 'TEXT_TOWN3', 'TEXT_TOWN4', 'TEXT_TOWN5', 'TEXT_TOWN6', 'TEXT_TOWN7', 'TEXT_MILK', 'TEXT_BAKERY', 'TEXT_SIMON', 'TEXT_SCHOOL', 'TEXT_TINGLE', 'TEXT_POST', 'TEXT_MUTOH', 'TEXT_BURLOV', 'TEXT_CARLOV', 'TEXT_REM', 'TEXT_HAPPY_HEARTH', 'TEXT_BLADE_MASTERS', 'TEXT_ANSWER_HOUSE', 'TEXT_UNK_WISE', 'TEXT_LIBRARY', 'TEXT_TOWN_MINISH1', 'TEXT_TOWN_MINISH2', 'TEXT_HAGEN', 'TEXT_DR_LEFT', 'TEXT_TOWN8', 'TEXT_CAFE']

    def get_text_index(self, data: int) -> str:
        if data == 0:
            return '0'
        entry = self.get_bits(data, 0, 8)
        category = self.get_bits(data, 8, 8)
        if category >= len(self.text_categories):
            raise Exception(f'TEXT_INDEX {hex(data)} not found')
        return f'TEXT_INDEX({self.text_categories[category]}, {hex(entry)})'


    def slot_extract_text_index_list(self) -> None:
        symbol_name = QApplication.clipboard().text()
        symbol = self.current_controller.symbols.find_symbol_by_name(symbol_name)
        try:
            self.extract_text_index_list(symbol)
        except Exception:
            traceback.print_exc()
            self.api.show_error(self.name, 'Error in extracting text index list')

    def extract_text_index_list(self, symbol: Symbol) -> None:
        reader = self.get_reader_for_symbol(symbol)
        result = f'const u16 {symbol.name}[] = {{\n'
        while reader.cursor < symbol.length:
            data = reader.read_u16()
            result += self.get_text_index(data) + ',\n'
        result += '};'
        print(result)
        QApplication.clipboard().setText(result)

    def slot_extract_coords_list(self) -> None:
        symbol_name = QApplication.clipboard().text()
        symbol = self.current_controller.symbols.find_symbol_by_name(symbol_name)
        try:
            self.extract_coords_list(symbol)
        except Exception:
            traceback.print_exc()
            self.api.show_error(self.name, 'Error in extracting coords list')

    def extract_coords_list(self, symbol: Symbol) -> None:
        reader = self.get_reader_for_symbol(symbol)
        result = f'const Coords {symbol.name}[] = {{\n'
        while reader.cursor < symbol.length:
            x = reader.read_s16()
            y = reader.read_s16()
            result += f'{{ .HALF = {{ {hex(x)}, {hex(y)} }} }}, '
        result += '};'
        print(result)
        QApplication.clipboard().setText(result)


    def slot_extract_dungeon_maps(self) -> None:
        self.map_data_symbol = self.current_controller.symbols.find_symbol_by_name('gMapData')

        symbol_name = QApplication.clipboard().text()
        symbol = self.current_controller.symbols.find_symbol_by_name(symbol_name)
        try:
            def handle_data(data_array):
                for data in data_array:
                    print(data)
                    if data['area'] == 0 and data['room'] == 0 and data['mapDataOffset'] == 0:
                        continue
                    data['room'] = self.room_ids[data['area']][data['room']]
                    data['area'] = self.area_ids[data['area']]
                    addr = self.map_data_symbol.address + data['mapDataOffset']
                    map_data_symbol = self.current_controller.symbols.get_symbol_at(addr)
                    data['mapDataOffset'] = 'offset_' + map_data_symbol.name
                    print(data)
                return data_array
            result = self.extract_data(f'const DungeonLayout {symbol.name}[];', self.current_controller.symbols, self.current_controller.rom, handle_data)
            print(result)
            QApplication.clipboard().setText(result)
        except Exception:
            traceback.print_exc()
            self.api.show_error(self.name, 'Error in extracting dungeon layout')

        return
        # Find the map graphics.

        self.assets = read_assets('map.json')
        self.map_data_symbol = self.current_controller.symbols.find_symbol_by_name('gMapData')
        self.replacements = []

        symbol = self.current_controller.symbols.find_symbol_by_name('gDungeonLayouts')
        reader = self.get_reader_for_symbol(symbol)
        while reader.cursor < symbol.length:
            self.extract_map_for_dungeon(self.read_symbol(reader))

        #self.print_all_room_paths()
        write_assets('map2.json', self.assets)
        with open('/tmp/replacements.s', 'w') as file:
            file.writelines(self.replacements)

    def extract_map_for_dungeon(self, symbol: Symbol) -> None:

        reader = self.get_reader_for_symbol(symbol)
        while reader.cursor < symbol.length:
            self.extract_map_for_floor(self.read_symbol(reader))

    def extract_map_for_floor(self, symbol: Symbol) -> None:
        #self.extract_area_table()
        reader = self.get_reader_for_symbol(symbol)
        while reader.cursor < symbol.length:
            area = reader.read_u8()
            room = reader.read_u8()
            pad = reader.read_u16()
            #if pad != 0:
                #raise Exception(f'Pad not 0 for {area}, {room}.')
            map_data_offset = reader.read_u32()

            if area == 0 and room == 0 and map_data_offset == 0:
                #print('End')
                continue

            addr = self.map_data_symbol.address + map_data_offset
            room_symbol = self.current_controller.symbols.get_symbol_at(addr)
            if addr != room_symbol.address:
                print(self.area_ids[area], self.room_ids[area][room])
                print(room_symbol)
                print(addr-room_symbol.address)
                continue

            room_meta = self.get_room_metadata(area, room)
            size = ((room_meta['width']//16 + 3) // 4) * (room_meta['height']//16)

            print(self.get_room_path(area, room), room_symbol, f'{size}/{room_symbol.length}')
            if size < room_symbol.length - 3:
                raise Exception('Size does not use whole symbol.')


            # Find the corresponding asset for this symbol
            asset = self.assets.get_asset_at_of_after(room_symbol.address, RomVariant.USA)
            new_path = self.get_room_path(area, room) + '/dungeon_map.bin'
            new_symbol = f'gDungeonMaps_{self.get_area_name(area)}_{self.get_room_name(area, room)}'
            self.replacements.append(f'{asset["path"]},{new_path}\n')
            self.replacements.append(f'{room_symbol.name}::, {new_symbol}::\n')
            asset['path'] = new_path
            asset['name'] = new_symbol
            asset['type'] = 'dungeon_map'
            asset['options'] = {
                'width': (room_meta['width']//16 + 3) // 4,
                'height': room_meta['height']//16
            }

    def get_room_path(self, area: int, room: int) -> str:
        return f'maps/areas/{area:03}_{self.get_area_name(area)}/rooms/{room:02}_{self.get_room_name(area, room)}'

    def get_area_path(self, area: int) -> str:
        return f'maps/areas/{area:03}_{self.get_area_name(area)}'

    def get_area_name(self, area: int) -> str:
        id = self.area_ids[area]
        start_char = 5 # Remove AREA_ at the start.
        # To camel case.
        result = ''
        for i in range(start_char, len(id)):
            if id[i] == '_':
                continue
            if i != start_char and id[i-1] != '_':
                result += id[i].lower()
            else:
                result += id[i].upper()
        return result

    def get_room_name(self, area: int, room: int) -> str:
        area_id = self.area_ids[area]
        id = self.room_ids[area][room]
        start_char = len(area_id) # Remove ROOM_ and area name at the start
        # To camel case.
        result = ''
        for i in range(start_char, len(id)):
            if id[i] == '_':
                continue
            if i != start_char and id[i-1] != '_':
                result += id[i].lower()
            else:
                result += id[i].upper()
        return result

    def print_all_room_paths(self) -> None:
        print('All room paths:')
        rc = 0
        for area, area_id in enumerate(self.area_ids):
            if len(self.room_ids[area]) > rc:
                rc = len(self.room_ids[area])
            for room, room_id in enumerate(self.room_ids[area]):
                path = self.get_room_path(area, room)
                print(path)
                Path('/tmp/assets/map/' + path).mkdir(parents=True, exist_ok=True)
        print(rc)
        for area, area_id in enumerate(self.area_ids):
            if len(self.room_ids[area]) == rc:
                print(area_id)

    def get_room_metadata(self, area: int, room: int) -> dict:
        result = {}
        symbol = self.current_controller.symbols.find_symbol_by_name('gAreaRoomHeaders')
        reader = self.get_reader_for_symbol(symbol)
        reader.cursor = area * 4
        rooms_symbol = self.read_symbol(reader)
        reader = self.get_reader_for_symbol(rooms_symbol)
        reader.cursor = room * 10
        result['x'] = reader.read_u16()
        result['y'] = reader.read_u16()
        result['width'] = reader.read_u16()
        result['height'] = reader.read_u16()
        result['gfx_index'] = reader.read_u16()

        return result

    sfx_ids = ['SFX_NONE', 'BGM_CASTLE_TOURNAMENT', 'BGM_VAATI_MOTIF', 'BGM_TITLE_SCREEN', 'BGM_CASTLE_MOTIF', 'BGM_ELEMENT_GET', 'BGM_FAIRY_FOUNTAIN', 'BGM_FILE_SELECT', 'BGM_INTRO_CUTSCENE', 'BGM_CREDITS', 'BGM_GAMEOVER', 'BGM_SAVING_ZELDA', 'BGM_LTTP_TITLE', 'BGM_VAATI_THEME', 'BGM_EZLO_THEME', 'BGM_STORY', 'BGM_FESTIVAL_APPROACH', 'BGM_BEAT_VAATI', 'BGM_UNUSED_12', 'BGM_BEANSTALK', 'BGM_HOUSE', 'BGM_CUCCO_MINIGAME', 'BGM_SYRUP_THEME', 'BGM_DUNGEON', 'BGM_ELEMENT_THEME', 'BGM_HYRULE_FIELD', 'BGM_HYRULE_CASTLE', 'BGM_HYRULE_CASTLE_NOINTRO', 'BGM_MINISH_VILLAGE', 'BGM_MINISH_WOODS', 'BGM_CRENEL_STORM', 'BGM_CASTOR_WILDS', 'BGM_HYRULE_TOWN', 'BGM_ROYAL_VALLEY', 'BGM_CLOUD_TOPS', 'BGM_DARK_HYRULE_CASTLE', 'BGM_SECRET_CASTLE_ENTRANCE', 'BGM_DEEPWOOD_SHRINE', 'BGM_CAVE_OF_FLAMES', 'BGM_FORTRESS_OF_WINDS', 'BGM_TEMPLE_OF_DROPLETS', 'BGM_PALACE_OF_WINDS', 'BGM_EZLO_STORY', 'BGM_ROYAL_CRYPT', 'BGM_ELEMENTAL_SANCTUARY', 'BGM_FIGHT_THEME', 'BGM_BOSS_THEME', 'BGM_VAATI_REBORN', 'BGM_VAATI_TRANSFIGURED', 'BGM_CASTLE_COLLAPSE', 'BGM_VAATI_WRATH', 'BGM_FIGHT_THEME2', 'BGM_DIGGING_CAVE', 'BGM_SWIFTBLADE_DOJO', 'BGM_MINISH_CAP', 'BGM_MT_CRENEL', 'BGM_PICORI_FESTIVAL', 'BGM_LOST_WOODS', 'BGM_FAIRY_FOUNTAIN2', 'BGM_WIND_RUINS', 'BGM_UNUSED_3C', 'BGM_UNUSED_3D', 'BGM_UNUSED_3E', 'BGM_UNUSED_3F', 'BGM_UNUSED_40', 'BGM_UNUSED_41', 'BGM_UNUSED_42', 'BGM_UNUSED_43', 'BGM_UNUSED_44', 'BGM_UNUSED_45', 'BGM_UNUSED_46', 'BGM_UNUSED_47', 'BGM_UNUSED_48', 'BGM_UNUSED_49', 'BGM_UNUSED_4A', 'BGM_UNUSED_4B', 'BGM_UNUSED_4C', 'BGM_UNUSED_4D', 'BGM_UNUSED_4E', 'BGM_UNUSED_4F', 'BGM_UNUSED_50', 'BGM_UNUSED_51', 'BGM_UNUSED_52', 'BGM_UNUSED_53', 'BGM_UNUSED_54', 'BGM_UNUSED_55', 'BGM_UNUSED_56', 'BGM_UNUSED_57', 'BGM_UNUSED_58', 'BGM_UNUSED_59', 'BGM_UNUSED_5A', 'BGM_UNUSED_5B', 'BGM_UNUSED_5C', 'BGM_UNUSED_5D', 'BGM_LEARN_SCROLL', 'BGM_EZLO_GET', 'BGM_UNUSED_60', 'BGM_UNUSED_61', 'BGM_UNUSED_62', 'BGM_UNUSED_63', 'SFX_BEEP', 'SFX_TEXTBOX_OPEN', 'SFX_TEXTBOX_CLOSE', 'SFX_TEXTBOX_NEXT', 'SFX_TEXTBOX_SWAP', 'SFX_TEXTBOX_CHOICE', 'SFX_TEXTBOX_SELECT', 'SFX_6B', 'SFX_MENU_CANCEL', 'SFX_MENU_ERROR', 'SFX_RUPEE_BOUNCE', 'SFX_RUPEE_GET', 'SFX_HEART_BOUNCE', 'SFX_HEART_GET', 'SFX_SECRET', 'SFX_SECRET_BIG', 'SFX_METAL_CLINK', 'SFX_PLY_VO1', 'SFX_PLY_VO2', 'SFX_PLY_VO3', 'SFX_PLY_VO4', 'SFX_PLY_VO5', 'SFX_PLY_VO6', 'SFX_PLY_VO7', 'SFX_PLY_JUMP', 'SFX_PLY_LAND', 'SFX_7E', 'SFX_PLY_LIFT', 'SFX_80', 'SFX_81', 'SFX_82', 'SFX_WATER_WALK', 'SFX_WATER_SPLASH', 'SFX_FALL_HOLE', 'SFX_86', 'SFX_PLY_DIE', 'SFX_88', 'SFX_BARREL_RELEASE', 'SFX_BARREL_ENTER', 'SFX_BARREL_ROLL', 'SFX_BARREL_ROLL_STOP', 'SFX_VO_EZLO1', 'SFX_VO_EZLO2', 'SFX_VO_EZLO3', 'SFX_VO_EZLO4', 'SFX_VO_EZLO5', 'SFX_VO_EZLO6', 'SFX_VO_EZLO7', 'SFX_VO_ZELDA1', 'SFX_VO_ZELDA2', 'SFX_VO_ZELDA3', 'SFX_VO_ZELDA4', 'SFX_VO_ZELDA5', 'SFX_VO_ZELDA6', 'SFX_VO_ZELDA7', 'SFX_9B', 'SFX_9C', 'SFX_9D', 'SFX_9E', 'SFX_9F', 'SFX_A0', 'SFX_VO_TINGLE1', 'SFX_VO_TINGLE2', 'SFX_VO_KING1', 'SFX_VO_KING2', 'SFX_VO_KING3', 'SFX_VO_KING4', 'SFX_VO_KING5', 'SFX_A8', 'SFX_A9', 'SFX_AA', 'SFX_SPIRITS_RELEASE', 'SFX_AC', 'SFX_VO_BEEDLE', 'SFX_AE', 'SFX_AF', 'SFX_B0', 'SFX_VO_MINISH1', 'SFX_VO_MINISH2', 'SFX_VO_MINISH3', 'SFX_VO_MINISH4', 'SFX_B5', 'SFX_B6', 'SFX_B7', 'SFX_B8', 'SFX_B9', 'SFX_BA', 'SFX_BB', 'SFX_BC', 'SFX_BD', 'SFX_BE', 'SFX_BF', 'SFX_C0', 'SFX_C1', 'SFX_C2', 'SFX_C3', 'SFX_C4', 'SFX_C5', 'SFX_C6', 'SFX_C7', 'SFX_C8', 'SFX_C9', 'SFX_CA', 'SFX_CB', 'SFX_REM_SLEEP', 'SFX_TASK_COMPLETE', 'SFX_KEY_APPEAR', 'SFX_CF', 'SFX_D0', 'SFX_VO_DOG', 'SFX_VO_CAT', 'SFX_VO_EPONA', 'SFX_VO_COW', 'SFX_VO_CUCCO_CALL', 'SFX_VO_CHEEP', 'SFX_ITEM_SWORD_CHARGE', 'SFX_ITEM_SWORD_CHARGE_FINISH', 'SFX_D9', 'SFX_DA', 'SFX_VO_STURGEON', 'SFX_HAMMER1', 'SFX_HAMMER2', 'SFX_HAMMER3', 'SFX_HAMMER4', 'SFX_HAMMER5', 'SFX_HAMMER6', 'SFX_CUCCO_MINIGAME_BELL', 'SFX_E3', 'SFX_E4', 'SFX_BUTTON_DEPRESS', 'SFX_THUD_HEAVY', 'SFX_WIND1', 'SFX_WIND2', 'SFX_WIND3', 'SFX_EA', 'SFX_EB', 'SFX_EC', 'SFX_ED', 'SFX_EE', 'SFX_EF', 'SFX_F0', 'SFX_F1', 'SFX_F2', 'SFX_F3', 'SFX_SUMMON', 'SFX_F5', 'SFX_EVAPORATE', 'SFX_APPARATE', 'SFX_F8', 'SFX_TELEPORTER', 'SFX_FA', 'SFX_FB', 'SFX_FC', 'SFX_ITEM_BOMB_EXPLODE', 'SFX_HIT', 'SFX_FF', 'SFX_100', 'SFX_101', 'SFX_102', 'SFX_103', 'SFX_PLACE_OBJ', 'SFX_105', 'SFX_106', 'SFX_107', 'SFX_108', 'SFX_ITEM_GET', 'SFX_10A', 'SFX_10B', 'SFX_BUTTON_PRESS', 'SFX_10D', 'SFX_10E', 'SFX_10F', 'SFX_110', 'SFX_111', 'SFX_112', 'SFX_113', 'SFX_114', 'SFX_115', 'SFX_116', 'SFX_117', 'SFX_ITEM_SHIELD_BOUNCE', 'SFX_ITEM_GLOVES_KNOCKBACK', 'SFX_EM_ARMOS_ON', 'SFX_CHEST_OPEN', 'SFX_11C', 'SFX_11D', 'SFX_EM_MOBLIN_SPEAR', 'SFX_LOW_HEALTH', 'SFX_CHARGING_UP', 'SFX_STAIRS', 'SFX_122', 'SFX_123', 'SFX_124', 'SFX_125', 'SFX_126', 'SFX_BOSS_HIT', 'SFX_BOSS_DIE', 'SFX_BOSS_EXPLODE', 'SFX_12A', 'SFX_12B', 'SFX_12C', 'SFX_12D', 'SFX_12E', 'SFX_12F', 'SFX_130', 'SFX_131', 'SFX_132', 'SFX_133', 'SFX_134', 'SFX_135', 'SFX_136', 'SFX_137', 'SFX_138', 'SFX_139', 'SFX_13A', 'SFX_13B', 'SFX_13C', 'SFX_ITEM_LANTERN_ON', 'SFX_ITEM_LANTERN_OFF', 'SFX_ITEM_SWORD_BEAM', 'SFX_140', 'SFX_HEART_CONTAINER_SPAWN', 'SFX_SPARKLES', 'SFX_143', 'SFX_144', 'SFX_145', 'SFX_146', 'SFX_147', 'SFX_148', 'SFX_149', 'SFX_14A', 'SFX_14B', 'SFX_14C', 'SFX_14D', 'SFX_14E', 'SFX_14F', 'SFX_150', 'SFX_151', 'SFX_NEAR_PORTAL', 'SFX_153', 'SFX_154', 'SFX_155', 'SFX_156', 'SFX_157', 'SFX_158', 'SFX_159', 'SFX_15A', 'SFX_15B', 'SFX_15C', 'SFX_15D', 'SFX_15E', 'SFX_15F', 'SFX_160', 'SFX_161', 'SFX_162', 'SFX_TOGGLE_DIVING', 'SFX_164', 'SFX_165', 'SFX_166', 'SFX_167', 'SFX_168', 'SFX_169', 'SFX_16A', 'SFX_PRESSURE_PLATE', 'SFX_16C', 'SFX_16D', 'SFX_16E', 'SFX_PLY_SHRINKING', 'SFX_PLY_GROW', 'SFX_171', 'SFX_172', 'SFX_EZLO_UI', 'SFX_174', 'SFX_175', 'SFX_176', 'SFX_177', 'SFX_178', 'SFX_179', 'SFX_17A', 'SFX_LAVA_TILE_STEP', 'SFX_LAVA_TILE_WOBBLE', 'SFX_LAVA_TILE_SINK', 'SFX_LAVA_TILE_FLIP', 'SFX_LAVA_TILE_LAND', 'SFX_180', 'SFX_181', 'SFX_182', 'SFX_183', 'SFX_184', 'SFX_185', 'SFX_186', 'SFX_STAIRS_ASCEND', 'SFX_STAIRS_DESCEND', 'SFX_189', 'SFX_18A', 'SFX_18B', 'SFX_18C', 'SFX_18D', 'SFX_18E', 'SFX_18F', 'SFX_190', 'SFX_191', 'SFX_192', 'SFX_193', 'SFX_194', 'SFX_195', 'SFX_196', 'SFX_197', 'SFX_198', 'SFX_199', 'SFX_19A', 'SFX_19B', 'SFX_19C', 'SFX_19D', 'SFX_19E', 'SFX_19F', 'SFX_1A0', 'SFX_1A1', 'SFX_1A2', 'SFX_1A3', 'SFX_1A4', 'SFX_1A5', 'SFX_1A6', 'SFX_1A7', 'SFX_1A8', 'SFX_1A9', 'SFX_1AA', 'SFX_1AB', 'SFX_1AC', 'SFX_1AD', 'SFX_1AE', 'SFX_1AF', 'SFX_1B0', 'SFX_ICE_BLOCK_SLIDE', 'SFX_ICE_BLOCK_STOP', 'SFX_ICE_BLOCK_MELT', 'SFX_1B4', 'SFX_1B5', 'SFX_1B6', 'SFX_VO_GORON1', 'SFX_VO_GORON2', 'SFX_VO_GORON3', 'SFX_VO_GORON4', 'SFX_EM_DEKUSCRUB_HIT', 'SFX_1BC', 'SFX_1BD', 'SFX_1BE', 'SFX_1BF', 'SFX_1C0', 'SFX_1C1', 'SFX_1C2', 'SFX_1C3', 'SFX_1C4', 'SFX_1C5', 'SFX_1C6', 'SFX_1C7', 'SFX_1C8', 'SFX_1C9', 'SFX_1CA', 'SFX_1CB', 'SFX_1CC', 'SFX_ELEMENT_PLACE', 'SFX_ELEMENT_FLOAT', 'SFX_ELEMENT_CHARGE', 'SFX_1D0', 'SFX_ELEMENT_INFUSE', 'SFX_1D2', 'SFX_1D3', 'SFX_1D4', 'SFX_1D5', 'SFX_VO_CUCCO1', 'SFX_VO_CUCCO2', 'SFX_VO_CUCCO3', 'SFX_VO_CUCCO4', 'SFX_VO_CUCCO5', 'SFX_1DB', 'SFX_1DC', 'SFX_1DD', 'SFX_1DE', 'SFX_1DF', 'SFX_1E0', 'SFX_1E1', 'SFX_1E2', 'SFX_1E3', 'SFX_1E4', 'SFX_1E5', 'SFX_1E6', 'SFX_1E7', 'SFX_1E8', 'SFX_1E9', 'SFX_1EA', 'SFX_1EB', 'SFX_1EC', 'SFX_1ED', 'SFX_1EE', 'SFX_1EF', 'SFX_1F0', 'SFX_1F1', 'SFX_1F2', 'SFX_1F3', 'SFX_1F4', 'SFX_1F5', 'SFX_1F6', 'SFX_1F7', 'SFX_1F8', 'SFX_1F9', 'SFX_1FA', 'SFX_1FB', 'SFX_1FC', 'SFX_1FD', 'SFX_1FE', 'SFX_1FF', 'SFX_200', 'SFX_201', 'SFX_202', 'SFX_203', 'SFX_204', 'SFX_205', 'SFX_206', 'SFX_207', 'SFX_208', 'SFX_209', 'SFX_20A', 'SFX_20B', 'SFX_20C', 'SFX_20D', 'SFX_20E', 'SFX_20F', 'SFX_210', 'SFX_211', 'SFX_212', 'SFX_213', 'SFX_214', 'SFX_215', 'SFX_216', 'SFX_217', 'SFX_218', 'SFX_219', 'SFX_21A', 'SFX_21B', 'SFX_21C', 'SFX_21D', 'SFX_21E', 'SFX_21F', 'SFX_PICOLYTE', 'SFX_221', ]
    local_banks = ['LOCAL_BANK_G', 'LOCAL_BANK_0', 'LOCAL_BANK_1', 'LOCAL_BANK_2', 'LOCAL_BANK_3', 'LOCAL_BANK_4', 'LOCAL_BANK_5', 'LOCAL_BANK_6', 'LOCAL_BANK_7', 'LOCAL_BANK_8', 'LOCAL_BANK_9', 'LOCAL_BANK_10', 'LOCAL_BANK_11', 'LOCAL_BANK_12', ]
    def slot_extract_area_metadata(self) -> None:
        area_flags = [
            ('AR_IS_OVERWORLD', 0x1),
            ('AR_HAS_KEYS', 0x2),
            ('AR_IS_DUNGEON', 0x4),
            ('AR_HAS_MAP', 0x8),
            ('AR_HAS_ENEMIES', 0x10),
            ('AR_IS_MOLE_CAVE', 0x20),
            ('AR_HAS_NO_ENEMIES', 0x40),
            ('AR_ALLOWS_WARP', 0x80,),
        ]

        try:
            def handle_data(data_array):
                for data in data_array:
                    data['flags'] = self.extract_bitmask(area_flags, data['flags'])
                    data['flag_bank'] = self.local_banks[data['flag_bank']]
                    data['queueBgm'] = self.sfx_ids[data['queueBgm']]
                    print(data)
                return data_array
            result = self.extract_data(f'const AreaHeader gAreaMetadata[];', self.current_controller.symbols, self.current_controller.rom, handle_data)
            print(result)
            QApplication.clipboard().setText(result)
        except Exception:
            traceback.print_exc()
            self.api.show_error(self.name, 'Error in extracting area metadata')


    def extract_bitmask(self, bitmask_definition: List[Tuple[str, int]], value: int) -> str:
        result = []
        for (key, mask) in bitmask_definition:
            if value & mask:
                result.append(key)
        return BitmaskValue(result)

    def align_map_data(self) -> None:
        self.assets = read_assets('map.json')
        for asset in self.assets.assets:
            if 'size' in asset:
                if asset['size'] % 4 != 0:
                    asset['size'] += 4 - (asset['size'] % 4)
        write_assets('map2.json', self.assets)
        print('done')

    def slot_fix_tilesets(self) -> None:
        self.assets = read_assets('map.json')
        self.map_data_symbol = self.current_controller.symbols.find_symbol_by_name('gMapData')
        self.replacements = []

        #tilesets_symbol = self.current_controller.symbols.find_symbol_by_name('gAreaTilesets')
        #self.read_tilesets(tilesets_symbol)

        #metatilesets_symbol = self.current_controller.symbols.find_symbol_by_name('gAreaMetatiles')
        #self.read_metatilesets(metatilesets_symbol)

        tilemaps_symbol = self.current_controller.symbols.find_symbol_by_name('gAreaRoomMaps')
        self.read_tilemaps(tilemaps_symbol)

        #write_assets('map2.json', self.assets)
        with open('/tmp/replacements.s', 'w') as file:
            file.writelines(self.replacements)

    def read_tilesets(self, symbol: Symbol) -> None:
        self.used_tilesets = []
        reader = self.get_reader_for_symbol(symbol)
        area = 0
        while reader.cursor < symbol.length:
            area_symbol = self.read_symbol(reader)
            self.read_tilesets_area(area_symbol, area)
            area += 1

    def read_tilesets_area(self, symbol: Symbol, area: int) -> None:
        reader = self.get_reader_for_symbol(symbol)
        tileset = 0
        while reader.cursor < symbol.length:
            area_symbol = self.read_symbol(reader)

            self.read_tilesets_room(area_symbol, area, tileset)
            tileset += 1

    def read_tilesets_room(self, symbol: Symbol, area: int, tileset: int) -> None:
        print(symbol)
        reader = self.get_reader_for_symbol(symbol)
        img = 0
        while reader.cursor < symbol.length:
            asset_offset = reader.read_u32() & 0x7FFFFFFF
            ram_address = reader.read_u32()
            property_2 = reader.read_u32()
            actual_type = 'unknown'

            if ram_address == 0:
                continue

            address = self.map_data_symbol.address + asset_offset
            tileset_symbol = self.current_controller.symbols.get_symbol_at(address)

            if tileset_symbol in self.used_tilesets:
                # This reuses the tileset from another area.
                img += 1
                continue
            self.used_tilesets.append(tileset_symbol)

            new_symbol = f'gAreaTileset_{self.get_area_name(area)}_{tileset}_{img}'

            if new_symbol != tileset_symbol.name:
                self.replacements.append(f'offset_{tileset_symbol.name},offset_{new_symbol}\n')
                self.replacements.append(f'{tileset_symbol.name}::,{new_symbol}::\n')

            path = self.get_area_path(area) + f'/tilesets/{tileset}/{new_symbol}.4bpp.lz'

            self.replacements.append(f'tilesets/{tileset_symbol.name}.4bpp.lz,{path}\n')
            self.replacements.append(f'tilesets/{tileset_symbol.name}.bin.lz,{path}\n')
            # print(hex(ram_address))
            # if 0x06000000 <= ram_address <= 0x0600DFFF: # Tile GFX data
            #     actual_type =  type + "_gfx"
            # elif ram_address == 0x0200B654: # BG1 layer data
            #     actual_type = type + "_layer1"
            # elif ram_address == 0x02025EB4: # BG2 layer data
            #     actual_type = type + "_layer2"
            # elif ram_address == 0x02012654: # BG1 tileset
            #     actual_type = type + "_tileset1"
            # elif ram_address == 0x0202CEB4: # BG2 tileset
            #     actual_type = type + "_tileset2"
            # elif ram_address == 0x02002F00: # BG1 8x8 tile mapping
            #     actual_type = type + "_mapping1"
            # elif ram_address == 0x02019EE0: # BG2 8x8 tile mapping
            #     actual_type = type + "_mapping2"
            # elif ram_address == 0x0600F000: # BG3 8x8 tile mapping
            #     actual_type = type + "_mapping3"
            # elif ram_address == 0x02010654: # BG1 tileset tile type data
            #     actual_type = type + "_tile_types1"
            # elif ram_address == 0x0202AEB4: # BG2 tileset tile type data
            #     actual_type = type + "_tile_types2"
            # elif ram_address == 0x02027EB4: # BG2 collision layer data
            #     actual_type = type + "_collision"

            print(path)
            img += 1

    def read_metatilesets(self, symbol: Symbol) -> None:
        self.used_tilesets = []
        reader = self.get_reader_for_symbol(symbol)
        area = 0
        while reader.cursor < symbol.length:
            area_symbol = self.read_symbol(reader)
            self.read_metatilesets_area(area_symbol, area)
            area += 1

    def read_metatilesets_area(self, symbol: Symbol, area: int) -> None:
        if symbol.name.endswith('_Unused'):
            return
        print(symbol)
        reader = self.get_reader_for_symbol(symbol)
        img = 0
        while reader.cursor < symbol.length:
            asset_offset = reader.read_u32() & 0x7FFFFFFF
            ram_address = reader.read_u32()
            property_2 = reader.read_u32()
            actual_type = 'unknown'

            if ram_address == 0:
                continue

            address = self.map_data_symbol.address + asset_offset
            tileset_symbol = self.current_controller.symbols.get_symbol_at(address)

            if tileset_symbol in self.used_tilesets:
                # This reuses the tileset from another area.
                img += 1
                continue
            self.used_tilesets.append(tileset_symbol)


            if ram_address == 0x02012654: # BG1 tileset
                new_symbol = f'gAreaMetaTileset_{self.get_area_name(area)}_top'
            elif ram_address == 0x0202CEB4: # BG2 tileset
                new_symbol = f'gAreaMetaTileset_{self.get_area_name(area)}_bottom'
            elif ram_address == 0x02010654: # BG1 tileset tile type data
                new_symbol = f'gAreaMetaTilesetTypes_{self.get_area_name(area)}_top'
            elif ram_address == 0x0202AEB4: # BG2 tileset tile type data
                new_symbol = f'gAreaMetaTilesetTypes_{self.get_area_name(area)}_bottom'
            else:
                raise Exception(f'Unknown type for addr: {hex(ram_address)}')


            if new_symbol != tileset_symbol.name:
                self.replacements.append(f'offset_{tileset_symbol.name},offset_{new_symbol}\n')
                self.replacements.append(f'{tileset_symbol.name}::,{new_symbol}::\n')

            path = self.get_area_path(area) + f'/metatilesets/{new_symbol}.bin.lz'

            self.replacements.append(f'assets/{tileset_symbol.name}.bin.lz,{path}\n')
            # print(hex(ram_address))
            # if 0x06000000 <= ram_address <= 0x0600DFFF: # Tile GFX data
            #     actual_type =  type + "_gfx"
            # elif ram_address == 0x0200B654: # BG1 layer data
            #     actual_type = type + "_layer1"
            # elif ram_address == 0x02025EB4: # BG2 layer data
            #     actual_type = type + "_layer2"
            # elif ram_address == 0x02012654: # BG1 tileset
            #     actual_type = type + "_tileset1"
            # elif ram_address == 0x0202CEB4: # BG2 tileset
            #     actual_type = type + "_tileset2"
            # elif ram_address == 0x02002F00: # BG1 8x8 tile mapping
            #     actual_type = type + "_mapping1"
            # elif ram_address == 0x02019EE0: # BG2 8x8 tile mapping
            #     actual_type = type + "_mapping2"
            # elif ram_address == 0x0600F000: # BG3 8x8 tile mapping
            #     actual_type = type + "_mapping3"
            # elif ram_address == 0x02010654: # BG1 tileset tile type data
            #     actual_type = type + "_tile_types1"
            # elif ram_address == 0x0202AEB4: # BG2 tileset tile type data
            #     actual_type = type + "_tile_types2"
            # elif ram_address == 0x02027EB4: # BG2 collision layer data
            #     actual_type = type + "_collision"

            print(path)
            img += 1

    def read_tilemaps(self, symbol: Symbol) -> None:
        self.used_tilesets = []
        reader = self.get_reader_for_symbol(symbol)
        area = 0
        while reader.cursor < 0x90*4:#symbol.length:
            area_symbol = self.read_symbol(reader)
            self.read_tilemaps_area(area_symbol, area)
            area += 1

    def read_tilemaps_area(self, symbol: Symbol, area: int) -> None:
        print('--', symbol)
        if symbol.name.endswith('_Unused'):
            return
        reader = self.get_reader_for_symbol(symbol)
        room = 0
        while reader.cursor < symbol.length:
            room_symbol = self.read_symbol(reader)
            self.read_tilemaps_room(room_symbol, area, room)
            room += 1

    def read_tilemaps_room(self, symbol: Symbol, area: int, room: int) -> None:
        print('---', symbol)
        print(area, room)
        if symbol is None:
            return
        reader = self.get_reader_for_symbol(symbol)
        img = 0
        while reader.cursor < symbol.length:
            asset_offset = reader.read_u32() & 0x7FFFFFFF
            ram_address = reader.read_u32()
            property_2 = reader.read_u32()
            actual_type = 'unknown'


            address = self.map_data_symbol.address + asset_offset
            tileset_symbol = self.current_controller.symbols.get_symbol_at(address)

            print(tileset_symbol.name)

            if tileset_symbol in self.used_tilesets:
                # This reuses the tileset from another area.
                img += 1
                continue
            self.used_tilesets.append(tileset_symbol)


            if ram_address == 0:
                continue

            if  0x06000000 <= ram_address <= 0x0600DFFF:
                # Tileset should already be correct.
                print('tileset')
                continue

            elif ram_address == 0x0200B654: # BG1 layer data
                new_symbol = f'gAreaRoomMap_{self.get_area_name(area)}_{self.get_room_name(area,room)}_top'
            elif ram_address == 0x02025EB4: # BG2 layer data
                new_symbol = f'gAreaRoomMap_{self.get_area_name(area)}_{self.get_room_name(area,room)}_bottom'

            elif ram_address == 0x02002F00: # BG1 8x8 tile mapping
                new_symbol = f'gRoomMapping_{self.get_area_name(area)}_{self.get_room_name(area,room)}_top'
            elif ram_address == 0x02019EE0: # BG2 8x8 tile mapping
                new_symbol = f'gRoomMapping_{self.get_area_name(area)}_{self.get_room_name(area,room)}_bottom'
            elif ram_address == 0x02027EB4: # BG2 collision layer data
                new_symbol = f'gRoomCollisionMap_{self.get_area_name(area)}_{self.get_room_name(area,room)}'
            # elif ram_address == 0x0202CEB4: # BG2 tileset
            #     new_symbol = f'gAreaMetaTileset_{self.get_area_name(area)}_bottom'
            # elif ram_address == 0x02010654: # BG1 tileset tile type data
            #     new_symbol = f'gAreaMetaTilesetTypes_{self.get_area_name(area)}_top'
            # elif ram_address == 0x0202AEB4: # BG2 tileset tile type data
            #     new_symbol = f'gAreaMetaTilesetTypes_{self.get_area_name(area)}_bottom'
            else:
                raise Exception(f'Unknown type for addr: {hex(ram_address)}')


            if new_symbol != tileset_symbol.name:
                self.replacements.append(f'offset_{tileset_symbol.name},offset_{new_symbol}\n')
                self.replacements.append(f'{tileset_symbol.name}::,{new_symbol}::\n')


            # TODO instead use get_room_path
            path = self.get_area_path(area) + f'/rooms/{self.get_room_name(area, room)}/{new_symbol}.bin.lz'
            path_uncompressed = self.get_area_path(area) + f'/rooms/{self.get_room_name(area, room)}/{new_symbol}.bin'

            self.replacements.append(f'assets/{tileset_symbol.name}.bin.lz,{path}\n')
            self.replacements.append(f'assets/{tileset_symbol.name}.bin,{path_uncompressed}\n')
            # print(hex(ram_address))
            # if 0x06000000 <= ram_address <= 0x0600DFFF: # Tile GFX data
            #     actual_type =  type + "_gfx"
            # elif ram_address == 0x0200B654: # BG1 layer data
            #     actual_type = type + "_layer1"
            # elif ram_address == 0x02025EB4: # BG2 layer data
            #     actual_type = type + "_layer2"
            # elif ram_address == 0x02012654: # BG1 tileset
            #     actual_type = type + "_tileset1"
            # elif ram_address == 0x0202CEB4: # BG2 tileset
            #     actual_type = type + "_tileset2"
            # elif ram_address == 0x02002F00: # BG1 8x8 tile mapping
            #     actual_type = type + "_mapping1"
            # elif ram_address == 0x02019EE0: # BG2 8x8 tile mapping
            #     actual_type = type + "_mapping2"
            # elif ram_address == 0x0600F000: # BG3 8x8 tile mapping
            #     actual_type = type + "_mapping3"
            # elif ram_address == 0x02010654: # BG1 tileset tile type data
            #     actual_type = type + "_tile_types1"
            # elif ram_address == 0x0202AEB4: # BG2 tileset tile type data
            #     actual_type = type + "_tile_types2"
            # elif ram_address == 0x02027EB4: # BG2 collision layer data
            #     actual_type = type + "_collision"

            print(path)
            img += 1

    def fix_paths(self):
        replacements = []
        for area, area_id in enumerate(self.area_ids):
            for room, room_id in enumerate(self.room_ids[area]):
                wrong_path = self.get_area_path(area) + f'/rooms/{self.get_room_name(area, room)}'
                right_path = self.get_room_path(area, room)
                replacements.append(f'{wrong_path},{right_path}\n')


        with open('/tmp/replacements.s', 'w') as file:
            file.writelines(replacements)

    def slot_export_configs(self) -> None:
        """Export config json files for the maps."""

        assets_folder = os.path.join(get_repo_location(), 'build', 'tmc', 'assets') # TODO handle different variants?

        area_configs = []
        room_configs = []

        for area, area_id in enumerate(self.area_ids):
            area_configs.append({
                'id': area,
                'name': area_id,
                'tilesets': [],
                'metatileset': -1
            })
            room_configs.append([])
            for room, room_id in enumerate(self.room_ids[area]):
                room_configs[area].append({
                    'id': room,
                    'name': room_id,
                    'area': area, # TODO can be implicit by parent folder?
                    'maps': []
                })


        # Tilesets
        tilesets_headers = AsmDataFile(os.path.join(get_repo_location(), 'data', 'map', 'tileset_headers.s'))
        used_tilesets = {}
        used_tilesets_tiles = {}

        for area, entry in enumerate(tilesets_headers.symbols['gAreaTilesets'].entries):
            symbol_name = entry.attributes[0]
            if symbol_name == 'gAreaTilesets_Unused':
                continue
            if symbol_name in used_tilesets.keys():
                # Reuse this tileset.
                area_configs[area]['tileset_ref'] = used_tilesets[symbol_name]
                continue
            used_tilesets[symbol_name] = area

            for tileset_id, entry in enumerate(tilesets_headers.symbols[symbol_name].entries):
                tileset = tilesets_headers.symbols[entry.attributes[0]]
                config = {
                    'id': tileset_id,
                    'area': area, # TODO can be implicit by parent folder?
                    'tiles': []
                }
                for entry in tileset.entries:
                    if entry.name == 'tileset_tiles':
                        tiles_symbol = entry.attributes[0][7:]
                        if tiles_symbol in used_tilesets_tiles.keys():
                            config['tiles'].append({
                                'ref': used_tilesets_tiles[tiles_symbol],                        
                                'dest': entry.attributes[1],
                                'compressed': entry.attributes[3] == '1'
                            })
                            continue
                        config['tiles'].append({
                            'src': tiles_symbol, # Remove offset_
                            'dest': entry.attributes[1],
                            'compressed': entry.attributes[3] == '1'
                        })
                        used_tilesets_tiles[tiles_symbol] = os.path.join(self.get_area_path(area), 'tilesets', str(tileset_id), tiles_symbol)
                    elif entry.name == 'tileset_palette_set':
                        config['palette_set'] = int(entry.attributes[0])
                    else:
                        raise Exception(f'Unknown tileset_headers entry type: {entry.name}.')
                
                config_path = os.path.join(assets_folder, self.get_area_path(area), 'tilesets', str(tileset_id), 'config.json')
                self.write_config(config_path, config)
               
                area_configs[area]['tilesets'].append(tileset_id)

        # Metatileset
        metatilesets_headers = AsmDataFile(os.path.join(get_repo_location(), 'data', 'map', 'metatile_headers.s'))
        used_metatilesets = {}
        used_metatilesets_entries = {}
        for area, entry in enumerate(metatilesets_headers.symbols['gAreaMetatiles'].entries):
            symbol_name = entry.attributes[0]
            if symbol_name == 'gAreaMetatiles_Unused':
                continue
            if symbol_name in used_metatilesets.keys():
                # Reused metatileset.
                area_configs[area]['metatileset'] = used_metatilesets[symbol_name]
                continue
            used_metatilesets[symbol_name] = area
            config = {
                'area': area, # TODO can be implicit by parent folder?
            }
            for entry in metatilesets_headers.symbols[symbol_name].entries:
                if entry.name == 'metatiles_bottom':
                    field = 'tiles_bottom'
                elif entry.name == 'metatiles_top':
                    field = 'tiles_top'
                elif entry.name == 'metatile_types_bottom':
                    field = 'types_bottom'
                elif entry.name == 'metatile_types_top':
                    field = 'types_top'
                else:
                    raise Exception(f'Unknown metatileset entry {entry.name}.')
                entry_symbol = entry.attributes[0][7:] # Remove offset_

                if entry_symbol == 'gAreaRoomMap_None':
                    continue

                if entry_symbol in used_metatilesets_entries.keys():
                    # Reused
                    config[field] = {
                        'ref': used_metatilesets_entries[entry_symbol],
                        'compressed': entry.attributes[2] == '1' # TODO if all of them are compressed, we only need to store the src
                    }
                    continue
                used_metatilesets_entries[entry_symbol] = os.path.join(self.get_area_path(area), 'metatileset', entry_symbol)
                config[field] = {
                    'src': entry_symbol,
                    'compressed': entry.attributes[2] == '1' # TODO if all of them are compressed, we only need to store the src
                }
            config_path = os.path.join(assets_folder, self.get_area_path(area), 'metatileset', 'config.json')
            self.write_config(config_path, config)
            area_configs[area]['metatileset'] = area

        # Rooms
        room_headers = AsmDataFile(os.path.join(get_repo_location(), 'data', 'map', 'room_headers.s'))
        for area, entry in enumerate(room_headers.symbols['gAreaRoomHeaders'].entries):
            symbol_name = entry.attributes[0]
            if symbol_name == '0x0':
                continue
            room = 0
            for entry in room_headers.symbols[symbol_name].entries:
                if entry.name == 'room_header':
                    if room >= len(room_configs[area]):
                        raise Exception(f'No space for room {room} in area {self.area_ids[area]} ({area}).')
                    room_configs[area][room]['x'] = int(entry.attributes[0], 0)
                    room_configs[area][room]['y'] = int(entry.attributes[1], 0)
                    room_configs[area][room]['width'] = int(entry.attributes[2], 0)
                    room_configs[area][room]['height'] = int(entry.attributes[3], 0)
                    room_configs[area][room]['tileset'] = int(entry.attributes[4], 0)
                    room += 1
                elif entry.name == '.2byte':
                    pass # end of this area
                else:
                    raise Exception(f'Unknown room headers entry: {entry.name}.')

        used_maps = {}
        map_headers = AsmDataFile(os.path.join(get_repo_location(), 'data', 'map', 'map_headers.s'))
        for area, entry in enumerate(map_headers.symbols['gAreaRoomMaps'].entries):
            symbol_name = entry.attributes[0]
            if symbol_name == 'gAreaRoomMaps_Unused':
                continue
            for room, entry in enumerate(map_headers.symbols[symbol_name].entries):
                # TODO handle reused rooms using references?

                room_symbol = entry.attributes[0]
                if room_symbol == '0x0' or room_symbol == 'gAreaRoomMap_Unused':
                    continue
                if room >= len(room_configs[area]):
                    print(len(map_headers.symbols[symbol_name].entries))
                    raise Exception(f'No space for room {room} in area {self.area_ids[area]} ({area}).')
                for entry in map_headers.symbols[room_symbol].entries:
                    if entry.name == 'map_bottom':
                        field = 'map_bottom'
                    elif entry.name == 'map_top':
                        field = 'map_top'
                    elif entry.name == 'tileset_tiles':
                        field = 'tiles' # TODO need to add dest
                    elif entry.name == 'map_bottom_special':
                        field = 'map_bottom_special'
                    elif entry.name == 'map_top_special':
                        field = 'map_top_special'
                    elif entry.name == 'collision_bottom':
                        field = 'collision_bottom'           
                    elif entry.name == '.4byte':
                        print(f'Unknown .4byte: {entry}.')
                        continue
                    else:
                        print(entry)
                        raise Exception(f'Unknown map headers entry: {entry.name}')

                    # TODO room map reuse (happens in beanstalks)

                    map_symbol = entry.attributes[0][7:] # Remove offset_

                    if map_symbol == 'gAreaRoomMap_None':
                        continue

                    if map_symbol in used_maps.keys():
                        # Reused map.
                        room_configs[area][room]['maps'].append({
                            'type': field,
                            'ref': used_maps[map_symbol],
                            'compressed': entry.attributes[2] == '1'
                        })
                        continue

                    used_maps[map_symbol] = os.path.join(self.get_room_path(area, room), map_symbol)

                    bin_path = os.path.join(get_repo_location(), 'build', 'tmc', 'assets', self.get_room_path(area, room), map_symbol + '.bin')
                    if not os.path.exists(bin_path):
                        print(f'Missing: {bin_path}')

                    room_configs[area][room]['maps'].append({
                        'type': field,
                        'src': map_symbol,
                        'compressed': entry.attributes[2] == '1'
                    })


        # Write the configs to files.
        for area, config in enumerate(area_configs):
            config_path = os.path.join(assets_folder, self.get_area_path(area), 'config.json')
            self.write_config(config_path, config)
            for room, config in enumerate(room_configs[area]):
                config_path = os.path.join(assets_folder, self.get_room_path(area, room), 'config.json')
                self.write_config(config_path, config)

        # area config.json
        # Tilesets
        # Meta-Tilesets
        # 

        # room config.json


        # TODO flag whether an area / a room is used
        # TODO Rename metatilesets folder to metatileset
        # TODO need to adapt the area/room enums in the decomp repo
        # TODO Fix icon on windows

        # TODO possibly controversial decisions:
        # - Use decimal for area and room numbers because we can only store decimal numbers.
        # - Split tilesets and metatilesets into areas even though they are reused by other areas.
        # - Use a ref field in the json for references.
        print('done')
        self.api.show_message('Export configs', 'Configs successfully exported.')

    def write_config(self, path: str, config: dict) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        json.dump(config, open(path, 'w'))