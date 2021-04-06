
from PySide6.QtGui import QColor
from tlh.const import RomVariant
from PySide6.QtCore import Signal
from tlh.data.annotations import Annotation
import typing
import PySide6
from PySide6.QtWidgets import QDialog
from tlh.ui.ui_edit_annotation_dialog import Ui_EditAnnotationDialog

class EditAnnotationDialog(QDialog):

    annotation_changed = Signal(Annotation)

    def __init__(self, parent, annotation: Annotation) -> None:
        super().__init__(parent=parent)
        self.ui = Ui_EditAnnotationDialog()
        self.ui.setupUi(self)

        self.rom_variant = annotation.rom_variant

        self.ui.lineEditVariant.setText(annotation.rom_variant)
        self.ui.lineEditAddress.setText(hex(annotation.address))
        self.ui.spinBoxLength.setValue(annotation.length)
        self.ui.lineEditColor.setText(annotation.color.name())
        self.ui.lineEditAuthor.setText(annotation.author)
        self.ui.plainTextEditNote.setPlainText(annotation.note)
        self.accepted.connect(self.on_accept)

    def get_annotation(self) -> Annotation:
        return Annotation(
            RomVariant(self.ui.lineEditVariant.text()),
            int(self.ui.lineEditAddress.text(), 16),
            self.ui.spinBoxLength.value(),
            QColor(self.ui.lineEditColor.text()),
            self.ui.lineEditAuthor.text(),
            self.ui.plainTextEditNote.toPlainText().strip()
        )
        
    def on_accept(self) -> None:
        self.annotation_changed.emit(self.get_annotation())