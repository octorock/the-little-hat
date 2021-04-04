import signal
import sys
from tlh.const import RomVariant
from tlh.hexeditor.manager import HexEditorManager

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (QApplication, QDockWidget, QHBoxLayout,
                               QInputDialog, QMainWindow, QMdiSubWindow, QMenu, QMessageBox,
                               QScrollBar, QWidget)

from tlh import settings
from tlh.common.ui.dark_theme import apply_dark_theme
from tlh.data.rom import Rom
from tlh.hexeditor.ui import HexEditorDock, HexEditorWidget
from tlh.settings.ui import SettingsDialog
from tlh.ui.ui_mainwindow import Ui_MainWindow


class MainWindow(QMainWindow):
    def __init__(self, app):
        super().__init__()
        self.setWindowIcon(QIcon(':/icons/icon.png'))

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.ui.actionQuit.triggered.connect(app.quit)
        self.ui.actionSettings.triggered.connect(self.show_settings_dialog)
        self.ui.actionAbout.triggered.connect(self.show_about_dialog)

        self.build_layouts_toolbar()

        #self.setCentralWidget(widget)
        #self.ui.centralwidget.hide()

        # Build all docks and then hide them, so they exist for layouts?
        self.ui.dockBuilder.hide()




        hex_editor_manager = HexEditorManager(self)
        # TODO make dynamic via menus?
        dock2 = QDockWidget('Hex Editor USA', self)
        dock2.setObjectName('dockHex')
        self.addDockWidget(Qt.DockWidgetArea.TopDockWidgetArea, dock2)
        dock2.setWidget(HexEditorDock(self, hex_editor_manager.get_hex_editor_instance(RomVariant.USA)))

        dock3 = QDockWidget('Hex Editor DEMO', self)
        dock3.setObjectName('dockHex2')
        self.addDockWidget(Qt.DockWidgetArea.TopDockWidgetArea, dock3)
        dock3.setWidget(HexEditorDock(self, hex_editor_manager.get_hex_editor_instance(RomVariant.DEMO)))

        dock4 = QDockWidget('Hex Editor JP', self)
        dock4.setObjectName('dockHex3')
        self.addDockWidget(Qt.DockWidgetArea.TopDockWidgetArea, dock4)
        dock4.setWidget(HexEditorDock(self, hex_editor_manager.get_hex_editor_instance(RomVariant.JP)))


        # Restore layout
        self.restoreState(settings.get_window_state())
        self.restoreGeometry(settings.get_geometry())

    def closeEvent(self, event):
        settings.set_window_state(self.saveState())
        settings.set_geometry(self.saveGeometry())

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
                layout = settings.Layout()
                layout.name = layout_name
                layout.windowState = self.saveState()
                layouts.append(layout)
                settings.set_layouts(layouts)

            self.build_layouts_toolbar()

    def load_layout(self, layout: settings.Layout):
        print(f'Loading layout {layout.name}')
        self.restoreState(layout.windowState)

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

    def show_about_dialog(self):
        QMessageBox.about(self, 'The Little Hat',
                          'The Little Hat\nVersion: 0.0')  # TODO


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
