from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QAction, QWindow
from common.ui.dark_theme import apply_dark_theme
import sys
from PySide6.QtWidgets import QApplication, QDockWidget, QInputDialog, QMainWindow, QMenu, QMenuBar, QMessageBox
from builder.ui import BuilderWidget
import signal


class MainWindow(QMainWindow):
    def __init__(self, app):
        super().__init__()
        self.setWindowTitle('The Little Hat')

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

        actionsSettings = QAction('Settings', self.menuTools)
        self.menuTools.addAction(actionsSettings)

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
        self.menuLayouts.clear()
        actionSaveLayout = QAction('Save Layout...', self.menuLayouts)
        self.menuLayouts.addAction(actionSaveLayout)
        actionSaveLayout.triggered.connect(self.save_layout)
        self.menuLayouts.addSeparator()

        settings = QSettings('octorock', 'the-little-hat')
        print('-' + settings.fileName())
        layouts = settings.value('layouts', [])
        for layout in layouts:
            action = QAction(layout, self.menuLayouts)
            self.menuLayouts.addAction(action)
            action.triggered.connect(
                lambda *args, layout=layout: self.load_layout(layout))
            # checked is a named parameter? https://forum.learnpyqt.com/t/getting-typeerror-lambda-missing-1-required-positional-argument-checked/586/5


def main():
    # Be able to close with Ctrl+C in the terminal once Qt is started https://stackoverflow.com/a/5160720
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QApplication(sys.argv)
    apply_dark_theme(app)

    window = MainWindow(app)

    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
