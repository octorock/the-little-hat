from PySide6.QtCore import Signal
from PySide6.QtWidgets import QDockWidget, QWidget
from tlh.ui.ui_hexviewer import Ui_HexViewerDock

class HexViewerDock (QDockWidget):
    toggle_linked = Signal(bool)
    def __init__(self, parent: QWidget, title: str) -> None:
        super().__init__(parent)
        self.ui = Ui_HexViewerDock()
        self.ui.setupUi(self)
        self.setWindowTitle(title)


#        self.widget = HexAreaWidget(self, instance, self.ui.scrollBar, self.ui.labelStatusBar)
        #self.ui.horizontalLayout_2.insertWidget(0, self.widget)
        #self.ui.pushButtonGoto.clicked.connect(self.widget.show_goto_dialog)
        #self.ui.pushButtonLink.toggled.connect(self.toggle_linked.emit)
        #instance.linked_changed.connect(self.ui.pushButtonLink.setChecked)
