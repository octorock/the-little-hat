
from tlh.hexviewer.edit_pointer_dialog import parse_address
from tlh.const import RomVariant
from PySide6.QtCore import Signal
from tlh.data.constraints import Constraint
from PySide6.QtWidgets import QDialog
from tlh.ui.ui_edit_constraint_dialog import Ui_EditConstraintDialog

class EditConstraintDialog(QDialog):

    constraint_changed = Signal(Constraint)

    def __init__(self, parent, constraint: Constraint) -> None:
        super().__init__(parent=parent)
        self.ui = Ui_EditConstraintDialog()
        self.ui.setupUi(self)

        self.ui.comboBoxVariantA.setCurrentIndex(self.get_variant_index(constraint.romA))
        self.ui.lineEditAddressA.setText(hex(constraint.addressA))
        self.ui.comboBoxVariantB.setCurrentIndex(self.get_variant_index(constraint.romB))
        if constraint.addressB is not None:
            self.ui.lineEditAddressB.setText(hex(constraint.addressB))
        self.ui.spinBoxCertainty.setValue(constraint.certainty)
        self.ui.lineEditAuthor.setText(constraint.author)
        self.ui.plainTextEditNote.setPlainText(constraint.note)
        self.ui.checkBoxEnabled.setChecked(constraint.enabled)
        self.accepted.connect(self.on_accept)

    def get_variant_index(self, variant: RomVariant) -> int:
        # TODO use a Qt Model for the combo box instead of static text values
        if variant == RomVariant.USA:
            return 0
        elif variant == RomVariant.JP:
            return 1
        elif variant == RomVariant.EU:
            return 2
        elif variant == RomVariant.DEMO:
            return 3
        elif variant == RomVariant.CUSTOM:
            return 4

        return -1

    def get_constraint(self) -> Constraint:
        return Constraint(
            RomVariant(self.ui.comboBoxVariantA.currentText()),
            parse_address(self.ui.lineEditAddressA.text()),
            RomVariant(self.ui.comboBoxVariantB.currentText()),
            parse_address(self.ui.lineEditAddressB.text()),
            self.ui.spinBoxCertainty.value(),
            self.ui.lineEditAuthor.text(),
            self.ui.plainTextEditNote.toPlainText().strip(),
            self.ui.checkBoxEnabled.isChecked()
        )
        
    def on_accept(self) -> None:
        self.constraint_changed.emit(self.get_constraint())