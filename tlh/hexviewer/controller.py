from dataclasses import dataclass
from typing import List
from tlh.data.symbols import Symbol, SymbolList
from tlh.hexviewer.display_byte import DisplayByte
from tlh.hexviewer.ui.hex_area import KeyType
from tlh.data.rom import Rom, get_rom
from tlh.data.database import get_annotation_database, get_pointer_database, get_constraint_database, get_symbol_database
from tlh.data.annotations import AnnotationList, Annotation
from tlh.data.pointer import Pointer, PointerList
from tlh.data.constraints import Constraint, ConstraintList, ConstraintManager, InvalidConstraintError
from tlh.hexviewer.diff_calculator import AbstractDiffCalculator, NoDiffCalculator
from PySide6.QtCore import QObject, Signal, QPoint
from PySide6.QtGui import QColor, QKeySequence, QShortcut, Qt
from PySide6.QtWidgets import QInputDialog, QMessageBox, QToolTip, QMenu, QApplication
from tlh.hexviewer.ui.dock import HexViewerDock
from tlh.const import ROM_OFFSET, ROM_SIZE, RomVariant
from tlh.hexviewer.address_resolver import AbstractAddressResolver, TrivialAddressResolver
from tlh import settings
from tlh.hexviewer.edit_annotation_dialog import EditAnnotationDialog
from tlh.hexviewer.edit_constraint_dialog import EditConstraintDialog
from tlh.hexviewer.edit_pointer_dialog import EditPointerDialog

class HexViewerController(QObject):
    '''
    Controls a single hex view and contains as much of the logic as possible
    '''

    signal_toggle_linked = Signal(bool)
    # Only relevant for linked
    signal_start_offset_moved = Signal(int)
    signal_cursor_moved = Signal(int)
    signal_selection_updated = Signal(int)
    signal_pointer_discovered = Signal(Pointer)
    signal_multiple_pointers_discovered = Signal(int, int)
    signal_only_in_current_marked = Signal(int, int)
    signal_remove_pointer = Signal(Pointer)

    def __init__(self, dock: HexViewerDock, rom_variant: RomVariant, rom: Rom) -> None:
        super().__init__(parent=dock)
        self.dock = dock
        self.area = dock.ui.hexArea
        self.status_bar = dock.ui.labelStatusBar
        self.scroll_bar = dock.ui.scrollBar
        self.rom_variant = rom_variant
        self.rom = rom
        self.address_resolver = TrivialAddressResolver()
        self.diff_calculator = NoDiffCalculator()

        # State TODO put into different class?
        self.is_linked = False
        self.start_offset = 0
        self.cursor = 0
        self.selected_bytes = 1

        self.display_byte_cache = {}  # TODO invalidate this cache if a constraint is added

        # Settings # TODO move elsewhere
        self.diff_color = QColor(158, 80, 88)  # QColor(244, 108, 117)
        self.pointer_color = QColor(68, 69, 34)
        self.default_annotation_color = QColor(50, 180, 50)
        self.default_selection_size = settings.get_default_selection_size()
        self.highlight_8_bytes = settings.is_highlight_8_bytes()

        self.contextmenu_handlers = []

        self.setup_scroll_bar()
        self.scroll_bar.valueChanged.connect(self.slot_scroll_bar_changed)

        # Connect to all necessary UI signals
        self.dock.ui.pushButtonGoto.clicked.connect(self.slot_show_goto_dialog)
        self.dock.ui.pushButtonLink.clicked.connect(self.slot_toggle_linked)
        # self.dock.ui.scrollBar.valueChanged.connect(self.on_scroll_bar_changed)
        self.area.signal_resized.connect(self.slot_on_resize)
        self.area.signal_scroll_wheel_changed.connect(
            self.slot_scroll_wheel_changed)
        self.area.signal_cursor_changed.connect(
            self.slot_update_cursor_from_offset)
        self.area.signal_selection_updated.connect(
            self.slot_update_selection_from_offset)
        self.area.signal_key_cursor_pressed.connect(
            self.slot_key_cursor_pressed)
        self.area.signal_key_selection_pressed.connect(
            self.slot_key_selection_pressed)
        self.area.signal_context_menu_shown.connect(
            self.slot_shot_context_menu)
        self.area.signal_show_tooltip_at_offset.connect(
            self.slot_show_tooltip_at_offset)
        self.area.signal_go_to_pointer_at_offset.connect(
            self.slot_go_to_pointer_at)

        # Keyboard shortcuts
        QShortcut(QKeySequence(Qt.Key_G), self.dock,
                  self.slot_show_goto_dialog, context=Qt.WidgetWithChildrenShortcut)
        QShortcut(QKeySequence(Qt.CTRL | Qt.Key_C), self.dock,
                  self.copy_selected_bytes, context=Qt.WidgetWithChildrenShortcut)
        QShortcut(QKeySequence(Qt.CTRL | Qt.Key_A), self.dock,
                  self.mark_as_all_pointer, context=Qt.WidgetWithChildrenShortcut)
        QShortcut(QKeySequence(Qt.Key_4), self.dock, lambda:self.update_selected_bytes(4),
                  context=Qt.WidgetWithChildrenShortcut)
        QShortcut(QKeySequence(Qt.Key_8), self.dock, lambda:self.update_selected_bytes(8),
                  context=Qt.WidgetWithChildrenShortcut)
        QShortcut(QKeySequence(Qt.Key_F3), self.dock, self.slot_jump_to_next_diff,
                  context=Qt.WidgetWithChildrenShortcut)
        QShortcut(QKeySequence(Qt.Key_Delete), self.dock, self.slot_delete_current_pointer,
                  context=Qt.WidgetWithChildrenShortcut)

        # TODO tmp
        QShortcut(QKeySequence(Qt.Key_Tab), self.dock, lambda:(self.update_cursor(self.cursor+5), self.update_selected_bytes(4)),
                  context=Qt.WidgetWithChildrenShortcut) # Go to next midi command or whatever
        QShortcut(QKeySequence(Qt.Key_W), self.dock, lambda:(self.update_cursor(self.cursor+12), self.update_selected_bytes(4)),
                  context=Qt.WidgetWithChildrenShortcut)

        self.pointers: PointerList = None
        self.annotations: AnnotationList = None
        self.constraints: ConstraintList = None
        self.symbols: SymbolList = None

        if settings.is_using_constraints():
            self.update_pointers()
            get_pointer_database().pointers_changed.connect(self.slot_update_pointers)

        self.update_annotations()
        get_annotation_database().annotations_changed.connect(self.slot_update_annotations)

        if settings.is_using_constraints():
            self.update_constraints()
            get_constraint_database().constraints_changed.connect(self.slot_update_constraints)

        self.update_symbols()
        get_symbol_database().symbols_changed.connect(self.slot_update_symbols)

        self.update_hex_area()

        self.status_bar.setText('loaded')

    def update_pointers(self):
        if settings.is_using_constraints():
            pointer_database = get_pointer_database()
            self.pointers = pointer_database.get_pointers(self.rom_variant)

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

    def update_constraints(self):
        if settings.is_using_constraints():
            constraint_database = get_constraint_database()
            constraints = constraint_database.get_constraints()
            self.constraints = ConstraintList(constraints, self.rom_variant)

    def slot_update_constraints(self) -> None:
        self.update_constraints()
        self.request_repaint()

    def update_symbols(self):
        symbol_database = get_symbol_database()
        if symbol_database.are_symbols_loaded(self.rom_variant):
            self.symbols = symbol_database.get_symbols(self.rom_variant)
        else:
            self.symbols = None

    def slot_update_symbols(self) -> None:
        self.update_symbols()
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

    def invalidate(self) -> None:
        '''
        Invalidates all assumptions about the underlying data and requests a full repaint.
        Call this if the underlying rom changed.
        '''
        self.rom = get_rom(self.rom_variant)

        self.request_repaint()

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
        #print(f'updating hex area {self.dock.windowTitle()}') # TODO reduce the amount of repaint at the start

        data = self.get_bytes(
            self.start_offset,
            self.start_offset + self.area.number_of_lines_on_screen() * self.area.bytes_per_line
        )

        self.area.display_data = data

        # Build labels
        labels = []
        for l in range(self.area.number_of_lines_on_screen()):
            labels.append(self.get_local_label(
                self.start_offset + l * self.area.bytes_per_line))

        self.area.display_labels = labels

        self.area.repaint()

    def get_local_label(self, virtual_address: int) -> str:
        local_address = self.address_resolver.to_local(virtual_address)
        if local_address == -1:
            return ''
        return '%08X' % (local_address + ROM_OFFSET)

    def get_bytes(self, from_index: int, to_index: int) -> List[DisplayByte]:
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
            return DisplayByte('  ', None, False, [], [], [])

        # TODO make sure local address is < length of rom

        background = None

        byte_value = self.rom.get_byte(local_address)

        # annotation_color = self.is_annotation(local_address)
        # if annotation_color is not None:
        #     background = annotation_color
        # elif
        pointers = []

        if self.pointers is not None:
            pointers = self.pointers.get_pointers_at(local_address)

        if len(pointers) > 0:
            background = self.pointer_color
        elif self.diff_calculator.is_diffing(virtual_address):
            background = self.diff_color
        elif self.highlight_8_bytes and byte_value == 8: # Make visual pointer detection easier
            background = QColor(0, 40, 0)

        display_byte = DisplayByte(
            '%02X' % byte_value,
            background,
            self.is_selected(virtual_address),
            self.annotations.get_annotations_at(local_address),
            self.constraints.get_constraints_at(local_address) if self.constraints is not None else [],
            pointers
        )
        # self.display_byte_cache[virtual_address] = display_byte
        return display_byte

    def is_pointer(self, local_address: int) -> bool:
        return len(self.pointers.get_pointers_at(local_address)) > 0

    def get_pointers_at(self, virtual_address: int) -> List[Pointer]:
        local_address = self.address_resolver.to_local(virtual_address)
        if local_address == -1:
            return []
        return self.pointers.get_pointers_at(local_address)


    def is_selected(self, virtual_address: int) -> bool:
        if self.selected_bytes < 0:
            return virtual_address > self.cursor + self.selected_bytes and virtual_address <= self.cursor
        else:
            return virtual_address >= self.cursor and virtual_address < self.cursor + self.selected_bytes

    def slot_show_goto_dialog(self):
        (input_str, res) = QInputDialog.getText(
            self.dock, 'Goto', 'Enter local address to jump to')
        if res:
            # Parse as hex (TODO maybe as decimal, if no 0x and no ABCDEF)
            # TODO handle errors
            try:
                local_address = int(input_str, 16)
            except ValueError:
                # maybe it is a symbol?
                if self.symbols is not None:
                    symbol = self.symbols.find_symbol_by_name(input_str)
                    if symbol is not None:
                        local_address = symbol.address
                    else:
                        QMessageBox.critical(self.parent(), 'Goto', f'{input_str} is not an address or symbol.')
                        return
                else:
                    QMessageBox.critical(self.parent(), 'Goto', f'{input_str} is not an address and symbols are not loaded for {self.rom_variant}.')
                    return

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
        if self.selected_bytes != self.default_selection_size:
            self.update_selected_bytes(self.default_selection_size)

    def slot_update_cursor_from_offset(self, offset: int) -> None:
        self.update_cursor(self.start_offset + offset)

    def update_selected_bytes(self, selected_bytes: int) -> None:
        if self.is_linked:
            self.signal_selection_updated.emit(selected_bytes)
        else:
            self.set_selected_bytes(selected_bytes)

    def set_selected_bytes(self, selected_bytes: int) -> None:
        self.selected_bytes = selected_bytes
        self.update_status_bar()
        self.update_hex_area()

    def slot_update_selection_from_offset(self, offset: int) -> None:
        cursor = offset + self.start_offset
        selection = cursor - self.cursor
        if selection < 0:
            selection -= 1
        else:
            selection += 1
        self.update_selected_bytes(selection)

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

    def length(self) -> int:  # TODO move into address resolver? Take largest virtual address for this from constraint manager?
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
        local_address = self.address_resolver.to_local(self.cursor)
        if local_address == -1 or local_address > 0xffffff:
            text = 'Cursor not in used area '
        else:
            text = f'Cursor: {hex(local_address+ROM_OFFSET)}'

            if self.selected_bytes != 0:
                text += f' Bytes selected: {self.selected_bytes}'

            if self.symbols is not None:
                # Show symbol at cursor for USA if symbols are loaded from .map file
                symbol = self.symbols.get_symbol_at(local_address)
                if symbol is not None:
                    offset = local_address - symbol.address
                    text += f'\n{symbol.name} (+{offset}|{symbol.length}) [{symbol.file}] '

        self.status_bar.setText(text)

    def scroll_to_cursor(self):
        full_lines = self.area.number_of_lines_on_screen()-2
        # Is the cursor too far down?
        if (self.cursor - self.start_offset) // self.area.bytes_per_line >= full_lines:
            # Move to the cursor.
            # (self.cursor // self.area.bytes_per_line - self.number_of_lines_on_screen() -3) * self.area.bytes_per_line)
            self.update_start_offset(
                (self.cursor//self.area.bytes_per_line - full_lines)*self.area.bytes_per_line)

        # Is the cursor too far up?
        elif (self.cursor - self.start_offset) // self.area.bytes_per_line < 0:
            # Move to the cursor.
            self.update_start_offset(
                (self.cursor//self.area.bytes_per_line)*self.area.bytes_per_line)

    def slot_key_cursor_pressed(self, key: KeyType) -> None:
        if key == KeyType.UP:
            if self.cursor >= self.area.bytes_per_line:
                self.update_cursor(self.cursor - self.area.bytes_per_line)
        elif key == KeyType.DOWN:
            # TODO check bounds
            self.update_cursor(self.cursor + self.area.bytes_per_line)
        elif key == KeyType.LEFT:
            self.update_cursor(max(0, self.cursor - 1))
        elif key == KeyType.RIGHT:
            # TODO check bounds
            self.update_cursor(self.cursor + 1)
        elif key == KeyType.PAGE_UP:
            page_bytes = (self.area.number_of_lines_on_screen()-1) * \
                self.area.bytes_per_line
            if self.cursor >= page_bytes:
                self.update_cursor(self.cursor - page_bytes)
            elif self.cursor >= self.area.bytes_per_line:
                self.update_cursor(self.cursor % self.area.bytes_per_line)
        elif key == KeyType.PAGE_DOWN:
            # TODO check bounds
            page_bytes = (self.area.number_of_lines_on_screen()-1) * \
                self.area.bytes_per_line
            self.update_cursor(self.cursor + page_bytes)
        elif key == KeyType.HOME:
            self.update_cursor(self.cursor - self.cursor % self.area.bytes_per_line)
        elif key == KeyType.END:
            self.update_cursor(self.cursor - self.cursor % self.area.bytes_per_line + self.area.bytes_per_line - 1)

    def slot_key_selection_pressed(self, key: KeyType) -> None:
        if key == KeyType.LEFT:
            selection = self.selected_bytes-1
            if selection == 0:
                selection = -2
            # TODO file bounds
            self.update_selected_bytes(selection)
        elif key == KeyType.RIGHT:
            selection = self.selected_bytes+1
            if selection == -1:
                selection = 1
            # TODO file bounds
            self.update_selected_bytes(selection)
        elif key == KeyType.UP:
            selection = self.selected_bytes - self.area.bytes_per_line
            # TODO passing 0, file bounds
            self.update_selected_bytes(selection)
        elif key == KeyType.DOWN:
            selection = self.selected_bytes + self.area.bytes_per_line
            # TODO passing 0, file bounds
            self.update_selected_bytes(selection)
        else:
            # TODO
            pass

    def slot_shot_context_menu(self, pos: QPoint) -> None:
        menu = QMenu(self.dock)
        menu.addAction('Copy cursor address', self.copy_cursor_address)
        menu.addAction('Copy selected bytes', self.copy_selected_bytes)

        if self.symbols is not None:
            menu.addAction('Copy symbol at or before cursor address', self.slot_copy_symbol)

        if abs(self.selected_bytes) == 4:
            menu.addAction('Copy selected as pointer address',
                           self.copy_selected_pointer_address)
            menu.addSeparator()
            menu.addAction('Only mark as pointer', self.mark_as_pointer)
            if self.is_linked:
                menu.addAction(
                    'Mark as pointer in all linked editors and add constraint', self.mark_as_all_pointer)

        # General actions
        menu.addSeparator()
        menu.addAction('Add annotation at cursor',
                       self.open_new_annotation_dialog)
        menu.addAction('Add manual constraint at cursor',
                       self.open_new_constraint_dialog)
        if self.is_linked:
            menu.addAction('Mark selected bytes only in current variant',
                           self.mark_only_in_current)

        menu.addAction('Goto', self.slot_show_goto_dialog)

        # Allow plugins to add context menu entries by registering a context menu handler
        for handler in self.contextmenu_handlers:
            handler(self, menu)

        menu.exec_(pos)

    def copy_cursor_address(self):
        local_address = self.address_resolver.to_local(
            self.cursor) + ROM_OFFSET
        QApplication.clipboard().setText(hex(local_address).upper().replace('0X', '0x'))

    def copy_selected_bytes(self):
        QApplication.clipboard().setText(
            self.get_bytes_str(self.get_selected_range()))

    def get_local_address(self, virtual_address: int) -> int:
        return self.address_resolver.to_local(virtual_address)

    def slot_copy_symbol(self):
        symbol = self.symbols.get_symbol_at(self.address_resolver.to_local(self.cursor))
        if symbol is not None:
            QApplication.clipboard().setText(symbol.name)
        

    def get_bytes_str(self, range: range) -> str:
        results = []
        for local_address in map(self.get_local_address, range):
            if local_address != -1:
                results.append('%02X' % self.rom.get_byte(local_address))
        return ' '.join(results)

    def copy_selected_pointer_address(self):
        address = self.cursor
        if self.selected_bytes == -4:
            address -= 3
        points_to = self.get_as_pointer(address)
        QApplication.clipboard().setText(hex(points_to))

    def get_as_pointer(self, virtual_address: int) -> int:
        return self.rom.get_pointer(self.get_local_address(virtual_address))

    def get_selected_range(self) -> range:
        if self.selected_bytes < 0:
            return range(self.cursor + self.selected_bytes + 1, self.cursor + 1)
        else:
            return range(self.cursor, self.cursor + self.selected_bytes)

    def get_new_pointer_dialog(self):
        address = self.cursor
        if self.selected_bytes == -4:
            address -= 3
        points_to = self.get_as_pointer(address)

        pointer = Pointer(self.rom_variant, self.address_resolver.to_local(
            address), points_to, 5, settings.get_username())

        return EditPointerDialog(self.dock, pointer)

    def mark_as_pointer(self):
        if abs(self.selected_bytes) != 4:
            return
        dialog = self.get_new_pointer_dialog()
        dialog.pointer_changed.connect(self.add_new_pointer)
        dialog.show()

    def add_new_pointer(self, pointer: Pointer) -> None:
        if pointer.points_to < ROM_OFFSET or pointer.points_to > ROM_OFFSET + ROM_SIZE:
            QMessageBox.critical(self.dock, 'Add pointer and constraints', f'Address {hex(pointer.points_to)} is not inside the rom.')
            return
        get_pointer_database().add_pointer(pointer)

    def mark_as_all_pointer(self):
        if abs(self.selected_bytes) % 4 != 0:
            return

        if abs(self.selected_bytes) == 4: # Mark one pointer
            dialog = self.get_new_pointer_dialog()
            dialog.pointer_changed.connect(self.add_new_pointer_and_constraints)
            dialog.show()
        else: # Mark multiple pointers
            reply = QMessageBox.question(self.dock, 'Add pointer and constraints', f'Do you really want to mark {abs(self.selected_bytes)//4} pointers and add the corresponding constraints?')
            if reply == QMessageBox.Yes:
                base_address = self.cursor
                if self.selected_bytes <0:
                    base_address += self.selected_bytes + 1

                self.signal_multiple_pointers_discovered.emit(base_address, abs(self.selected_bytes)//4)

    def add_new_pointer_and_constraints(self, pointer: Pointer) -> None:
        if pointer.points_to < ROM_OFFSET or pointer.points_to > ROM_OFFSET + ROM_SIZE:
            QMessageBox.critical(self.dock, 'Add pointer and constraints', f'Address {hex(pointer.points_to)} is not inside the rom.')
            return
        self.signal_pointer_discovered.emit(pointer)
        
    def open_new_annotation_dialog(self):
        address = self.cursor
        length = abs(self.selected_bytes)
        if self.selected_bytes < 0:
            address += self.selected_bytes + 1
        annotation = Annotation(self.rom_variant, self.address_resolver.to_local(
            address), length, self.default_annotation_color, settings.get_username())
        dialog = EditAnnotationDialog(self.dock, annotation)
        dialog.annotation_changed.connect(self.add_new_annotation)
        dialog.show()

    def add_new_annotation(self, annotation: Annotation) -> None:
        get_annotation_database().add_annotation(annotation)


    def open_new_constraint_dialog(self):
        address = self.cursor
        constraint = Constraint(self.rom_variant, self.address_resolver.to_local(
            address), None, None, 5, settings.get_username(), None, True)
        dialog = EditConstraintDialog(self.dock, constraint)
        dialog.constraint_changed.connect(self.add_new_constraint)
        dialog.show()

    def add_new_constraint(self, constraint: Constraint) -> None:
        # Check that constraint is valid
        constraint_manager = ConstraintManager({RomVariant.USA, RomVariant.DEMO, RomVariant.EU, RomVariant.JP, RomVariant.DEMO_JP, RomVariant.CUSTOM, RomVariant.CUSTOM_EU, RomVariant.CUSTOM_JP, RomVariant.CUSTOM_DEMO_USA, RomVariant.CUSTOM_DEMO_JP})
        constraint_manager.add_all_constraints(
            get_constraint_database().get_constraints())
        try:
            constraint_manager.add_constraint(constraint)
            constraint_manager.rebuild_relations()
        except InvalidConstraintError as e:
            QMessageBox.critical(self.parent(), 'Add constraint', 'Invalid Constraint')
            return

        get_constraint_database().add_constraint(constraint)

    def mark_only_in_current(self) -> None:
        address = self.cursor
        length = abs(self.selected_bytes)
        if self.selected_bytes < 0:
            address += self.selected_bytes + 1
        self.signal_only_in_current_marked.emit(address, length)

    def slot_show_tooltip_at_offset(self, offset: int, pos: QPoint) -> None:
        virtual_address = self.start_offset + offset
        local_address = self.address_resolver.to_local(virtual_address)
        pointers = self.pointers.get_pointers_at(local_address)
        if len(pointers) == 0:
            QToolTip.hideText()
            return True
        text = f'Pointer to {hex(pointers[0].points_to)}'
        if self.symbols is not None:
            points_to = pointers[0].points_to-ROM_OFFSET
            symbol = self.symbols.get_symbol_at(points_to)
            if symbol is not None:
                offset = points_to - symbol.address
                text += f'\n{symbol.name} (+{offset}) [{symbol.file}]'
        QToolTip.showText(pos, text)

    def slot_go_to_pointer_at(self, offset: int) -> None:
        virtual_address = self.start_offset + offset
        local_address = self.address_resolver.to_local(virtual_address)
        pointers = self.pointers.get_pointers_at(local_address)
        if len(pointers) > 0:
            # just jump to the first pointer
            self.update_cursor(self.address_resolver.to_virtual(
                pointers[0].points_to-ROM_OFFSET))

    def slot_on_resize(self) -> None:
        self.setup_scroll_bar()
        self.update_hex_area()


    def is_diffing_and_not_pointer(self, virtual_address: int) -> None:
        local_address = self.address_resolver.to_local(virtual_address)
        if local_address == -1:
            return False
        if self.is_pointer(local_address):
            return False
        #return self.diff_calculator.is_diffing(virtual_address)

        if self.diff_calculator.is_diffing(virtual_address):
            # Also check that 3 bytes forward there is a 0x08
            return self.rom.get_byte(local_address+3) == 8
        return False

    def is_diffing(self, virtual_address: int) -> None:
        return self.diff_calculator.is_diffing(virtual_address)

    def slot_jump_to_next_diff(self) -> None:
        virtual_address = self.cursor
        if self.selected_bytes > 0:
            virtual_address += self.selected_bytes

        #while not self.is_diffing_and_not_pointer(virtual_address) and virtual_address < 0xfffffff:
        while not self.is_diffing(virtual_address) and virtual_address < 0xfffffff:

            # TODO end of file
            virtual_address += 1

        self.update_cursor(virtual_address)


    def slot_delete_current_pointer(self) -> None:
        if abs(self.selected_bytes) != 4:
            return
        address = self.cursor
        if self.selected_bytes == -4:
            address -= 3

        pointers = self.get_pointers_at(address)
        if len(pointers) != 1:
            return

        self.signal_remove_pointer.emit(pointers[0])

    def set_contextmenu_handlers(self, handlers) -> None:
        self.contextmenu_handlers = handlers