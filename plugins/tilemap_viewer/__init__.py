from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List
from plugins.tilemap_viewer.asm_data_file import AsmDataFile
from tlh import settings
from tlh.plugin.api import PluginApi
from PySide6.QtWidgets import QDockWidget, QGraphicsPixmapItem, QGraphicsScene, QGraphicsView
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap, QKeySequence
from tlh.ui.ui_plugin_tilemap_dock import Ui_TilemapDock
import os
from PIL.Image import Image
from PIL.ImageQt import ImageQt
import PIL
import array
from plugins.tilemap_viewer.ids import area_ids, room_ids
import json

class TilemapViewerPlugin:
    name = 'Tilemap Viewer'
    description = '''Description of the test plugin
Descriptions can have multiple lines'''

    def __init__(self, api: PluginApi) -> None:
        self.api = api

    def load(self) -> None:
        self.menu_entry = self.api.register_menu_entry('Tilemap Viewer', self.show_tilemap_viewer)
        self.menu_entry.setShortcut(QKeySequence(Qt.CTRL|Qt.Key_F4))

    def unload(self) -> None:
        self.api.remove_menu_entry(self.menu_entry)
        if self.dock is not None:
            self.dock.close()

    def show_tilemap_viewer(self):
        self.dock = TilemapDock(self.api.main_window, self.api)
        self.api.main_window.addDockWidget(Qt.BottomDockWidgetArea, self.dock)

class TilemapDock(QDockWidget):
    def __init__(self, parent, api: PluginApi) -> None:
        super().__init__('', parent)
        self.api = api
        self.ui = Ui_TilemapDock()
        self.ui.setupUi(self)

        self.ui.spinBoxRoomWidth.valueChanged.connect(self.slot_change_room_width)

        # Set up combo boxes.
        self.ui.comboBoxArea.addItems(area_ids)
        self.ui.comboBoxArea.currentIndexChanged.connect(self.slot_area_change)
        self.ui.comboBoxRoom.addItem('Please first select an area')
        self.ui.comboBoxRoom.currentIndexChanged.connect(self.slot_room_change)
        self.ui.comboBoxMap.addItem('Please first select a room')
        self.ui.comboBoxMap.currentIndexChanged.connect(self.slot_map_change)


        self.assets_folder = Path(settings.get_repo_location()) / 'build' / 'USA' / 'assets' # TODO handle different variants?

        return

        area = 0
        room = 0
        tileset = 0


        area_folder = os.path.join(assets_folder, 'maps', 'areas', '000_MinishWoods')
        tileset_0_path = os.path.join(area_folder, 'tilesets', '0', 'gAreaTileset_MinishWoods_0_0.png')
        tileset_1_path = os.path.join(area_folder, 'tilesets', '0', 'gAreaTileset_MinishWoods_0_1.png')
        tileset_2_path = os.path.join(area_folder, 'tilesets', '0', 'gAreaTileset_MinishWoods_0_2.png')

        metatileset_path = os.path.join(area_folder, 'metatileset', 'gAreaMetaTileset_MinishWoods_bottom.bin')
        metatilemap_path = os.path.join(area_folder, 'rooms', 'Main', 'gAreaRoomMap_MinishWoods_Main_bottom.bin')
        vram_offset = 0

        #tileset_0_path = os.path.join(area_folder, 'tilesets', '1', 'gAreaTileset_MinishWoods_1_0.png')
        #tileset_2_path = os.path.join(area_folder, 'tilesets', '1', 'gAreaTileset_MinishWoods_1_1.png')
        metatileset_path = os.path.join(area_folder, 'metatileset', 'gAreaMetaTileset_MinishWoods_top.bin')
        metatilemap_path = os.path.join(area_folder, 'rooms', '00_Main', 'gAreaRoomMap_MinishWoods_Main_top.bin')

        # CHECK UNKNOWN MAPS, first decompress them via scripts/check_lz.py
        #metatileset_path = '/tmp/decompressed_0.bin'
        metatilemap_path = '/tmp/decompressed_0.bin'


        #area_folder = os.path.join(assets_folder, 'maps', 'areas', '136_DarkHyruleCastle')
        #metatileset_path = os.path.join(area_folder, 'metatileset', 'gAreaMetaTileset_DarkHyruleCastle_bottom.bin')
        #metatilemap_path = os.path.join(area_folder,'rooms','3b','gAreaRoomMap_DarkHyruleCastle_3b_top.bin')

        vram_offset = 0x4000 # top maps index tiles starting at 0x4000

        palette_groups_file = AsmDataFile(os.path.join(settings.get_repo_location(), 'data', 'gfx', 'palette_groups.s'))

        common_palette_set = read_palette_set(palette_groups_file, 0xb)
        tileset_palette_set = read_palette_set(palette_groups_file, 28)
        tileset_palette_set.fill_undefined(common_palette_set)

        palette_set = tileset_palette_set

        #palette_set.render_palettes()

        """
gAreaTileset_MinishWoods_0:: @ 08100CF4
    tileset_tiles offset_gAreaTileset_MinishWoods_0_0, 0x6000000, 0x4000, 1
    tileset_tiles offset_gAreaTileset_MinishWoods_0_1, 0x6004000, 0x4000, 1
    tileset_tiles offset_gAreaTileset_MinishWoods_0_2, 0x6008000, 0x4000, 1
    tileset_palette_set 28, 1
        """

        vram = VRAM()
        vram.add_tileset(PIL.Image.open(tileset_0_path), 0x0)
        vram.add_tileset(PIL.Image.open(tileset_1_path), 0x4000)
        vram.add_tileset(PIL.Image.open(tileset_2_path), 0x8000)

        vram_image = vram.render_vram()

        scene = QGraphicsScene(self.ui.graphicsView)
        tileset_item = QGraphicsPixmapItem(self.get_pixmap(vram_image))
        scene.addItem(tileset_item)
        self.ui.graphicsView.setScene(scene)

        metatileset = MetaTileset(metatileset_path, vram, vram_offset, palette_set)
        metatileset_image = metatileset.render_meta_tileset()
        scene2 = QGraphicsScene(self.ui.graphicsView_2)
        metatileset_item = QGraphicsPixmapItem(self.get_pixmap(metatileset_image))
        scene2.addItem(metatileset_item)
        self.ui.graphicsView_2.setScene(scene2)

        self.metatilemap = MetaTilemap(metatilemap_path, metatileset)
        self.ui.spinBoxRoomWidth.setValue(63)
        #self.slot_change_room_width(42)

    def slot_change_room_width(self, width: int) -> None:
        if width != 0:

            if self.use_256_colors_bg:
                if self.map == 'collision_bottom':
                    self.map_debug.render(self.ui.graphicsView_3, width)
                else:
                    self.show_image(self.ui.graphicsView_3, self.tilemap.render_tilemap(width * 2))
            else:        
                height = (len(self.metatilemap.metatiles) + (width - 1)) // width
                self.ui.spinBoxRoomHeight.setValue(height)
                self.show_image(self.ui.graphicsView_3, self.metatilemap.render_meta_tile_map(width))


    def show_image(self, graphicsView: QGraphicsView, image: Image) -> None:
        scene = QGraphicsScene(graphicsView)
        item = QGraphicsPixmapItem(self.get_pixmap(image))
        scene.addItem(item)
        graphicsView.setScene(scene)



    def get_pixmap(self, pil_image: Image) -> QPixmap:
        #width, height = pil_image.size
        #data = pil_image.tobytes('raw', 'BGRA')
        #qimage = QImage(data, width, height, QImage.Format_ARGB32)
        qimage = ImageQt(pil_image)
        pixmap = QPixmap.fromImage(qimage)
        return pixmap

    def slot_area_change(self, new_area: int) -> None:
        print('area', new_area)
        self.area = new_area
        self.ui.comboBoxRoom.clear()
        self.ui.comboBoxRoom.addItems(room_ids[self.area])

    def slot_room_change(self, new_room: int) -> None:
        if new_room != -1:
            self.room = new_room
            room_path = self.assets_folder / self.get_room_path(self.area, self.room)
            room_config = json.load(open(room_path / 'config.json', 'r'))
            self.ui.comboBoxMap.clear()
            self.maps = []
            if len(room_config['maps']) == 0:
                self.ui.comboBoxMap.addItem('No maps defined for this room.')

            for map in room_config['maps']:
                self.maps.append(map['type'])
                self.ui.comboBoxMap.addItem(map['type'])

    def slot_map_change(self, new_map: int) -> None:
        if new_map != -1 and len(self.maps) > 0:
            self.map = self.maps[new_map]
            self.slot_render_map()


    # TODO move to common file
    def get_room_path(self, area: int, room: int) -> str:
        return f'maps/areas/{area:03}_{self.get_area_name(area)}/rooms/{room:02}_{self.get_room_name(area, room)}'

    def get_area_path(self, area: int) -> str:
        return f'maps/areas/{area:03}_{self.get_area_name(area)}'

    def get_area_name(self, area: int) -> str:
        id = area_ids[area]
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
        area_id = area_ids[area]
        id = room_ids[area][room]
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


    def slot_render_map(self) -> None:
        self.use_256_colors_bg = self.area in [0x20, 0x2d] # TODO detect this by map type?

        if 'special' in self.map:
            self.use_256_colors_bg = True
        self.errors: List[str] = []
        try:

            # TODO modify depending on map type
            if self.map == 'map_top' or self.map == 'map_top_special':
                self.vram_offset = 0x4000 # top maps index tiles starting at 0x4000
            else:
                self.vram_offset = 0
            
            # Find out tileset.
            print(f'--- {self.area} / {self.room}')
            area_config = json.load(open(self.assets_folder / self.get_area_path(self.area) / 'config.json', 'r'))
            room_config = json.load(open(self.assets_folder / self.get_room_path(self.area, self.room) / 'config.json', 'r'))
            if not 'tileset' in room_config:
                self.errors.append(f'No tileset in room config for {room_ids[self.area][self.room]}. Assuming tileset 0.')
                room_config['tileset'] = 0
            tileset_area = self.area
            tileset_area_config = area_config
            if 'tileset_ref' in area_config: # Handle tileset reference.
                tileset_area = area_config['tileset_ref']
                tileset_area_config = json.load(open(self.assets_folder / self.get_area_path(tileset_area) / 'config.json', 'r'))
                
            tileset_id = room_config['tileset']

            # Check that the tileset exists in this area.
            if tileset_id not in tileset_area_config['tilesets']:
                if len(tileset_area_config['tilesets']) == 0:
                    raise Exception(f'No tilesets defined for area {area_ids[tileset_area]}.')
                replacement_tileset = tileset_area_config['tilesets'][0]
                self.errors.append(f'No tileset with id {tileset_id} in area {area_ids[tileset_area]} (requested by room {room_ids[self.area][self.room]}). Using tileset {replacement_tileset} instead.')
                tileset_id = replacement_tileset

            self.load_tileset(tileset_area, tileset_id)

            if self.use_256_colors_bg:
                if self.map == 'map_bottom_special' or self.map == 'map_top_special':
                    self.load_tilemap()
                elif self.map == 'collision_bottom':
                     self.load_map_debug()
            else:
                self.load_metatileset(area_config['metatileset'])        
                self.load_metatilemap()

            if len(self.errors) > 0:
                self.api.show_error('Tilemap Viewer', '\n'.join(self.errors))

        except Exception as e:
            print(e)
            self.api.show_error('Tilemap Viewer', str(e))
            raise e


    def load_tileset(self, tileset_area: int, tileset_id: int) -> None:
        tileset_path = self.assets_folder / self.get_area_path(tileset_area) / 'tilesets' / str(tileset_id)
        tileset_config = json.load(open(tileset_path / 'config.json', 'r'))
        self.vram = VRAM()
        for entry in tileset_config['tiles']:
            if 'src' in entry:
                entry_path = tileset_path / (entry['src'] + '.png')
            elif 'ref' in entry:
                entry_path = self.assets_folder / (entry['ref'] + '.png')
            else:
                raise Exception(f'Neither src nor ref in tiles definition.')

            offset = int(entry['dest'], 0) - 0x6000000
            self.vram.add_tileset(PIL.Image.open(entry_path), offset)

    
        if not 'palette_set' in tileset_config:
            raise Exception(f'No palette set in tileset config for {room_ids[tileset_area][self.room]}.')
        palette_set_id = tileset_config['palette_set']
        self.load_palette_set(palette_set_id)


        if self.use_256_colors_bg:
            self.vram.apply_256_colors(self.palette_set)
        vram_image = self.vram.render_vram()

        self.show_image(self.ui.graphicsView, vram_image)


    def load_palette_set(self, palette_set_id: int) -> None:
        palette_groups_file = AsmDataFile(os.path.join(settings.get_repo_location(), 'data', 'gfx', 'palette_groups.s'))
        common_palette_set = read_palette_set(palette_groups_file, 0xb)
        tileset_palette_set = read_palette_set(palette_groups_file, palette_set_id)
        tileset_palette_set.fill_undefined(common_palette_set)
        self.palette_set = tileset_palette_set

    def load_metatileset(self, metatileset_area: int) -> None:
        # TODO fix metatileset for 256 color bgs
        metatileset_path = self.assets_folder / self.get_area_path(metatileset_area) / 'metatileset'
        metatileset_config = json.load(open(metatileset_path / 'config.json', 'r'))

        metatile_type = 'tiles_bottom'
        if self.map == 'map_top':
            metatile_type = 'tiles_top'

        if not metatile_type in metatileset_config:
            raise Exception(f'{metatile_type} not found in metatileset for area {area_ids[metatileset_area]}.')
        
        config = metatileset_config[metatile_type]

        if 'src' in config:
            metatileset_path = metatileset_path / (config['src'] + '.bin')
        elif 'ref' in config:
            metatileset_path = self.assets_folder / (config['ref'] + '.bin')
        else:
            raise Exception(f'Neither src nor ref in metatileset definition.')


        # if not 'tiles_top' in metatileset_config:
        #     raise Exception(f'tiles_top not found in metatileset for area {area_ids[self.area]}.')
        
        # metatileset_path = metatileset_path / (metatileset_config['tiles_top']['src'] + '.bin')
        metatileset = MetaTileset(metatileset_path, self.vram, self.vram_offset, self.palette_set)
        metatileset_image = metatileset.render_meta_tileset()
        self.show_image(self.ui.graphicsView_2, metatileset_image)
        self.metatileset = metatileset

#        self.metatilemap = MetaTilemap(metatilemap_path, metatileset)
 #       self.ui.spinBoxRoomWidth.setValue(63)
        #self.slot_change_room_width(42)

    def load_metatilemap(self) -> None:
        room_path = self.assets_folder / self.get_room_path(self.area, self.room)
        room_config = json.load(open(room_path / 'config.json', 'r'))
        for map in room_config['maps']:

            if map['type'] == self.map:
#            if map['type'] == 'map_top':
                if 'src' in map:
                    metatilemap_path = room_path / (map['src'] + '.bin')
                elif 'ref' in map:
                    metatilemap_path = self.assets_folder / (map['ref'] + '.bin')
                else:
                    raise Exception(f'Neither src nor ref in map definition.')

                self.metatilemap = MetaTilemap(metatilemap_path, self.metatileset)
                if 'width' in room_config:
                    width = room_config['width'] // 16
                    if self.ui.spinBoxRoomWidth.value() != width:
                        self.ui.spinBoxRoomWidth.setValue(width)
                    else:
                        self.slot_change_room_width(width)
                else:
                    self.errors.append(f'No width defined for room {room_ids[self.area][self.room]}. Assuming 42.')
                    if self.ui.spinBoxRoomWidth.value() != 42:
                        self.ui.spinBoxRoomWidth.setValue(42)
                    else:
                        self.slot_change_room_width(42)  
                return

        raise Exception(f'No {self.map} map found for room {room_ids[self.area][self.room]}.')

    def load_tilemap(self) -> None:
        room_path = self.assets_folder / self.get_room_path(self.area, self.room)
        room_config = json.load(open(room_path / 'config.json', 'r'))
        for map in room_config['maps']:

            if map['type'] == self.map:
                if 'src' in map:
                    tilemap = room_path / (map['src'] + '.bin')
                elif 'ref' in map:
                    tilemap = self.assets_folder / (map['ref'] + '.bin')
                else:
                    raise Exception(f'Neither src nor ref in map definition.')

                print('LOADED TILEMAP')
                self.tilemap = Tilemap(tilemap, self.vram, self.vram_offset)
                if 'width' in room_config:
                    width = room_config['width'] // 16
                    if self.ui.spinBoxRoomWidth.value() != width:
                        self.ui.spinBoxRoomWidth.setValue(width)
                    else:
                        self.slot_change_room_width(width)
                else:
                    self.errors.append(f'No width defined for room {room_ids[self.area][self.room]}. Assuming 42.')
                    if self.ui.spinBoxRoomWidth.value() != 42:
                        self.ui.spinBoxRoomWidth.setValue(42)
                    else:
                        self.slot_change_room_width(42)  
                return

        raise Exception(f'No {self.map} map found for room {room_ids[self.area][self.room]}.')

    def load_map_debug(self) -> None:
        room_path = self.assets_folder / self.get_room_path(self.area, self.room)
        room_config = json.load(open(room_path / 'config.json', 'r'))
        for map in room_config['maps']:

            if map['type'] == self.map:
                if 'src' in map:
                    map_path = room_path / (map['src'] + '.bin')
                elif 'ref' in map:
                    map_path = self.assets_folder / (map['ref'] + '.bin')
                else:
                    raise Exception(f'Neither src nor ref in map definition.')

                print('LOADED TILEMAP')
                self.map_debug = DebugMap(map_path)
                if 'width' in room_config:
                    width = room_config['width'] // 16
                    if self.ui.spinBoxRoomWidth.value() != width:
                        self.ui.spinBoxRoomWidth.setValue(width)
                    else:
                        self.slot_change_room_width(width)
                else:
                    self.errors.append(f'No width defined for room {room_ids[self.area][self.room]}. Assuming 42.')
                    if self.ui.spinBoxRoomWidth.value() != 42:
                        self.ui.spinBoxRoomWidth.setValue(42)
                    else:
                        self.slot_change_room_width(42)  
                return

        raise Exception(f'No {self.map} map found for room {room_ids[self.area][self.room]}.')

TILE_SIZE = 8
META_TILE_SIZE = 16

class Palette:
    palette: List[int] = []
    def __init__(self) -> None:
        self.palette = [255, 0, 255] * 32
    
    def read_from_file(self, path: str) -> None:
        self.palette = []
        with open(path, 'r') as f:
            if f.readline().strip() != 'JASC-PAL':
                raise Exception(f'Unknown palette file: {path}')
            f.readline() # TODO what does this line say (0100) max value in hex or something?
            num_colors = int(f.readline().strip())
            for i in range(0, num_colors):
                (r, g, b) = f.readline().split()
                self.palette.append(int(r))
                self.palette.append(int(g))
                self.palette.append(int(b))
        #print(self.palette)

UNDEFINED_PALETTE = Palette()

class PaletteSet:
    palettes: List[Palette] = [None]*32 # 16 bg, 16 obj

    def get_palette(self, index: int) -> Palette:
        palette = None
        if index < len(self.palettes):
            palette = self.palettes[index]
        if palette is None:
            print(f'Palette {index} not found.')
            return UNDEFINED_PALETTE
        return palette

    def render_palettes(self) -> None:
        for i, palette in enumerate(self.palettes):
            if palette is None:
                continue
            img = PIL.Image.new('RGB', (len(palette.palette)//3,1))
            for j in range(0, len(palette.palette)//3):
                img.putpixel((j, 0), (
                    palette.palette[j*3+0],
                    palette.palette[j*3+1],
                    palette.palette[j*3+2],
                ))

            img.save(f'/tmp/mc/palette_{i}.png')

    def fill_undefined(self, palette_set: 'PaletteSet') -> None:
        """Fill undefined palettes from another palette set"""
        for i, palette in enumerate(self.palettes):
            if palette is None:
                self.palettes[i] = palette_set.palettes[i]


def read_palette_set(file: AsmDataFile, index: int) -> PaletteSet:
    assets_folder = os.path.join(settings.get_repo_location(), 'build', 'USA', 'assets') # TODO handle different variants?

    symbol_name = file.symbols['gPaletteGroups'].entries[index].attributes[0]
    symbol = file.symbols[symbol_name]
    print(f'Read palette set from symbol {symbol_name}.')
    palette_set = PaletteSet()
    for entry in symbol.entries:
        print(entry)
        palette_id = int(entry.attributes_dict['palette'][4:])
        offset = 0
        if 'offset' in entry.attributes_dict:
            offset = int(entry.attributes_dict['offset'], 0)
        count = int(entry.attributes_dict['count'], 0)
        for i in range(0, count):
            print(f'Read palette {palette_id + i} to {offset+i}.')
            palette = Palette()
            palette.read_from_file(os.path.join(assets_folder, 'palettes', f'gPalette_{palette_id+i}.pal'))
            palette_set.palettes[offset+i] = palette
    return palette_set


class VRAM:
    # The VRAM in tiles form but just storing the 8x8 tiles as PIL images.
    tiles: List[Image]

    def __init__(self) -> None:
        self.tiles = []

    def add_tileset(self, image: Image, addr: int) -> None:
        #print(len(list(image.getdata())))
        #print(image.palette)
        (width, height) = image.size
        index = addr // (TILE_SIZE * TILE_SIZE // 2) # 4 bit per pixel
        if width != TILE_SIZE:
            raise Exception(f'Tileset images with width of {width} not yet supported.')
        tile_height = height // TILE_SIZE

        last_index = index + tile_height
        if len(self.tiles) < last_index:
            self.tiles += [None] * (last_index - len(self.tiles))
        for i in range(0, tile_height):
            # Extract tile image.
            self.tiles[index + i] = image.crop((0, i*TILE_SIZE, TILE_SIZE, i*TILE_SIZE + TILE_SIZE))

    def render_vram(self) -> Image:
        vram_width = 32
        vram_height = (len(self.tiles)+(vram_width-1))//vram_width
        image = PIL.Image.new('RGBA', (vram_width*TILE_SIZE, vram_height*TILE_SIZE), (255, 0, 255, 255))

        def get_xy(i):
            x = (i % vram_width) * TILE_SIZE
            y = (i // vram_width) * TILE_SIZE
            return (x, y)

        for i in range(0, len(self.tiles)):
            if self.tiles[i] is not None:
                image.paste(self.tiles[i], get_xy(i))

        return image

    def apply_256_colors(self, palette_set: PaletteSet) -> None:
        for j, tile in enumerate(self.tiles):
            if tile is None:
                continue
            output_image = PIL.Image.new('RGBA', (TILE_SIZE, TILE_SIZE))
            data = tile.getdata()
            #print(len(data))
            output_data = []
            for i in range(0, len(data)):
                #print(data[i])
                try:
                    val = 255 - data[i]
                except Exception as e:
                    print(data[i])
                    print(e)
                    return
                palette_id = val // 16
                index = (val % 16)
                palette = palette_set.get_palette(palette_id)
                #index = 15- data[i] // 16
                [r,g,b] = palette.palette[index*3:(index+1)*3]
                output_data.append((r,g,b))
                #print(len(palette.palette[index*3:(index+1)*3]))
                #output_data.append(255)
                #data[i:i+3] = palette.palette[index*3:(index+1)*3]

            #print(len(output_data))
            output_image.putdata(output_data)
            self.tiles[j] = output_image

@dataclass
class TileAttr:
    palette_index: int
    horizontal_flip : bool
    vertical_flip: bool
    tile_number: int

@dataclass
class MetaTile:
    tiles: List[TileAttr] = field(default_factory=list)
    image: Image = None

class MetaTileset:
    metatiles: List[MetaTile]

    def __init__(self, path: str, vram: VRAM, vram_offset: int, palette_set: PaletteSet) -> None:
        self.metatiles = []
        self.vram = vram
        self.palette_set = palette_set
        tile_number_offset = vram_offset // (TILE_SIZE * TILE_SIZE // 2)
        arr = array.array('H')
        with open(path, 'rb') as f:
            arr.frombytes(f.read())

        i = 0
        metatile = None
        for tile_attrs in arr:
            palette_index   = (tile_attrs & 0xF000) >> 0xC
            horizontal_flip = (tile_attrs & 0x0400) > 0
            vertical_flip   = (tile_attrs & 0x0800) > 0
            tile_number     = (tile_attrs & 0x03FF)

            if i % 4 == 0:
                if metatile is not None:
                    self.metatiles.append(metatile)
                metatile = MetaTile()
                metatile.id = i // 4 # TODO just for debug?

            metatile.tiles.append(TileAttr(palette_index, horizontal_flip, vertical_flip, tile_number + tile_number_offset))
            i += 1

        if metatile is not None:
            self.metatiles.append(metatile)

        for metatile in self.metatiles:
            self.render_metatile(metatile)

        #print(self.metatiles)

    # Render the image into the metatile object.
    def render_metatile(self, metatile: MetaTile) -> None:
        if len(metatile.tiles) != 4:
            return
            #raise Exception(f'Metatile should consist of four tile attrs, not {len(metatile.tiles)}.')
        metatile.image = PIL.Image.new('RGBA', (META_TILE_SIZE, META_TILE_SIZE))
        for i in range(0, 4):
            tile_attr = metatile.tiles[i]
            tile_image = None
            if tile_attr.tile_number < len(self.vram.tiles):
                tile_image = self.vram.tiles[tile_attr.tile_number]
            if tile_image is None:
                print(f'Could not find tile with number {hex(tile_attr.tile_number)}')
                tile_image = PIL.Image.new('RGBA', (TILE_SIZE, TILE_SIZE), (255, 0, 255, 255))

            palette = self.palette_set.get_palette(tile_attr.palette_index)

            tile_image = self.swap_palette(tile_image, palette)
            
            if tile_attr.horizontal_flip:
                tile_image = tile_image.transpose(PIL.Image.FLIP_LEFT_RIGHT)
            if tile_attr.vertical_flip:
                tile_image = tile_image.transpose(PIL.Image.FLIP_TOP_BOTTOM)
            metatile.image.paste(tile_image, ((i%2) * TILE_SIZE, (i//2)*TILE_SIZE))

    def swap_palette(self, image: Image, palette:Palette) -> None:
        output_image = PIL.Image.new('RGBA', (TILE_SIZE, TILE_SIZE))
        data = image.getdata()
        #print(len(data))
        output_data = []
        for i in range(0, len(data)):
            index = 15- data[i] // 16
            [r,g,b] = palette.palette[index*3:(index+1)*3]
            output_data.append((r,g,b))
            #print(len(palette.palette[index*3:(index+1)*3]))
            #output_data.append(255)
            #data[i:i+3] = palette.palette[index*3:(index+1)*3]

        #print(len(output_data))
        output_image.putdata(output_data)
        return output_image


        # orig_colors = len(image.getcolors())
        # #new_image = image.convert('P', palette=PIL.Image.ADAPTIVE, colors=16)
        # #print(new_image.getpalette())
        # p_img = PIL.Image.new('P', (16, 16))
        # test_pal = [0, 0, 0, 17, 17, 17, 34, 34, 34, 51, 51, 51, 68, 68, 68, 85, 85, 85, 102, 102, 102, 119, 119, 119, 136, 136, 136, 153, 153, 153, 170, 170, 170, 187, 187, 187, 204, 204, 204, 221, 221, 221, 238, 238, 238, 255, 255, 255]
        # #test_pal += [0,0,0] * (256-16)
        # p_img.putpalette(test_pal)

        # # show_pal = [0] * 16*4
        # quant_img = image.quantize(palette=p_img, dither=0, colors=16)
        # print(quant_img.getpalette())
        # quant_img.putpalette(palette.palette, rawmode='RGB')
        # return quant_img.convert('RGBA')
        # print(quant_img.getcolors())
        # quant_img.putpalette(show_pal, rawmode='RGBA')
        # quant_img = quant_img.convert('RGBA')
        # new_image.putpalette(palette.palette)
        # new_colors = len(new_image.getcolors())
        # if orig_colors != new_colors:
        #     print(f'{orig_colors} -> {new_colors}')
        # return new_image.convert('RGBA')

    def render_meta_tileset(self) -> Image:
        metatileset_width = 16
        metatileset_height = (len(self.metatiles) + (metatileset_width-1)) // metatileset_width
        image = PIL.Image.new('RGBA', (metatileset_width * META_TILE_SIZE, metatileset_height * META_TILE_SIZE))
        def get_xy(i):
            x = (i % metatileset_width) * META_TILE_SIZE
            y = (i // metatileset_width) * META_TILE_SIZE
            return (x, y)

        print(f'Render {len(self.metatiles)} metatiles.')

        for i, metatile in enumerate(self.metatiles):
            if metatile.image is not None:
                image.paste(metatile.image, get_xy(i))
        return image


class MetaTilemap:
    def __init__(self, path: str, metaTileset: MetaTileset) -> None:
        self.metaTileset = metaTileset
        arr = array.array('H')
        with open(path, 'rb') as f:
            arr.frombytes(f.read())
        self.metatiles = arr

    def render_meta_tile_map(self, width_in_metatiles: str) -> Image:
        if width_in_metatiles <= 0:
            return None
        height = (len(self.metatiles) + (width_in_metatiles - 1)) // width_in_metatiles
        image = PIL.Image.new('RGBA', (width_in_metatiles * META_TILE_SIZE, height * META_TILE_SIZE))
        def get_xy(i):
            x = (i % width_in_metatiles) * META_TILE_SIZE
            y = (i // width_in_metatiles) * META_TILE_SIZE
            return (x, y)

        for i, metatile in enumerate(self.metatiles):
            image.paste(self.metaTileset.metatiles[metatile].image, get_xy(i))
        return image



class Tilemap:
    tiles: List[Image]

    def __init__(self, path: str, vram: VRAM, vram_offset: int) -> None:
        self.tiles = []
        self.vram = vram
        tile_number_offset = vram_offset // (TILE_SIZE * TILE_SIZE // 2)
        arr = array.array('H')
        with open(path, 'rb') as f:
            arr.frombytes(f.read())

        for tile_attrs in arr:
            palette_index   = (tile_attrs & 0xF000) >> 0xC
            horizontal_flip = (tile_attrs & 0x0400) > 0
            vertical_flip   = (tile_attrs & 0x0800) > 0
            tile_number     = (tile_attrs & 0x03FF)

            tile_number += tile_number_offset

            tile_image = None
            if tile_number < len(self.vram.tiles):
                tile_image = self.vram.tiles[tile_number]
            if tile_image is None:
                print(f'Could not find tile with number {hex(tile_number)}')
                tile_image = PIL.Image.new('RGBA', (TILE_SIZE, TILE_SIZE), (255, 0, 255, 255))
            if horizontal_flip:
                tile_image = tile_image.transpose(PIL.Image.FLIP_LEFT_RIGHT)
            if vertical_flip:
                tile_image = tile_image.transpose(PIL.Image.FLIP_TOP_BOTTOM)
            self.tiles.append(tile_image)


    def render_tilemap(self, width_in_tiles: int) -> Image:
        CHUNK_SIZE = 32
        if width_in_tiles % CHUNK_SIZE != 0:
            width_in_tiles = ((width_in_tiles + CHUNK_SIZE - 1) // CHUNK_SIZE) * CHUNK_SIZE
            print(f'Increase width to {width_in_tiles} to fit 256x256 chunks')
#            raise Exception(f'Tilemap is not consisting of 256x256 chunks, because it has a width of {width_in_tiles} tiles.')

        width_in_chunks = width_in_tiles // CHUNK_SIZE

        # TODO render 256x256 chunks into final image
        tilemap_width = width_in_tiles  
        tilemap_height = (len(self.tiles) + (tilemap_width-1)) // tilemap_width
        image = PIL.Image.new('RGBA', (tilemap_width * TILE_SIZE, tilemap_height * TILE_SIZE))
        def get_xy(i):
            in_chunk = i % (CHUNK_SIZE * CHUNK_SIZE)
            chunk = i // (CHUNK_SIZE * CHUNK_SIZE)
            chunk_x = chunk % width_in_chunks
            chunk_y = chunk // width_in_chunks


            x = ((in_chunk % CHUNK_SIZE) + (chunk_x * CHUNK_SIZE)) * TILE_SIZE
            y = ((in_chunk // CHUNK_SIZE) + (chunk_y * CHUNK_SIZE)) * TILE_SIZE
            return (x, y)

        print(f'Render {len(self.tiles)} tiles.')

        for i, tile in enumerate(self.tiles):
            if tile is not None:
                image.paste(tile, get_xy(i))
        return image


# Show the map as numbers
class DebugMap:
    tiles: List[int]

    def __init__(self, path: str) -> None:
        self.tiles = []
        arr = array.array('b')
        with open(path, 'rb') as f:
            arr.frombytes(f.read())

        for elm in arr:
            self.tiles.append(elm)
    
    def render(self, graphicsView: QGraphicsView, width_in_tiles: int) -> None:
        scene = QGraphicsScene(graphicsView)

        RENDER_SCALE = 3

        def get_xy(i):
            x = (i % width_in_tiles) * TILE_SIZE * RENDER_SCALE
            y = (i // width_in_tiles) * TILE_SIZE * RENDER_SCALE
            return (x, y)
    
        for i, tile in enumerate(self.tiles):
            text = scene.addText(hex(tile)[2:])
            (x,y) = get_xy(i)
            text.setPos(x, y)
#            scene.addItem(item)
        graphicsView.setScene(scene)
# TODO Cache tileset and metatileset if it is the same for the new selected map
# TODO Cache modified tiles for metatiles.
# TODO Make first color in palette transparent.
# TODO Fix tileset for map_top_special of beanstalk climbs by using 16 colors and respecting the palette choice of the tiles