from dataclasses import dataclass
from enum import Enum
import os
from plugins.data_extractor.gba_lz77 import GBALZ77, DecompressionError
from plugins.data_extractor.read_data import Reader, load_json_files, read_var
from tlh.const import ROM_OFFSET, RomVariant
from tlh.data.symbols import Symbol
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

@dataclass
class Asset:
    name: str
    type: str
    offset: int
    size: int
    compressed: bool


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
        menu.addAction('Test', self.slot_test)


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
        #self.extract_areas()
        #self.extract_area_table()
        #self.extract_gfx_groups()
        self.extract_sprites()
        return
        '''
        symbol_name = 'gUnk_0811EE64'

        symbol = self.current_controller.symbols.find_symbol_by_name(symbol_name)
        if symbol is None:
            self.api.show_error(self.name, f'Could not find symbol {symbol_name}')
            return

        data = self.current_controller.rom.get_bytes(symbol.address, symbol.address+symbol.length)
        reader = Reader(data, self.current_controller.symbols)
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


    def extract_gUnk_082F3D74(self) -> None:
        symbol_name = 'gUnk_082F3D74'

        symbol = self.current_controller.symbols.find_symbol_by_name(symbol_name)
        if symbol is None:
            self.api.show_error(self.name, f'Could not find symbol {symbol_name}')
            return

        data = self.current_controller.rom.get_bytes(symbol.address, symbol.address+symbol.length)
        reader = Reader(data, self.current_controller.symbols)

        first_level = []
        second_level = []

        lines = []
        lines.append('gUnk_082F3D74::\n')
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
                print(f'{reader.cursor} not in second_level {num_objects}')
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

    def extract_gUnk_089FB770(self) -> None:
        symbol_name = 'gUnk_089FB770'

        symbol = self.current_controller.symbols.find_symbol_by_name(symbol_name)
        if symbol is None:
            self.api.show_error(self.name, f'Could not find symbol {symbol_name}')
            return

        data = self.current_controller.rom.get_bytes(symbol.address, symbol.address+symbol.length)
        reader = Reader(data, self.current_controller.symbols)

        first_level = []
        second_level = []

        lines = []
        lines.append('gUnk_089FB770::\n')
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
            lines.append(f'\t.byte {extra_x_off}, {extra_y_off}\n')

            extra_x_off = reader.read_s8()
            extra_y_off = reader.read_s8()
            lines.append(f'\t.byte {extra_x_off}, {extra_y_off}\n')

        with open(os.path.join(get_repo_location(), 'build', 'tmc', 'assets', 'sprites', 'extraFrameOffsets.s'), 'w') as file:
            file.writelines(lines)

    def extract_fixed_type_gfx_data(self) -> None:
        symbol_name = 'gFixedTypeGfxData'

        symbol = self.current_controller.symbols.find_symbol_by_name(symbol_name)
        if symbol is None:
            self.api.show_error(self.name, f'Could not find symbol {symbol_name}')
            return

        data = self.current_controller.rom.get_bytes(symbol.address, symbol.address+symbol.length)
        reader = Reader(data, self.current_controller.symbols)

        lines = []
        lines.append('gFixedTypeGfxData::\n')

        index = 0
        while reader.cursor < symbol.length:
            pointer = reader.read_u32()
            gfx_data_ptr = pointer& 0x00FFFFFC
            compressed = pointer& 0x00000001

            maybe_size = ((pointer >> 0x10) & 0x7f00) >> 4

            print( (pointer& 0x7f000000) >> 0x18)
            gfx_data_len = ((pointer & 0x7F000000)>>24) * 0x200
            lines.append(f'\t.4byte {hex(gfx_data_ptr)} + {compressed} + {hex((gfx_data_len//0x200))}<<24  @{index}\n')
            self.gfx_assets.append(Asset(f'fixedTypeGfx_{index}', 'fixed_gfx ' + str(hex(maybe_size)), gfx_data_ptr, gfx_data_len, compressed))
            index += 1

        with open(os.path.join(get_repo_location(), 'build', 'tmc', 'assets', 'sprites', 'fixedTypeGfxDataPointers.s'), 'w') as file:
            file.writelines(lines)


    def extract_palette_groups(self) -> None:
        symbol_name = 'gPaletteGroups'
        symbol = self.current_controller.symbols.find_symbol_by_name(symbol_name)
        if symbol is None:
            self.api.show_error(self.name, f'Could not find symbol {symbol_name}')
            return

        data = self.current_controller.rom.get_bytes(symbol.address, symbol.address+symbol.length)
        reader = Reader(data, self.current_controller.symbols)

        lines = []
        lines.append('gPaletteGroups::\n')

        group_lines: list[str] = []
        palette_pointers: set[int] = set()
        palette_offsets: list[int] = []

        while reader.cursor < symbol.length:
            pointer = reader.read_u32()
            if pointer == 0:
                lines.append('\t.4byte 0\n')
                continue
            group_symbol = self.current_controller.symbols.get_symbol_at(pointer - ROM_OFFSET)
            palette_pointers.add(pointer)
            lines.append(f'\t.4byte {group_symbol.name}\n')

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
        data = self.current_controller.rom.get_bytes(symbol.address, symbol.address+symbol.length)
        reader = Reader(data, self.current_controller.symbols)
        continue_loading_palette_sets = True
        lines.append(f'{symbol.name}::\n')
        while continue_loading_palette_sets:
            global_palette_index = reader.read_u16()
            palette_load_offset = reader.read_u8()
            bitfield = reader.read_u8()

            num_palettes = bitfield & 0x0F
            if num_palettes == 0:
                num_palettes = 0x10
            continue_loading_palette_sets = (bitfield & 0x80 == 0x80)
            lines.append(f'\t.2byte {global_palette_index}\n')
            lines.append(f'\t.byte {palette_load_offset}\n')
            lines.append(f'\t.byte {num_palettes if num_palettes < 0x10 else 0} + {continue_loading_palette_sets*0x80}\n')
            for i in range(num_palettes):
                palette_indices.append(global_palette_index + i)
        return (lines, palette_indices)

    def extract_figurine_data(self) -> None:
        symbol_name = 'gFigurines'
        symbol = self.current_controller.symbols.find_symbol_by_name(symbol_name)
        if symbol is None:
            self.api.show_error(self.name, f'Could not find symbol {symbol_name}')
            return

        data = self.current_controller.rom.get_bytes(symbol.address, symbol.address+symbol.length)
        reader = Reader(data, self.current_controller.symbols)

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

        data = self.current_controller.rom.get_bytes(symbol.address, symbol.address+symbol.length)
        reader = Reader(data, self.current_controller.symbols)

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


        with open(os.path.join(get_repo_location(), 'build', 'tmc', 'assets', 'areas', 'metadata.s'), 'w') as file:
            file.writelines(lines)

        #self.extract_room_properties('Room_MinishWoods_Main')
        #self.extract_room_exit_list(self.current_controller.symbols.find_symbol_by_name('gExitLists_MinishWoods_Main'))
        print('done')

    def extract_area_table(self) -> None:
        symbol_name = 'gAreaTable'
        symbol = self.current_controller.symbols.find_symbol_by_name(symbol_name)
        if symbol is None:
            self.api.show_error(self.name, f'Could not find symbol {symbol_name}')
            return

        data = self.current_controller.rom.get_bytes(symbol.address, symbol.address+symbol.length)
        reader = Reader(data, self.current_controller.symbols)
        self.area_names = []
        self.room_names = []
        area_index = 0
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
        print(self.area_names)
        print(self.room_names)

        # Now extract all assets belonging to areas
        self.assets:list[Asset] = []
        self.extract_area_tilesets()
        assets_symbol = self.current_controller.symbols.find_symbol_by_name('gAssets')
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
                    assets[i-1].type += '_size_changed_from_' + hex(assets[i-1].size)
                    assets[i-1].size = asset.offset-assets[i-1].offset
                    print('Adapted offset of ' + assets[i-1].name)
            last_used_offset = asset.offset+asset.size
        last_used_offset = 0
        align_bytes = 0
        empty_bytes = 0
        with open('tmp/asset_log.txt', 'w') as file:
            for asset in assets:
                if asset.offset > last_used_offset:
                    diff = asset.offset-last_used_offset
                    if diff < 4:
#                        file.write(f'  .align 4 ({diff} bytes)\n')
                        align_bytes += diff
                        #print(hex(assets_symbol.address + asset.offset))
                    else:
                        file.write(f'# empty {hex(diff)}   from {hex(assets_symbol.address+previous_asset.offset+previous_asset.size)} to {hex(assets_symbol.address+asset.offset)}\n')
                        empty_bytes += diff
                elif asset.offset < last_used_offset:
                    if asset.offset == previous_asset.offset and asset.size == previous_asset.size:
                        file.write(f'  ^ same as previous: {asset.type} {asset.name}\n')
                        continue
                    file.write(f'%%% error {hex(last_used_offset-asset.offset)} bytes overlap\n')
                file.write(f'  - {asset.type} {asset.name}: {hex(asset.offset)} + {hex(asset.size)} [{"compressed" if asset.compressed else "raw"}]  @{hex(assets_symbol.address+asset.offset)}\n')

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
        data = self.current_controller.rom.get_bytes(symbol.address, symbol.address+symbol.length)
        reader = Reader(data, self.current_controller.symbols)
        room_index = 0
        while reader.cursor < symbol.length:
            room_symbol = self.read_symbol(reader)
            if room_symbol:
                self.room_names[area_index].append(room_symbol.name[5:])
                print(room_symbol.name)
            else:
                self.room_names[area_index].append('NULL')
                print('.4byte 0')
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
            print(tileset_symbol)
            if tileset_symbol:
                self.extract_asset(tileset_symbol, type)

    def extract_asset(self, symbol: Symbol, type: str) -> None:
        assets_symbol = self.current_controller.symbols.find_symbol_by_name('gAssets')

        data = self.current_controller.rom.get_bytes(symbol.address, symbol.address+symbol.length)
        reader = Reader(data, self.current_controller.symbols)
        i = 0
        while reader.cursor < symbol.length: # TODO use as general parsing code for asset list
            asset_offset = reader.read_u32() & 0x7FFFFFFF
            ram_address = reader.read_u32()
            property_2 = reader.read_u32()
            data_length = property_2 & 0x7FFFFFFF
            compressed = property_2& 0x80000000

            if ram_address == 0:
                print('Palette' , asset_offset)
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
                print(hex(asset_offset), compressed, hex(ram_address), hex(data_length))
            i += 1

    def extract_room_properties(self, symbol_name: str) -> None:
        symbol = self.current_controller.symbols.find_symbol_by_name(symbol_name)
        if symbol is None:
            self.api.show_error(self.name, f'Could not find symbol {symbol_name}')
            return

        data = self.current_controller.rom.get_bytes(symbol.address, symbol.address+symbol.length + 0x100)
        reader = Reader(data, self.current_controller.symbols)

        entity_list_1 = self.read_symbol(reader)
        entity_list_2 = self.read_symbol(reader)
        enemy_list = self.read_symbol(reader)
        tile_entity_list = self.read_symbol(reader)
        unknown_func_1 = self.read_symbol(reader)
        unknown_func_2 = self.read_symbol(reader)
        unknown_func_3 = self.read_symbol(reader)
        state_changing_func = self.read_symbol(reader)

        print('ETTTT')
        self.extract_entity_list(entity_list_1)
        self.extract_entity_list(entity_list_2)
        self.extract_entity_list(enemy_list)
        print('TILES')
        self.extract_tile_entity_list(tile_entity_list)

        print(entity_list_1, entity_list_2, enemy_list, tile_entity_list, unknown_func_1, unknown_func_2, unknown_func_3, state_changing_func)
        while reader.cursor < symbol.length:
            additional_entity_list = self.read_symbol(reader)
            print(additional_entity_list)
            # TODO detect delayed entity lists
            # TODO also detect other non-list pointers?
            # self.extract_entity_list(additional_entity_list)

    def extract_entity_list(self, symbol: Symbol) -> None:
        if symbol is None:
            return
        print('entity list ', symbol)
        data = self.current_controller.rom.get_bytes(symbol.address, symbol.address+symbol.length + 0x100)
        reader = Reader(data, self.current_controller.symbols)
        while True:
            type_and_unknowns = reader.read_u8()

            type = type_and_unknowns & 0x0F
            unknown_1 = (type_and_unknowns & 0xF0) >> 4
            unknowns = reader.read_u8()
            unknown_2 = unknowns & 0x0F
            unknown_3 = (unknowns & 0xF0) >> 4
            subtype = reader.read_u8()
            params_a = reader.read_u8()
            params_b = reader.read_u32()
            params_c = reader.read_u32()
            params_d = reader.read_u32()
            if type_and_unknowns == 0xff: # End of list
                break
            print(type, hex(subtype))
            print(params_a,hex(params_b), hex(params_c), hex(params_d))


        if reader.cursor < symbol.length:
            print('@ unaccounted bytes')
            while reader.cursor < symbol.length:
                print(reader.read_u8())

    def extract_tile_entity_list(self, symbol: Symbol) -> None:
        if symbol is None:
            return
        print('tile entity list ', symbol)
        data = self.current_controller.rom.get_bytes(symbol.address, symbol.address+symbol.length + 0x100)
        reader = Reader(data, self.current_controller.symbols)
        while True:
            type = reader.read_u8()
            params_a = reader.read_u8()
            params_b = reader.read_u16()
            params_c = reader.read_u16()
            params_d = reader.read_u16()
            if type == 0:
                break
            print(hex(type), hex(params_a), hex(params_b), hex(params_c), hex(params_d))


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

        data = self.current_controller.rom.get_bytes(symbol.address, symbol.address+symbol.length)
        reader = Reader(data, self.current_controller.symbols)

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
        self.gfx_assets.append(Asset('gFigurinePals', 'palette', 0x13040, 0x7740, False))
        self.gfx_assets.append(Asset('gFigurineGfx', 'gfx', 0x29cc80, 0x82780-0x8c0, False))



        # print gfx asset
        self.print_assets_list(self.assets_symbol, self.gfx_assets)

        # print('---------')
        # for replacement in self.replacements:
        #     print(replacement[0]+','+replacement[1])

    def get_compressed_length(self, addr: int, uncompressed_length: int) -> int:
        compressed_data = self.current_controller.rom.get_bytes(addr, addr+uncompressed_length)
        (decompressed_data, compressed_length) = GBALZ77.decompress(compressed_data)
        return compressed_length

    def extract_gfx_group(self, symbol: Symbol, group_index: int) -> list[str]:
        print(symbol)
        data = self.current_controller.rom.get_bytes(symbol.address, symbol.address+symbol.length)
        reader = Reader(data, self.current_controller.symbols)
        self.replacements.append((symbol.name, f'gGfxGroup_{group_index}'))
        gfx_index = 0
        lines = []
        lines.append(f'{symbol.name}::\n')
        while reader.cursor < symbol.length:
            unk0 = reader.read_u32()
            gfx_offset = unk0 & 0xFFFFFF
            dest = reader.read_u32()
            unk8 = reader.read_u32()
            size = unk8 & 0xFFFFFF
            terminator = unk0 & 0x80000000

            print(f'gGfx_{group_index}_{gfx_index}')
            compressed = unk8 & 0x80000000
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

            lines.append(f'\t.4byte {hex(gfx_offset)}+{hex(terminator)}+{hex(unk0 & 0xF000000)}, {hex(dest)}, {hex(uncompressed_size)} + {hex(compressed)} @ {gfx_index}\n')
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

        data = self.current_controller.rom.get_bytes(symbol.address, symbol.address+symbol.length)
        reader = Reader(data, self.current_controller.symbols)
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

    def extract_sprite_frame(self, symbol: Symbol) -> None:
        data = self.current_controller.rom.get_bytes(symbol.address, symbol.address+symbol.length)
        reader = Reader(data, self.current_controller.symbols)
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
        data = self.current_controller.rom.get_bytes(symbol.address, symbol.address+symbol.length)
        reader = Reader(data, self.current_controller.symbols)

        lines = []
        animation_lines = []
        lines.append(symbol.name + '::\n')
        i = 0
        while reader.cursor < symbol.length:
            animation_ptr = self.read_symbol(reader)
            if animation_ptr:
                lines.append(f'\t.4byte {symbol.name}_{i}\n')
                animation_lines += self.extract_animation(animation_ptr, f'{symbol.name}_{i}')
            else:
                lines.append(f'\t.4byte 0\n')
            i += 1

        with open(os.path.join(get_repo_location(), 'build', 'tmc', 'assets', 'animations', symbol.name+'.s'), 'w') as file:
            file.writelines(animation_lines)
            file.writelines(lines)

    def extract_animation(self, symbol: Symbol, new_name: str) -> list[str]:
        data = self.current_controller.rom.get_bytes(symbol.address, symbol.address+symbol.length)
        reader = Reader(data, self.current_controller.symbols)
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
        reader = Reader(data, self.current_controller.symbols)

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