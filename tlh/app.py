import signal
import sys
from tlh.data.rom import get_rom, invalidate_rom
from tlh.common.ui.layout import Layout
from tlh.dock_manager import DockManager

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QAction, QIcon, QPixmap
from PySide6.QtWidgets import (QApplication, QInputDialog,
                               QMainWindow, QMenu, QMessageBox, QSplashScreen)

from tlh import settings
from tlh.common.ui.dark_theme import apply_dark_theme
from tlh.const import RomVariant
from tlh.data.database import get_symbol_database, initialize_databases, save_all_databases
from tlh.plugin.loader import load_plugins, reload_plugins
from tlh.settings.ui import SettingsDialog
from tlh.ui.ui_mainwindow import Ui_MainWindow
from os import path

class MainWindow(QMainWindow):
    def __init__(self, app):
        super().__init__()
        self.setWindowIcon(QIcon(':/icons/icon.png'))

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.ui.actionSave.triggered.connect(self.slot_save)
        self.ui.actionQuit.triggered.connect(app.quit)
        self.ui.actionSettings.triggered.connect(self.slot_show_settings_dialog)
        self.ui.actionAbout.triggered.connect(self.slot_show_about_dialog)

        self.update_hex_viewer_actions()

        self.ui.actionUSA.triggered.connect(
            lambda: self.dock_manager.add_hex_editor(RomVariant.USA))
        self.ui.actionDEMO.triggered.connect(
            lambda: self.dock_manager.add_hex_editor(RomVariant.DEMO))
        self.ui.actionEU.triggered.connect(
            lambda: self.dock_manager.add_hex_editor(RomVariant.EU))
        self.ui.actionJP.triggered.connect(
            lambda: self.dock_manager.add_hex_editor(RomVariant.JP))
        self.ui.actionDEMO_JP.triggered.connect(
            lambda: self.dock_manager.add_hex_editor(RomVariant.DEMO_JP))
        self.ui.actionCUSTOM.triggered.connect(
            lambda: self.dock_manager.add_hex_editor(RomVariant.CUSTOM)
        )
        self.ui.actionCUSTOM_EU.triggered.connect(
            lambda: self.dock_manager.add_hex_editor(RomVariant.CUSTOM_EU)
        )
        self.ui.actionCUSTOM_JP.triggered.connect(
            lambda: self.dock_manager.add_hex_editor(RomVariant.CUSTOM_JP)
        )
        self.ui.actionCUSTOM_DEMO_USA.triggered.connect(
            lambda: self.dock_manager.add_hex_editor(RomVariant.CUSTOM_DEMO_USA)
        )
        self.ui.actionCUSTOM_DEMO_JP.triggered.connect(
            lambda: self.dock_manager.add_hex_editor(RomVariant.CUSTOM_DEMO_JP)
        )
        self.ui.actionReloadCUSTOM.triggered.connect(self.slot_reload_custom_rom)
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
        self.ui.actionReloadPlugins.triggered.connect(reload_plugins)

        # Restore layout
        self.load_layout(settings.get_session_layout())


        if settings.is_always_load_symbols():
            self.load_symbols(RomVariant.CUSTOM, True)
            self.load_symbols(RomVariant.CUSTOM_EU, True)
            self.load_symbols(RomVariant.CUSTOM_JP, True)
            self.load_symbols(RomVariant.CUSTOM_DEMO_USA, True)
            self.load_symbols(RomVariant.CUSTOM_DEMO_JP, True)

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

    def slot_show_settings_dialog(self):
        dialog = SettingsDialog(self)
        dialog.show()
        dialog.finished.connect(self.settings_dialog_closed)

    def settings_dialog_closed(self, result: int):
        # TODO would be nicer with a signal in the settings, but that would require the settings to be a QObject
        self.build_layouts_toolbar()
        self.update_hex_viewer_actions()

    def slot_show_about_dialog(self):
        QMessageBox.about(self, 'The Little Hat',
                          'The Little Hat\nVersion: 0.0')  # TODO

    def update_hex_viewer_actions(self):
        self.ui.actionUSA.setDisabled(get_rom(RomVariant.USA) is None)
        self.ui.actionDEMO.setDisabled(get_rom(RomVariant.DEMO) is None)
        self.ui.actionJP.setDisabled(get_rom(RomVariant.JP) is None)
        self.ui.actionEU.setDisabled(get_rom(RomVariant.EU) is None)
        self.ui.actionDEMO_JP.setDisabled(get_rom(RomVariant.DEMO_JP) is None)
        self.ui.actionCUSTOM.setDisabled(get_rom(RomVariant.CUSTOM) is None)
        self.ui.actionCUSTOM_EU.setDisabled(get_rom(RomVariant.CUSTOM_EU) is None)
        self.ui.actionCUSTOM_JP.setDisabled(get_rom(RomVariant.CUSTOM_JP) is None)
        self.ui.actionCUSTOM_DEMO_USA.setDisabled(get_rom(RomVariant.CUSTOM_DEMO_USA) is None)
        self.ui.actionCUSTOM_DEMO_JP.setDisabled(get_rom(RomVariant.CUSTOM_DEMO_JP) is None)

    def slot_load_symbols(self):
        self.load_symbols(RomVariant.CUSTOM, False)
        self.load_symbols(RomVariant.CUSTOM_EU, False)
        self.load_symbols(RomVariant.CUSTOM_JP, False)
        self.load_symbols(RomVariant.CUSTOM_DEMO_USA, False)
        self.load_symbols(RomVariant.CUSTOM_DEMO_JP, False)

    def load_symbols(self, rom_variant: RomVariant, silent: bool) -> None:

        maps = {
            RomVariant.CUSTOM: 'tmc.map',
            RomVariant.CUSTOM_EU: 'tmc_eu.map',
            RomVariant.CUSTOM_JP: 'tmc_jp.map',
            RomVariant.CUSTOM_DEMO_USA: 'tmc_demo_usa.map',
            RomVariant.CUSTOM_DEMO_JP: 'tmc_demo_jp.map',
        }

        map_file = path.join(settings.get_repo_location(), maps[rom_variant])
        if not path.isfile(map_file):
            if silent:
                print(f'Could not find tmc.map file at {map_file}.')
            else:
                QMessageBox.critical(self, 'Load symbols from .map file', f'Could not find tmc.map file at {map_file}.')
            return

        get_symbol_database().load_symbols_from_map(rom_variant, map_file)
        if not silent:
            QMessageBox.information(self, 'Load symbols', f'Successfully loaded symbols for {rom_variant} rom from tmc.map file.')


    def slot_save(self) -> None:
        save_all_databases()

        # Misuse message dialog as notification https://stackoverflow.com/a/43134238
        msgbox = QMessageBox(self)
        msgbox.setWindowTitle('Save')
        msgbox.setText('Saved pointers, constraints and annotations.')
        msgbox.setModal(False)
        msgbox.show()

        # Automatically hide dialog after half a second
        timer = QTimer(self)
        timer.timeout.connect(msgbox.close)
        timer.timeout.connect(timer.stop)
        timer.timeout.connect(timer.deleteLater)
        timer.start(500)

    def slot_reload_custom_rom(self) -> None:
        invalidate_rom(RomVariant.CUSTOM)
        invalidate_rom(RomVariant.CUSTOM_EU)
        invalidate_rom(RomVariant.CUSTOM_JP)
        invalidate_rom(RomVariant.CUSTOM_DEMO_USA)
        invalidate_rom(RomVariant.CUSTOM_DEMO_JP)

        if settings.is_always_load_symbols():
            self.load_symbols(RomVariant.CUSTOM, True)
            self.load_symbols(RomVariant.CUSTOM_EU, True)
            self.load_symbols(RomVariant.CUSTOM_JP, True)
            self.load_symbols(RomVariant.CUSTOM_DEMO_USA, True)
            self.load_symbols(RomVariant.CUSTOM_DEMO_USA, True)

        # Reload all hex viewers for the CUSTOM variant

        controllers = self.dock_manager.hex_viewer_manager.get_controllers_for_variant(RomVariant.CUSTOM)
        for controller in controllers:
            controller.invalidate()
        controllers = self.dock_manager.hex_viewer_manager.get_controllers_for_variant(RomVariant.CUSTOM_EU)
        for controller in controllers:
            controller.invalidate()
        controllers = self.dock_manager.hex_viewer_manager.get_controllers_for_variant(RomVariant.CUSTOM_JP)
        for controller in controllers:
            controller.invalidate()
        controllers = self.dock_manager.hex_viewer_manager.get_controllers_for_variant(RomVariant.CUSTOM_DEMO_USA)
        for controller in controllers:
            controller.invalidate()
        controllers = self.dock_manager.hex_viewer_manager.get_controllers_for_variant(RomVariant.CUSTOM_DEMO_JP)
        for controller in controllers:
            controller.invalidate()
        # TODO also reload all linked viewers?

        self.update_hex_viewer_actions()
        # QMessageBox.information(self, 'Reloaded CUSTOM rom', 'Invalidated CUSTOM rom. You need to close and reopen CUSTOM hex viewers to view the new data.')

def run():
    # Be able to close with Ctrl+C in the terminal once Qt is started https://stackoverflow.com/a/5160720
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    arguments = sys.argv
    # Remove warning about invalid style override
    arguments.extend(['-style', 'Fusion'])
    app = QApplication(arguments)
    apply_dark_theme(app)

    # Show splash screen
    pixmap = QPixmap(':/icons/splash.png')
    splash = QSplashScreen(pixmap)
    splash.setWindowTitle('The Little Hat')
    splash.showMessage('loading...', alignment=Qt.AlignBottom | Qt.AlignCenter, color=Qt.white)
    splash.show()
    app.processEvents()

    window = MainWindow(app)

    window.show()
    splash.finish(window)
    return app.exec_()
