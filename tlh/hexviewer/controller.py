from dataclasses import dataclass
from tlh.data.rom import Rom, get_rom
from tlh.data.database import get_annotation_database, get_pointer_database
from tlh.data.annotations import AnnotationList
from tlh.data.pointer import Pointer, PointerList
from tlh.hexviewer.diff_calculator import AbstractDiffCalculator, NoDiffCalculator
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, Qt
from PySide6.QtWidgets import QWidget
from tlh.hexviewer.ui.dock import HexViewerDock
from tlh.const import RomVariant
from tlh.hexviewer.address_resolver import AbstractAddressResolver, TrivialAddressResolver

@dataclass
class DisplayByte:
    text: str
    background: QColor
    is_selected: bool


class HexViewerController(QObject):
    '''
    Controls a single hex view and contains as much of the logic as possible
    '''

    signal_toggle_linked = Signal(bool)

    def __init__(self, dock: HexViewerDock, rom_variant: RomVariant) -> None:
        super().__init__(parent=dock)
        self.dock = dock
        self.area = dock.ui.hexArea
        self.status_bar = dock.ui.labelStatusBar
        self.rom_variant = rom_variant
        self.rom = get_rom(rom_variant)
        self.address_resolver = TrivialAddressResolver()
        self.diff_calculator = NoDiffCalculator()

        # State TODO put into different class?
        self.is_linked = False
        self.start_offset = 0
        self.cursor = 100
        self.selected_bytes = 0
        self.displayed_bytes = []

        self.display_byte_cache = {}  # TODO invalidate this cache if a constraint is added

        # Settings # TODO move elsewhere
        self.diff_color = QColor(158, 80, 88)  # QColor(244, 108, 117)
        self.pointer_color = QColor(68, 69, 34)

        # Connect to all necessary UI signals
        # self.dock.ui.pushButtonGoto.connect(self.show_goto_dialog)
        self.dock.ui.pushButtonLink.clicked.connect(self.slot_toggle_linked)
        # self.dock.ui.scrollBar.valueChanged.connect(self.on_scroll_bar_changed)
        self.area.signal_resized.connect(self.update_hex_area)

        self.pointers: PointerList = None
        self.annotations: AnnotationList = None

        self.update_pointers()
        get_pointer_database().pointers_changed.connect(self.slot_update_pointers)

        self.update_annotations()
        get_annotation_database().annotations_changed.connect(self.slot_update_annotations)
        self.update_hex_area()

    def update_pointers(self):
        pointer_database = get_pointer_database()
        pointers = pointer_database.get_pointers()
        self.pointers = PointerList(pointers, self.rom_variant)

    def slot_update_pointers(self) -> None:
        self.update_pointers()
        self.request_repaint()

    def update_annotations(self):
        annotation_database = get_annotation_database()
        annotations = annotation_database.get_annotations()
        self.annotations = AnnotationList(annotations, self.rom_variant)
    
    def slot_update_annotations(self) -> None:
        self.update_annotations()
        self.request_repaint()

    def set_linked(self, linked: bool) -> None:
        self.is_linked = linked
        self.dock.ui.pushButtonLink.setChecked(linked)

    def set_address_resolver_and_diff_calculator(self, address_resolver: AbstractAddressResolver, diff_calculator: AbstractDiffCalculator) -> None:
        self.address_resolver = address_resolver
        self.diff_calculator = diff_calculator

    def slot_toggle_linked(self, linked: bool) -> None:
        # Don't emit if the button checked state was just set via set_linked
        if linked != self.is_linked:
            self.signal_toggle_linked.emit(linked)

    def request_repaint(self) -> None:
        '''
        Invalidates the display byte cache and repaints
        '''
        self.display_byte_cache = {}
        self.update_hex_area()

    def update_hex_area(self) -> None:
        '''
        Builds the display model for the hex area to paint
        '''
        # print('updating hex area') TODO reduce the amount of repaint at the start
        data = self.get_bytes(
            self.start_offset,
            self.start_offset + self.area.number_of_lines_on_screen() * self.area.bytes_per_line
        )

        self.area.display_data = data

        self.area.repaint()

    def get_bytes(self, from_index: int, to_index: int) -> list[DisplayByte]:
        return list(map(
            self.get_display_byte_for_virtual_address,
            range(from_index, to_index)
        ))

    def get_display_byte_for_virtual_address(self, virtual_address: int) -> DisplayByte:
        # TODO test if the cache actually improves performance or is just a memory waste
        if virtual_address in self.display_byte_cache:
            return self.display_byte_cache[virtual_address]

        local_address = self.address_resolver.to_local(virtual_address)
        if local_address == -1:
            return DisplayByte('  ', None, False)

        # TODO make sure local address is < length of rom

        background = None

        annotation_color = self.is_annotation(local_address)
        if annotation_color is not None:
            background = annotation_color
        elif self.is_pointer(local_address):
            background = self.pointer_color
        elif self.diff_calculator.is_diffing(virtual_address):
            background = self.diff_color

        display_byte = DisplayByte(
            '%02X' % self.rom.get_byte(local_address),
            background,
            False # TODO is_selected
            )
        self.display_byte_cache[virtual_address] = display_byte
        return display_byte

    def is_pointer(self, local_address: int) -> bool:
        return len(self.pointers.get_pointers_at(local_address)) > 0

    def get_pointers_at(self, virtual_address: int) -> list[Pointer]:
        local_address = self.constraint_manager.to_local(
            self.rom_variant, virtual_address)
        if local_address == -1:
            return []
        return self.pointers.get_pointers_at(local_address)

    def is_annotation(self, local_address: int) -> QColor:
        # Just returns the first annotation, does not care about multiple overlapping
        annotations = self.annotations.get_annotations_at(local_address)
        if len(annotations) > 0:
            return annotations[0].color
        return None
