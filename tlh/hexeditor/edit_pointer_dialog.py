
from PySide6.QtCore import Signal
from tlh.data.pointer import Pointer
import typing
import PySide6
from PySide6.QtWidgets import QDialog
from tlh.ui.ui_edit_pointer_dialog import Ui_EditPointerDialog

class EditPointerDialog(QDialog):

    pointer_changed = Signal(Pointer)

    def __init__(self, parent, pointer: Pointer) -> None:
        super().__init__(parent=parent)
        self.ui = Ui_EditPointerDialog()
        self.ui.setupUi(self)

        self.rom_variant = pointer.rom_variant

        self.ui.lineEditAddress.setText(hex(pointer.address))
        self.ui.lineEditPointsTo.setText(hex(pointer.points_to))
        self.ui.spinBoxCertainty.setValue(pointer.certainty)
        self.ui.lineEditAuthor.setText(pointer.author)
        self.ui.plainTextEditNote.setPlainText(pointer.note)
        self.accepted.connect(self.on_accept)

    def get_pointer(self) -> Pointer:
        return Pointer(
            self.rom_variant,
            int(self.ui.lineEditAddress.text(), 16),
            int(self.ui.lineEditPointsTo.text(), 16),
            self.ui.spinBoxCertainty.value(),
            self.ui.lineEditAuthor.text(),
            self.ui.plainTextEditNote.toPlainText().strip()
        )
        
    def on_accept(self) -> None:
        self.pointer_changed.emit(self.get_pointer())