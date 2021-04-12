import signal
import sys
from tlh.data.symbols import load_symbols_from_map
from tlh.common.ui.progress_dialog import ProgressDialog
from tlh.data.rom import get_rom
from tlh.common.ui.layout import Layout
from tlh.dock_manager import DockManager

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (QApplication, QInputDialog,
                               QMainWindow, QMenu, QMessageBox)

from tlh import settings
from tlh.common.ui.dark_theme import apply_dark_theme
from tlh.const import RomVariant
from tlh.data.database import initialize_databases
from tlh.plugin.loader import load_plugins
from tlh.settings.ui import SettingsDialog
from tlh.ui.ui_mainwindow import Ui_MainWindow
from os import path

class MainWindow(QMainWindow):
    def __init__(self, app):
        super().__init__()
        self.setWindowIcon(QIcon(':/icons/icon.png'))

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.ui.actionQuit.triggered.connect(app.quit)
        self.ui.actionSettings.triggered.connect(self.show_settings_dialog)
        self.ui.actionAbout.triggered.connect(self.show_about_dialog)

        self.update_hex_viewer_actions()

        self.ui.actionUSA.triggered.connect(
            lambda: self.dock_manager.add_hex_editor(RomVariant.USA))
        self.ui.actionDEMO.triggered.connect(
            lambda: self.dock_manager.add_hex_editor(RomVariant.DEMO))
        self.ui.actionEU.triggered.connect(
            lambda: self.dock_manager.add_hex_editor(RomVariant.EU))
        self.ui.actionJP.triggered.connect(
            lambda: self.dock_manager.add_hex_editor(RomVariant.JP))
        self.ui.actionLoadSymbols.triggered.connect(self.slot_load_symbols)

        self.build_layouts_toolbar()

        # self.setCentralWidget(widget)
        # self.ui.centralwidget.hide()

        # Build all docks and then hide them, so they exist for layouts?
        self.ui.dockBuilder.hide()
        self.ui.menuTools.insertAction(self.ui.menuPlugins.menuAction(), self.ui.dockBuilder.toggleViewAction())

        initialize_databases(self)

        self.dock_manager = DockManager(self)

        # Load plugins
        load_plugins(self)

        # Restore layout
        self.load_layout(settings.get_session_layout())


        if settings.is_always_load_symbols():
            self.load_symbols(True)

    def closeEvent(self, event):
        layout = Layout('', self.saveState(), self.saveGeometry(),
                        self.dock_manager.save_state())
        settings.set_session_layout(layout)

    def save_layout(self):
        (layout_name, res) = QInputDialog.getText(
            self, 'Save Layout', 'Enter name for the layout')
        if res:
            layouts = settings.get_layouts()

            if layout_name in layouts:  # TODO
                res = QMessageBox.question(
                    self, 'Save Layout', f'Do you want to overwrite the existing layout {layout_name}?')

                print(res)
                if res != QMessageBox.StandardButton.Yes:
                    return
            else:
                layout = Layout(layout_name, self.saveState(
                ), self.saveGeometry(), self.dock_manager.save_state())
                layouts.append(layout)
                settings.set_layouts(layouts)

            self.build_layouts_toolbar()

    def load_layout(self, layout: settings.Layout):
        print(f'Loading layout {layout.name}')
        self.dock_manager.restore_state(layout.dock_state)
        self.restoreState(layout.state)
        self.restoreGeometry(layout.geometry)

    def build_layouts_toolbar(self):
        self.ui.menuLayouts.clear()
        actionSaveLayout = QAction('Save Layout...', self.ui.menuLayouts)
        self.ui.menuLayouts.addAction(actionSaveLayout)
        actionSaveLayout.triggered.connect(self.save_layout)
        # TODO how to reset the layout?
        # actionResetLayout = QAction('Reset Layout', self.ui.menuLayouts)
        # self.ui.menuLayouts.addAction(actionResetLayout)
        # actionResetLayout.triggered.connect(lambda: self.restoreState(None))
        self.ui.menuLayouts.addSeparator()

        submenus = {}

        layouts = settings.get_layouts()

        for layout in layouts:
            elements = layout.name.split('/')

            action = QAction(elements[-1], self.ui.menuLayouts)
            action.triggered.connect(
                lambda *args, layout=layout: self.load_layout(layout))
            # checked is a named parameter?
            # https://forum.learnpyqt.com/t/getting-typeerror-lambda-missing-1-required-positional-argument-checked/586/5

            # Add at correct location
            parent = self.ui.menuLayouts
            menus = {'children': submenus}
            for element in elements[:-1]:
                if element not in menus['children']:
                    menus['children'][element] = {
                        'menu': QMenu(element, parent),
                        'children': {}
                    }
                    parent.addMenu(menus['children'][element]['menu'])

                parent = menus['children'][element]['menu']
                menus = menus['children'][element]

            parent.addAction(action)

    def show_settings_dialog(self):
        dialog = SettingsDialog(self)
        dialog.show()
        dialog.finished.connect(self.settings_dialog_closed)

    def settings_dialog_closed(self, result: int):
        # TODO would be nicer with a signal in the settings, but that would require the settings to be a QObject
        self.build_layouts_toolbar()
        self.update_hex_viewer_actions()

    def show_about_dialog(self):
        QMessageBox.about(self, 'The Little Hat',
                          'The Little Hat\nVersion: 0.0')  # TODO

    def update_hex_viewer_actions(self):
        self.ui.actionUSA.setDisabled(get_rom(RomVariant.USA) is None)
        self.ui.actionDEMO.setDisabled(get_rom(RomVariant.DEMO) is None)
        self.ui.actionJP.setDisabled(get_rom(RomVariant.JP) is None)
        self.ui.actionEU.setDisabled(get_rom(RomVariant.EU) is None)

    def slot_load_symbols(self):
        self.load_symbols(False)

    def load_symbols(self, silent: bool) -> None:
        map_file = path.join(settings.get_repo_location(), 'tmc.map')
        if not path.isfile(map_file):
            if silent:
                print(f'Could not find tmc.map file at {map_file}.')    
            else:
                QMessageBox.critical(self, 'Load symbols from .map file', f'Could not find tmc.map file at {map_file}.')
            return
        load_symbols_from_map(map_file)
        if not silent:
            QMessageBox.information(self, 'Load symbols', 'Successfully loaded symbols for USA rom from tmc.map file.')



def run():
    # Be able to close with Ctrl+C in the terminal once Qt is started https://stackoverflow.com/a/5160720
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    arguments = sys.argv
    # Remove warning about invalid style override
    arguments.extend(['-style', 'Fusion'])
    app = QApplication(arguments)
    apply_dark_theme(app)

    window = MainWindow(app)

    window.show()
    return app.exec_()
