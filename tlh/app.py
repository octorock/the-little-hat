from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QAction, QIcon, QWindow
from tlh.common.ui.dark_theme import apply_dark_theme
import sys
from PySide6.QtWidgets import QApplication, QDialog, QDockWidget, QInputDialog, QMainWindow, QMenu, QMenuBar, QMessageBox
from tlh.builder.ui import BuilderWidget
import signal
from tlh.ui.ui_settings import Ui_dialogSettings
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

        widget = BuilderWidget(self)
        self.setCentralWidget(widget)

        # Temp docks
        dock1 = QDockWidget(self)
        dock1.setObjectName('temp1')
        dock1.setWindowTitle('Temp1')
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock1)

        # Restore layout
        settings = QSettings('octorock', 'the-little-hat')
        self.restoreState(settings.value('windowState'))
        self.restoreGeometry(settings.value('geometry'))

        """         self.setWindowTitle('The Little Hat')
        self.setWindowIcon(QIcon(':/icons/icon.png'))

        menubar = QMenuBar(self)
        self.setMenuBar(menubar)

        self.menuFile = QMenu('File', menubar)
        menubar.addMenu(self.menuFile)
        actionQuit = QAction('Quit', self.menuFile)
        actionQuit.setShortcut('Ctrl+Q')
        actionQuit.triggered.connect(app.quit)

        self.menuFile.addAction(actionQuit)

        self.menuTools = QMenu('Tools', menubar)
        menubar.addMenu(self.menuTools)

        actionSettings = QAction('Settings', self.menuTools)
        actionSettings.triggered.connect(self.show_settings_dialog)
        self.menuTools.addAction(actionSettings)

        self.menuLayouts = QMenu('Layouts', menubar)
        menubar.addMenu(self.menuLayouts)

        self.build_layouts_toolbar()

        widget = BuilderWidget(self)
        self.setCentralWidget(widget)

        # Temp docks
        dock1 = QDockWidget(self)
        dock1.setObjectName('temp1')
        dock1.setWindowTitle('Temp1')
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock1)

        # Restore layout
        settings = QSettings('octorock', 'the-little-hat')
        self.restoreState(settings.value('windowState'))
        self.restoreGeometry(settings.value('geometry'))
"""

    def closeEvent(self, event):
        settings = QSettings('octorock', 'the-little-hat')
        settings.setValue('windowState', self.saveState())
        settings.setValue('geometry', self.saveGeometry())

    def save_layout(self):
        (layout_name, res) = QInputDialog.getText(
            self, 'Save Layout', 'Enter name for the layout')
        if res:
            settings = QSettings('octorock', 'the-little-hat')
            layouts = settings.value('layouts', [])

            if layout_name in layouts:
                res = QMessageBox.question(
                    self, 'Save Layout', f'Do you want to overwrite the existing layout {layout_name}?')

                print(res)
                if res != QMessageBox.StandardButton.Yes:
                    return
            else:
                layouts.append(layout_name)
                settings.setValue('layouts', layouts)

            settings.setValue('layout_' + layout_name, self.saveState())

            self.build_layouts_toolbar()

    def load_layout(self, layout_name):
        print(f'Loading layout {layout_name}')
        settings = QSettings('octorock', 'the-little-hat')
        self.restoreState(settings.value('layout_'+layout_name))

    def build_layouts_toolbar(self):
        self.ui.menuLayouts.clear()
        actionSaveLayout = QAction('Save Layout...', self.ui.menuLayouts)
        self.ui.menuLayouts.addAction(actionSaveLayout)
        actionSaveLayout.triggered.connect(self.save_layout)
        self.ui.menuLayouts.addSeparator()

        submenus = {}

        settings = QSettings('octorock', 'the-little-hat')
        print('-' + settings.fileName())
        layouts = settings.value('layouts', [])
        layouts.sort()

        for layout in layouts:
            elements = layout.split('/')

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
                print(element)

            parent.addAction(action)

    def show_settings_dialog(self):
        dialog = QDialog(self)
        ui = Ui_dialogSettings()
        ui.setupUi(dialog)
        dialog.show()

    def show_about_dialog(self):
        QMessageBox.about(self, 'The Little Hat',
                          'The Little Hat\nVersion: 0.0')  # TODO


def run():
    # Be able to close with Ctrl+C in the terminal once Qt is started https://stackoverflow.com/a/5160720
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    arguments = sys.argv
    arguments.extend(['-style', 'Fusion']) # Remove warning about invalid style override
    app = QApplication(arguments)
    apply_dark_theme(app)

    window = MainWindow(app)

    window.show()
    return app.exec_()
