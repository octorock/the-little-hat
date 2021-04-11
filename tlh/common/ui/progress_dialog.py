

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QWidget
from tlh.ui.ui_progress_dialog import Ui_ProgressDialog

class ProgressDialog(QDialog):

    def __init__(self, parent: QWidget, title: str, text: str, abortable: bool) -> None:
        super().__init__(parent=parent)
        self.ui = Ui_ProgressDialog()
        self.ui.setupUi(self)

        self.setWindowTitle(title)
        self.ui.label.setText(text)

        self.ui.buttonBox.button(QDialogButtonBox.Abort).setDisabled(not abortable)


    def set_progress(self, value: int) -> None:
        self.ui.progressBar.setValue(value)