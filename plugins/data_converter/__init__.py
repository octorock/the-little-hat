
from tlh.common.ui.close_dock import CloseDock
from tlh.plugin.api import PluginApi
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from tlh.ui.ui_plugin_dataconverter_dock import Ui_ConverterDock

class DataConverterPlugin:
    name = 'Data Converter'
    description = 'Converts between different representations of data'

    def __init__(self, api: PluginApi) -> None:
        self.api = api
        self.dock = None

    def load(self) -> None:
        self.action_show_converter = self.api.register_menu_entry('Data Converter', self.slot_show_converter)

    def unload(self) -> None:
        self.api.remove_menu_entry(self.action_show_converter)
        if self.dock is not None:
            self.dock.close()

    def slot_show_converter(self) -> None:
        self.dock = ConverterDock(self.api.main_window, self.api)
        self.api.main_window.addDockWidget(Qt.LeftDockWidgetArea, self.dock)

class ConverterDock(CloseDock):
    def __init__(self, parent, api: PluginApi) -> None:
        super().__init__('', parent)
        self.api = api
        self.ui = Ui_ConverterDock()
        self.ui.setupUi(self)

        self.ui.pushButtonTilePos.clicked.connect(self.slot_number2tilepos)
        self.ui.pushButtonTilePosOffset.clicked.connect(self.slot_number2tileposoffset)

    def slot_number2tilepos(self):
        number = QApplication.clipboard().text()
        try:
            number = int(number, 0)
        except ValueError:
            self.api.show_error(DataConverterPlugin.name, f'{number} is not a number.')
            return

        x = number % 0x40
        y = number // 0x40

        result = f'TILE_POS({x}, {y})'
        print(result)
        QApplication.clipboard().setText(result)

    def slot_number2tileposoffset(self):
        number = QApplication.clipboard().text()
        try:
            number = int(number, 0)
        except ValueError:
            self.api.show_error(DataConverterPlugin.name, f'{number} is not a number.')
            return
        y = number // 0x40
        number -= y * 0x40
        # Handle it probably being a positive x offset a row below
        if number < -0x20:
            y -= 1
            number += 0x40
        elif number > 0x20:
            y += 1
            number -= 0x40
        x = number

        result = f'TILE_POS({x}, {y})'
        print(result)
        QApplication.clipboard().setText(result)