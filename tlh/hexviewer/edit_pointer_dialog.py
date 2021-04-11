
from tlh.const import ROM_OFFSET
from PySide6.QtCore import Signal
from tlh.data.pointer import Pointer
from PySide6.QtWidgets import QDialog
from tlh.ui.ui_edit_pointer_dialog import Ui_EditPointerDialog

def parse_address(text: str) -> int:
    addr = int(text, 16)
    if addr > ROM_OFFSET:
        addr -= ROM_OFFSET
    return addr

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
            parse_address(self.ui.lineEditAddress.text()),
            int(self.ui.lineEditPointsTo.text(), 16),# TODO why do we store them with full address?
            self.ui.spinBoxCertainty.value(),
            self.ui.lineEditAuthor.text(),
            self.ui.plainTextEditNote.toPlainText().strip()
        )

        
    def on_accept(self) -> None:
        self.pointer_changed.emit(self.get_pointer())