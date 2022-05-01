import PySide6
from PySide6.QtWidgets import QDockWidget
from PySide6.QtCore import Signal

class CloseDock(QDockWidget):
    '''
    Dock Widget that emits signal_closed when it is closed so that we can react to it
    '''
    signal_closed = Signal()
    def closeEvent(self, event: PySide6.QtGui.QCloseEvent) -> None:
        self.signal_closed.emit()
        return super().closeEvent(event)