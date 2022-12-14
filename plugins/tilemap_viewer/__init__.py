from dataclasses import dataclass, field
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

class TilemapViewerPlugin:
    name = 'Tilemap Viewer'
    description = '''Description of the test plugin
Descriptions can have multiple lines'''

    def __init__(self, api: PluginApi) -> None:
        self.api = api

    def load(self) -> None:
        self.menu_entry = self.api.register_menu_entry('Tilemap Viewer', self.show_tilemap_viewer)
        self.menu_entry.setShortcut(QKeySequence(Qt.CTRL + Qt.Key_F4))

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

        assets_folder = os.path.join(settings.get_repo_location(), 'build', 'tmc', 'assets') # TODO handle different variants?

        area = 0
        room = 0
        tileset = 0


        area_folder = os.path.join(assets_folder, 'maps', 'areas', '000_MinishWoods')
        tileset_0_path = os.path.join(area_folder, 'tilesets', '0', 'gAreaTileset_MinishWoods_0_0.png')
        tileset_1_path = os.path.join(area_folder, 'tilesets', '0', 'gAreaTileset_MinishWoods_0_1.png')
        tileset_2_path = os.path.join(area_folder, 'tilesets', '0', 'gAreaTileset_MinishWoods_0_2.png')

        metatileset_path = os.path.join(area_folder, 'metatilesets', 'gAreaMetaTileset_MinishWoods_bottom.bin')
        metatilemap_path = os.path.join(area_folder, 'rooms', 'Main', 'gAreaRoomMap_MinishWoods_Main_bottom.bin')
        vram_offset = 0

        #tileset_0_path = os.path.join(area_folder, 'tilesets', '1', 'gAreaTileset_MinishWoods_1_0.png')
        #tileset_2_path = os.path.join(area_folder, 'tilesets', '1', 'gAreaTileset_MinishWoods_1_1.png')
        metatileset_path = os.path.join(area_folder, 'metatilesets', 'gAreaMetaTileset_MinishWoods_top.bin')
        metatilemap_path = os.path.join(area_folder, 'rooms', '00_Main', 'gAreaRoomMap_MinishWoods_Main_top.bin')
        #metatileset_path = '/tmp/decompressed_0.bin'
        #metatilemap_path = '/tmp/decompressed_1.bin'


        #area_folder = os.path.join(assets_folder, 'maps', 'areas', '136_DarkHyruleCastle')
        #metatileset_path = os.path.join(area_folder, 'metatilesets', 'gAreaMetaTileset_DarkHyruleCastle_bottom.bin')
        #metatilemap_path = os.path.join(area_folder,'rooms','3b','gAreaRoomMap_DarkHyruleCastle_3b_top.bin')

        vram_offset = 0x4000 # top maps index tiles starting at 0x4000

        palette_groups_file = AsmDataFile(os.path.join(settings.get_repo_location(), 'data', 'gfx', 'palette_groups.s'))

        common_palette_set = read_palette_set(palette_groups_file, 0xb)
        tileset_palette_set = read_palette_set(palette_groups_file, 28)
        tileset_palette_set.fill_undefined(common_palette_set)

        palette_set = tileset_palette_set

        palette_set.render_palettes()

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



TILE_SIZE = 8
META_TILE_SIZE = 16

class Palette:
    palette: List[int] = []

    def __init__(self, path: str) -> None:
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

class PaletteSet:
    palettes: List[Palette] = [None]*32 # 16 bg, 16 obj

    def get_palette(self, index: int) -> Palette:
        palette = None
        if index < len(self.palettes):
            palette = self.palettes[index]
        if palette is None:
            raise Exception(f'Palette {index} not found.')
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
    assets_folder = os.path.join(settings.get_repo_location(), 'build', 'tmc', 'assets') # TODO handle different variants?

    symbol_name = file.symbols['gPaletteGroups'].entries[index].attributes[0]
    symbol = file.symbols[symbol_name]
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
            palette_set.palettes[offset+i] = Palette(os.path.join(assets_folder, 'palettes', f'gPalette_{palette_id+i}.pal'))
    return palette_set


class VRAM:
    # The VRAM in tiles form but just storing the 8x8 tiles as PIL images.
    tiles: List[Image] = []

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
    metatiles: List[MetaTile] = []

    def __init__(self, path: str, vram: VRAM, vram_offset: int, palette_set: PaletteSet) -> None:
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
            tile_image = self.vram.tiles[tile_attr.tile_number]
            if tile_image is None:
                print(f'Could not find tile with number {hex(tile_attr.tile_number)}')
                tile_image = PIL.Image.new('RGBA', (TILE_SIZE, TILE_SIZE), (255, 0, 255, 255))

            palette = self.palette_set.get_palette(tile_attr.palette_index)
            # if metatile.id == 0x10:
            #     print('---', tile_attr.palette_index)
            #     print(palette.palette[0:3])
            # if metatile.id == 0x10:
            #     tile_image.save(f'/tmp/mc/{i}_before.png')
            tile_image = self.swap_palette(tile_image, palette)
            # if metatile.id == 0x10:
            #     tile_image.save(f'/tmp/mc/{i}_after.png')
            #tile_image = tile_image.convert('P', palette=palette.palette)
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

