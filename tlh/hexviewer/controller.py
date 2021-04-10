from dataclasses import dataclass
from tlh.data.rom import Rom, get_rom
from tlh.data.database import get_annotation_database, get_pointer_database
from tlh.data.annotations import AnnotationList
from tlh.data.pointer import Pointer, PointerList
from tlh.hexviewer.diff_calculator import AbstractDiffCalculator, NoDiffCalculator
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QBrush, QColor, QKeySequence, QPainter, QShortcut, Qt
from PySide6.QtWidgets import QInputDialog, QWidget
from tlh.hexviewer.ui.dock import HexViewerDock
from tlh.const import ROM_OFFSET, RomVariant
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
    # Only relevant for linked
    signal_start_offset_moved = Signal(int)
    signal_cursor_moved = Signal(int)
    signal_section_updated = Signal(int)

    def __init__(self, dock: HexViewerDock, rom_variant: RomVariant) -> None:
        super().__init__(parent=dock)
        self.dock = dock
        self.area = dock.ui.hexArea
        self.status_bar = dock.ui.labelStatusBar
        self.scroll_bar = dock.ui.scrollBar
        self.rom_variant = rom_variant
        self.rom = get_rom(rom_variant)
        self.address_resolver = TrivialAddressResolver()
        self.diff_calculator = NoDiffCalculator()

        # State TODO put into different class?
        self.is_linked = False
        self.start_offset = 0
        self.cursor = 0
        self.selected_bytes = 1
        self.displayed_bytes = []

        self.display_byte_cache = {}  # TODO invalidate this cache if a constraint is added

        # Settings # TODO move elsewhere
        self.diff_color = QColor(158, 80, 88)  # QColor(244, 108, 117)
        self.pointer_color = QColor(68, 69, 34)

        self.setup_scroll_bar()
        self.scroll_bar.valueChanged.connect(self.slot_scroll_bar_changed)

        # Connect to all necessary UI signals
        self.dock.ui.pushButtonGoto.clicked.connect(self.slot_show_goto_dialog)
        self.dock.ui.pushButtonLink.clicked.connect(self.slot_toggle_linked)
        # self.dock.ui.scrollBar.valueChanged.connect(self.on_scroll_bar_changed)
        self.area.signal_resized.connect(self.update_hex_area)
        self.area.signal_scroll_wheel_changed.connect(self.slot_scroll_wheel_changed)

        # Keyboard shortcuts
        QShortcut(QKeySequence(Qt.CTRL + Qt.Key_G), self.dock, self.slot_show_goto_dialog, context=Qt.WidgetWithChildrenShortcut)

        self.pointers: PointerList = None
        self.annotations: AnnotationList = None

        self.update_pointers()
        get_pointer_database().pointers_changed.connect(self.slot_update_pointers)

        self.update_annotations()
        get_annotation_database().annotations_changed.connect(self.slot_update_annotations)
        self.update_hex_area()


        self.status_bar.setText('loaded')

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
        # if virtual_address in self.display_byte_cache:
        #     return self.display_byte_cache[virtual_address]

        local_address = self.address_resolver.to_local(virtual_address)
        if local_address == -1 or local_address > 0xffffff:
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
            self.is_selected(virtual_address)
            )
        # self.display_byte_cache[virtual_address] = display_byte
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

    def is_selected(self, virtual_address: int) -> bool:
        if self.selected_bytes < 0:
            return virtual_address > self.cursor + self.selected_bytes and virtual_address <= self.cursor
        else:
            return virtual_address >= self.cursor and virtual_address < self.cursor + self.selected_bytes



    def slot_show_goto_dialog(self):
        (local_address, res) = QInputDialog.getText(
        self.dock, 'Goto', 'Enter local address to jump to')
        if res:
            # Parse as hex (TODO maybe as decimal, if no 0x and no)
            # TODO handle errors
            local_address = int(local_address, 16)

            if local_address > ROM_OFFSET:
                local_address -= ROM_OFFSET
            # TODO error for everything that is not in [0x00000000, 0x00FFFFFF] or [0x08000000, 0x08FFFFFF]
            self.update_cursor(self.address_resolver.to_virtual(local_address))


    def update_start_offset(self, virtual_address: int) -> None:
        if self.is_linked:
            if self.start_offset != virtual_address:
                self.signal_start_offset_moved.emit(virtual_address)
        else:
            self.set_start_offset(virtual_address)

    def set_start_offset(self, virtual_address: int) -> None:
        self.start_offset = virtual_address
        self.scroll_bar.setValue(virtual_address//self.area.bytes_per_line)
        self.update_hex_area()

    def update_cursor(self, virtual_address: int) -> None:
        if self.is_linked:
            self.signal_cursor_moved.emit(virtual_address)
        else:
            self.set_cursor(virtual_address)

        self.scroll_to_cursor()

    def set_cursor(self, virtual_address: int) -> None:
        self.cursor = virtual_address
        self.update_status_bar()
        self.update_hex_area()

    def update_selected_bytes(self, selected_bytes: int) -> None:
        if self.is_linked:
            self.signal_selection_updated.emit(selected_bytes)
        else:
            self.set_selected_bytes(selected_bytes)

    def set_selected_bytes(self, selected_bytes: int) -> None:
        self.selected_bytes = selected_bytes
        self.update_hex_area()

    def setup_scroll_bar(self):
        # TODO call this again once the hex view has it's size / changes it's size
        self.scroll_bar.setMinimum(0)
        self.scroll_bar.setMaximum(
            self.number_of_rows() - self.area.number_of_lines_on_screen()+1)
        self.scroll_bar.setPageStep(self.area.number_of_lines_on_screen())

    def number_of_rows(self):
        length = self.length() 
        num_rows = length // self.area.bytes_per_line
        if length % self.area.bytes_per_line > 0:
            num_rows += 1
        return num_rows


    def length(self) -> int: # TODO move into address resolver? Take largest virtual address for this from constraint manager?
        return self.address_resolver.to_virtual(self.rom.length())


    def slot_scroll_bar_changed(self, value):
        self.update_start_offset(value * self.area.bytes_per_line)

    def slot_scroll_wheel_changed(self, lines_delta):
        if lines_delta <= 0:
            self.update_start_offset(max(self.start_offset + lines_delta, 0))
        else:
            self.update_start_offset(min(self.start_offset + lines_delta,
                                         (self.number_of_rows() - self.area.number_of_lines_on_screen() + 1)*self.area.bytes_per_line))
                                         
    def update_status_bar(self):
        text = f'Cursor: {self.get_local_address_str(self.cursor)}'

        if (self.selected_bytes != 0):
            text += f' Bytes selected: {self.selected_bytes}'
        self.status_bar.setText(text)

    def get_local_address_str(self, virtual_address: int) -> str:
        return hex(self.address_resolver.to_local(virtual_address) + ROM_OFFSET)


    def scroll_to_cursor(self):
        full_lines = self.area.number_of_lines_on_screen()-2
        # Is the cursor too far down?
        if (self.cursor - self.start_offset) // self.area.bytes_per_line >= full_lines:
            # Move to the cursor.
            self.update_start_offset((self.cursor//self.area.bytes_per_line - full_lines)*self.area.bytes_per_line)#(self.cursor // self.area.bytes_per_line - self.number_of_lines_on_screen() -3) * self.area.bytes_per_line)

        # Is the cursor too far up?
        elif (self.cursor - self.start_offset) // self.area.bytes_per_line < 0:
            # Move to the cursor.
            self.update_start_offset((self.cursor//self.area.bytes_per_line)*self.area.bytes_per_line)

