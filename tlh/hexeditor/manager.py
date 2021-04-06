from enum import Enum
from tlh.data.annotations import Annotation

from PySide6.QtGui import QColor
from tlh.data.database import get_annotation_database, get_pointer_database, get_constraint_database
from tlh.data.constraints import Constraint, ConstraintManager
from tlh.data.rom import Rom, get_rom
from tlh.const import ROM_OFFSET, RomVariant
from PySide6.QtCore import QObject, Signal
from dataclasses import dataclass
from tlh.data.pointer import Pointer
from tlh import settings



@dataclass
class DisplayByte:
    text: str
    background: QColor




class HexEditorInstance(QObject):
    """
    Object that is passed to a single hex editor
    uses the constraint manager to translate from virtual to local addresses and vice versa
    """

    start_offset_moved = Signal(int)
    start_offset_moved_externally = Signal(int)
    cursor_moved = Signal(int)
    cursor_moved_externally = Signal(int)
    selection_updated = Signal(int)
    selection_updated_externally = Signal(int)
    pointer_discovered = Signal(Pointer)
    repaint_requested = Signal()

    def __init__(self, parent, rom_variant: RomVariant, rom: Rom, constraint_manager: ConstraintManager) -> None:
        super().__init__(parent=parent)
        self.manager = parent
        self.rom_variant = rom_variant
        self.rom = rom
        self.constraint_manager = constraint_manager

        self.display_byte_cache = {} # TODO invalidate this cache if a constraint is added


        self.diff_color = QColor(158, 80, 88)#QColor(244, 108, 117)
        self.pointer_color = QColor(68, 69, 34)

        self.pointers: list[Pointer] = []
        self.annotations: list[Annotation] = []

        self.update_pointers()
        pointer_database = get_pointer_database()
        pointer_database.pointers_changed.connect(self.update_pointers)

        self.update_annotations()
        annotation_database = get_annotation_database()
        annotation_database.annotations_changed.connect(self.update_annotations)

    def update_pointers(self):
        pointer_database = get_pointer_database()
        pointers = pointer_database.get_pointers()
        self.pointers.clear()
        for pointer in pointers:
            if pointer.rom_variant == self.rom_variant:
                self.pointers.append(pointer)
        # TODO sort pointer list?
        self.request_repaint()

    def update_annotations(self):
        annotation_database = get_annotation_database()
        annotations = annotation_database.get_annotations()
        self.annotations.clear()
        for annotation in annotations:
            if annotation.rom_variant == self.rom_variant:
                self.annotations.append(annotation)
        # TODO sort annotation list
        self.request_repaint()

    def request_repaint(self):
        self.display_byte_cache = {} # Invalidate TODO only at the added pointers?
        self.repaint_requested.emit()


    def get_local_label(self, index: int) -> str:
        local_address = self.constraint_manager.to_local(self.rom_variant, index)
        if local_address == -1:
            return ''
        return '%08X' % (local_address + ROM_OFFSET)

    def get_display_byte_for_index(self, index: int) -> DisplayByte:
        if index in self.display_byte_cache: # TODO test if the cache actually improves performance or is just a memory waste
            return self.display_byte_cache[index]

        local_address = self.constraint_manager.to_local(self.rom_variant, index)
        if local_address == -1:
            return DisplayByte('  ', None)

        # TODO make sure local address is < length of rom
        
        background = None

        annotation_color = self.is_annotation(index)
        if annotation_color is not None:
            background = annotation_color
        elif self.is_pointer(index):
            background = self.pointer_color
        elif self.manager.is_diffing(index):
            background = self.diff_color

        display_byte = DisplayByte('%02X' % self.rom.get_byte(local_address), background)
        self.display_byte_cache[index] = display_byte
        return display_byte

    def is_pointer(self, index: int) -> bool:
        # TODO binary search
        for pointer in self.pointers:
            if index >= pointer.address and index < pointer.address + 4:
                return True
        return False

    def is_annotation(self, index: int) -> QColor:
        # Just returns the first annotation, does not care about multiple overlapping
        for annotation in self.annotations:
            if index >= annotation.address and index < annotation.address + annotation.length:
                return annotation.color
        return None

    def get_bytes(self, from_index: int, to_index: int) -> list[DisplayByte]:
        return list(map(
            self.get_display_byte_for_index
                    , range(from_index, to_index)
        ))

    def length(self) -> int:
        # TODO calculate length of virtual rom
        return self.rom.length()

    def to_virtual(self, local_address: int) -> int:
        return self.constraint_manager.to_virtual(self.rom_variant, local_address)
    # def jump_to_local_address(self, local_address: int) -> None:
    #     virtual_address = self.constraint_manager.to_virtual(self.rom_variant, local_address)
    #     self.cursor_moved.emit(virtual_address)

    def get_local_address_str(self, virtual_address: int) -> str:
        return hex(self.get_local_address(virtual_address) + ROM_OFFSET)

    def get_local_address(self, virtual_address: int) -> int:
        return self.constraint_manager.to_local(self.rom_variant, virtual_address)

    def get_bytes_str(self, range: range) -> str:
        results = []
        for local_address in map(self.get_local_address, range):
            if local_address != -1:
                results.append('%02X' % self.rom.get_byte(local_address))
        return ' '.join(results)

    def get_as_pointer(self, virtual_address: int) -> int:
        return self.rom.get_pointer(self.get_local_address(virtual_address))



class HexEditorManager(QObject):
    """
    Manages all hex editors
    """
    def __init__(self, parent) -> None:
        super().__init__(parent=parent)
        self.variants = {RomVariant.USA, RomVariant.DEMO, RomVariant.JP}
        self.roms: dict[RomVariant, Rom] = {}
        for variant in self.variants:
            self.roms[variant] = get_rom(variant)
        self.instances: list[HexEditorInstance] = []

        self.constraint_manager = ConstraintManager(self.variants) # TODO make configurable
        self.update_constraints()
        get_constraint_database().constraints_changed.connect(self.update_constraints)

        

    def update_constraints(self):
        print('update constraints')
        self.constraint_manager.reset()
        self.constraint_manager.add_all_constraints(get_constraint_database().get_constraints())        
        for instance in self.instances:
            instance.request_repaint()

    def get_hex_editor_instance(self, rom_variant: RomVariant)-> HexEditorInstance:
        instance = HexEditorInstance(self, rom_variant, self.roms[rom_variant], self.constraint_manager)
        instance.start_offset_moved.connect(self.move_all_start_offsets)
        instance.cursor_moved.connect(self.move_all_cursors)
        instance.selection_updated.connect(self.update_all_selections)
        instance.pointer_discovered.connect(self.add_pointers_and_constraints)
        self.instances.append(instance)
        return instance

    def move_all_start_offsets(self, virtual_address: int) -> None:
        for instance in self.instances:
            instance.start_offset_moved_externally.emit(virtual_address)

    def move_all_cursors(self, virtual_address: int) ->None:
        for instance in self.instances:
            instance.cursor_moved_externally.emit(virtual_address)

    def update_all_selections(self, selected_bytes: int) ->None:
        for instance in self.instances:
            instance.selection_updated_externally.emit(selected_bytes)

    def is_diffing(self, virtual_address: int) -> bool:
        # TODO cache this, optimize accesses of rom data

        data = None
        for variant in self.variants:
            local_address = self.constraint_manager.to_local(variant, virtual_address)
            if local_address == -1:
                # does not count as a difference
                continue
            local_data = self.roms[variant].get_byte(local_address)
            if data is None:
                data = local_data
                continue
            if data != local_data:
                return True
        return False
        
    def add_pointers_and_constraints(self, pointer: Pointer) -> None:
        # Found a pointer that is the same for all variants

        new_pointers = [pointer]
        new_constraints = []
        virtual_address = self.constraint_manager.to_virtual(pointer.rom_variant, pointer.address)

        for variant in self.variants:
            if variant != pointer.rom_variant:
                address = self.constraint_manager.to_local(variant, virtual_address)
                points_to = self.roms[variant].get_pointer(address)
                # Add a corresponding pointer for this variant
                new_pointers.append(Pointer(variant, address, points_to, pointer.certainty, pointer.author, pointer.note))
                
                # Add a constraint for the places that these two pointers are pointing to, as the pointers should be the same
                # TODO check that it's actually a pointer into rom

                note = f'Pointer at {pointer.rom_variant} {hex(pointer.address)}'
                if pointer.note.strip() != '':
                    note += '\n' + pointer.note
                
                # TODO test that adding the added constraints are not invalid
                new_constraints.append(Constraint(pointer.rom_variant, pointer.points_to-ROM_OFFSET, variant, points_to-ROM_OFFSET, pointer.certainty, pointer.author, note))


        pointer_database = get_pointer_database()
        pointer_database.add_pointers(new_pointers)
        constraint_database = get_constraint_database()
        constraint_database.add_constraints(new_constraints)