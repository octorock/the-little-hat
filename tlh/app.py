import signal
import sys
from tlh.data.rom import Rom
from tlh.settings.ui import SettingsDialog

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (QApplication, QDialog, QDockWidget, QHBoxLayout,
                               QInputDialog, QMainWindow, QMenu, QMessageBox, QScrollBar, QWidget)

from tlh import settings
from tlh.builder.ui import BuilderWidget
from tlh.common.ui.dark_theme import apply_dark_theme
from tlh.hexeditor.ui import HexEditorWidget
from tlh.ui.ui_mainwindow import Ui_MainWindow
from tlh.ui.ui_settings import Ui_dialogSettings


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

        widget = BuilderWidget(self)
        self.setCentralWidget(widget)

        # Temp docks
        dock1 = QDockWidget(self)
        dock1.setObjectName('temp1')
        dock1.setWindowTitle('Temp1')
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock1)

        dock2 = QDockWidget('Hex Editor', self)
        dock2.setObjectName('dockHex')
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock2)

        rom = Rom(settings.get_rom_usa())
        rom2 = Rom(settings.get_rom_demo())
        hex_editor = QWidget(self)
        layout = QHBoxLayout(hex_editor)
        scrollBar = QScrollBar(hex_editor)
        widget = HexEditorWidget(hex_editor, rom, rom2, scrollBar)
        layout.addWidget(widget)
        layout.addWidget(scrollBar)
        hex_editor.setLayout(layout)
        dock2.setWidget(hex_editor)

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

            if layout_name in layouts: # TODO
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
        #actionResetLayout = QAction('Reset Layout', self.ui.menuLayouts)
        #self.ui.menuLayouts.addAction(actionResetLayout)
        #actionResetLayout.triggered.connect(lambda: self.restoreState(None))
        self.ui.menuLayouts.addSeparator()

        submenus = {}

        layouts = settings.get_layouts()

        for layout in layouts:
            elements = layout.name.split('/')

            action = QAction(elements[-1], self.ui.menuLayouts)
            action.triggered.connect(
                lambda *args, layout=layout: self.load_layout(layout))
            # checked is a named parameter? https://forum.learnpyqt.com/t/getting-typeerror-lambda-missing-1-required-positional-argument-checked/586/5

            # Add at correct location
            parent = self.ui.menuLayouts
            menus = {'children': submenus}
            for element in elements[:-1]:
                if not element in menus['children']:
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
        self.build_layouts_toolbar() # TODO would be nicer with a signal in the settings, but that would require the settings to be a QObject

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
