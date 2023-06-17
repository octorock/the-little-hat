import os
from tlh.plugin.api import PluginApi
from PySide6.QtWidgets import QDockWidget
from PySide6.QtCore import Qt
from tlh.ui.ui_plugin_metasprite_dock import Ui_MetaspriteDock
import json
from PIL import Image

class MetaspriteViewerPlugin:
    name = 'Metasprite Viewer'
    description = '''Shows some metasprites'''

    def __init__(self, api: PluginApi) -> None:
        self.api = api

    def load(self) -> None:
        self.action_show_dock = self.api.register_menu_entry('Metasprite Viewer', self.slot_show_dock)

    def unload(self) -> None:
        self.api.remove_menu_entry(self.action_show_dock)

    def slot_show_dock(self):
        self.dock = ViewerDock(self.api.main_window, self.api)
        self.api.main_window.addDockWidget(Qt.BottomDockWidgetArea, self.dock)

class ViewerDock(QDockWidget):
    def __init__(self, parent, api: PluginApi) -> None:
        super().__init__('', parent)
        self.api = api
        self.ui = Ui_MetaspriteDock()
        self.ui.setupUi(self)
        #self.ui.graphicsView.addItem()

        image_folder = '/ssd/octorock/git/tmc/figurine1'
        image_data = json.load(open(os.path.join(image_folder, 'image.json'), 'r'))

        min_x = 9999
        min_y = 9999
        max_x = -9999
        max_y = -9999

        for layer in image_data['layers']:
            if layer['x'] < min_x:
                min_x = layer['x']
            if layer['y'] < min_y:
                min_y = layer['y']
            if layer['x']+layer['w'] > max_x:
                max_x = layer['x']+layer['w']
            if layer['y']+layer['h'] > max_y:
                max_y = layer['y']+layer['h']

        width = max_x - min_x
        height = max_y - min_y

        print(width, height)

        image = Image.new("RGBA", (width, height), (255, 255, 255, 0))
        print(image_data)


        for layer in image_data['layers']:
            obj_image = Image.open(os.path.join(image_folder, layer['file']))
            image.paste(obj_image, (layer['x'] - min_x, layer['y'] - min_y))
        image.save(open('/tmp/test.png', 'wb'))
'''
    final_image_min_x = 9999
    final_image_min_y = 9999
    final_image_max_x = -9999
    final_image_max_y = -9999
    for image, min_x, min_y in images_and_offsets:
      max_x = min_x + image.width
      max_y = min_y + image.height
      if min_x < final_image_min_x:
        final_image_min_x = min_x
      if min_y < final_image_min_y:
        final_image_min_y = min_y
      if max_x > final_image_max_x:
        final_image_max_x = max_x
      if max_y > final_image_max_y:
        final_image_max_y = max_y

    final_image_width = final_image_max_x - final_image_min_x
    final_image_height = final_image_max_y - final_image_min_y
    final_image = Image.new("RGBA", (final_image_width, final_image_height), (255, 255, 255, 0))

'''