from tlh.hexviewer.diff_calculator import LinkedDiffCalculator, NoDiffCalculator
from tlh.hexviewer.address_resolver import LinkedAddressResolver, TrivialAddressResolver
from PySide6.QtWidgets import QMessageBox
from tlh.hexviewer.controller import HexViewerController
from tlh.data.annotations import AnnotationList

from PySide6.QtGui import QColor
from tlh.data.database import get_annotation_database, get_pointer_database, get_constraint_database
from tlh.data.constraints import Constraint, ConstraintManager
from tlh.data.rom import Rom, get_rom
from tlh.const import ROM_OFFSET, RomVariant
from PySide6.QtCore import QObject, Signal
from dataclasses import dataclass
from tlh.data.pointer import Pointer, PointerList
from tlh import settings

'''


class AbstractHexEditorInstance(QObject):
    start_offset_moved = Signal(int)
    start_offset_moved_externally = Signal(int)
    cursor_moved = Signal(int)
    cursor_moved_externally = Signal(int)
    selection_updated = Signal(int)
    selection_updated_externally = Signal(int)
    pointer_discovered = Signal(Pointer)
    only_in_current_marked = Signal(int, int)
    repaint_requested = Signal()
    linked_changed = Signal(bool)

    def __init__(self, parent) -> None:
        super().__init__(parent=parent)

class HexEditorInstance(AbstractHexEditorInstance):
    """
    Object that is passed to a single hex editor
    uses the constraint manager to translate from virtual to local addresses and vice versa
    """

    def __init__(self, parent, rom_variant: RomVariant, rom: Rom, constraint_manager: ConstraintManager) -> None:
        super().__init__(parent=parent)
        self.manager = parent
        self.rom_variant = rom_variant
        self.rom = rom
        self.constraint_manager = constraint_manager

        self.display_byte_cache = {} # TODO invalidate this cache if a constraint is added


        self.diff_color = QColor(158, 80, 88)#QColor(244, 108, 117)
        self.pointer_color = QColor(68, 69, 34)

        self.pointers: PointerList = None
        self.annotations: AnnotationList = None

        self.update_pointers()
        pointer_database = get_pointer_database()
        pointer_database.pointers_changed.connect(self.update_pointers)

        self.update_annotations()
        annotation_database = get_annotation_database()
        annotation_database.annotations_changed.connect(self.update_annotations)

    def update_pointers(self):
        pointer_database = get_pointer_database()
        pointers = pointer_database.get_pointers()
        self.pointers = PointerList(pointers, self.rom_variant)
        self.request_repaint()

    def update_annotations(self):
        annotation_database = get_annotation_database()
        annotations = annotation_database.get_annotations()
        self.annotations = AnnotationList(annotations, self.rom_variant)
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

        annotation_color = self.is_annotation(local_address)
        if annotation_color is not None:
            background = annotation_color
        elif self.is_pointer(local_address):
            background = self.pointer_color
        elif self.manager.is_diffing(index):
            background = self.diff_color

        display_byte = DisplayByte('%02X' % self.rom.get_byte(local_address), background)
        self.display_byte_cache[index] = display_byte
        return display_byte

    def is_pointer(self, local_address: int) -> bool:
        return len(self.pointers.get_pointers_at(local_address)) > 0

    def get_pointers_at(self, virtual_address: int) -> list[Pointer]:
        local_address = self.constraint_manager.to_local(self.rom_variant, virtual_address)
        if local_address == -1:
            return []
        return self.pointers.get_pointers_at(local_address)

    def is_annotation(self, local_address: int) -> QColor:
        # Just returns the first annotation, does not care about multiple overlapping
        annotations = self.annotations.get_annotations_at(local_address)
        if len(annotations) > 0:
            return annotations[0].color
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

    def to_local(self, virtual_address: int) -> int:
        return self.constraint_manager.to_local(self.rom_variant, virtual_address)
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



class SoloHexEditorInstance(AbstractHexEditorInstance):
    def __init__(self, parent, rom_variant: RomVariant, rom: Rom) -> None:
        super().__init__(parent=parent)
        self.rom_variant = rom_variant
        self.rom = rom

        self.display_byte_cache = {} # TODO invalidate this cache if a constraint is added
        self.pointer_color = QColor(68, 69, 34)

        self.pointers: PointerList = None
        self.annotations: AnnotationList = None

        self.update_pointers()
        pointer_database = get_pointer_database()
        pointer_database.pointers_changed.connect(self.update_pointers)

        self.update_annotations()
        annotation_database = get_annotation_database()
        annotation_database.annotations_changed.connect(self.update_annotations)


        self.start_offset_moved.connect(self.start_offset_moved_externally)
        self.cursor_moved.connect(self.cursor_moved_externally)
        self.selection_updated.connect(self.selection_updated_externally)

    def update_pointers(self):
        pointer_database = get_pointer_database()
        pointers = pointer_database.get_pointers()
        self.pointers = PointerList(pointers, self.rom_variant)
        self.request_repaint()

    def update_annotations(self):
        annotation_database = get_annotation_database()
        annotations = annotation_database.get_annotations()
        self.annotations = AnnotationList(annotations, self.rom_variant)
        self.request_repaint()

    def request_repaint(self):
        self.display_byte_cache = {} # Invalidate TODO only at the added pointers?
        self.repaint_requested.emit()


    def get_local_label(self, local_address: int) -> str:
        return '%08X' % (local_address + ROM_OFFSET)

    def get_display_byte_for_index(self, index: int) -> DisplayByte:
        if index in self.display_byte_cache: # TODO test if the cache actually improves performance or is just a memory waste
            return self.display_byte_cache[index]

        local_address = index

        # TODO make sure local address is < length of rom
        
        background = None

        annotation_color = self.is_annotation(local_address)
        if annotation_color is not None:
            background = annotation_color
        elif self.is_pointer(local_address):
            background = self.pointer_color

        display_byte = DisplayByte('%02X' % self.rom.get_byte(local_address), background)
        self.display_byte_cache[index] = display_byte
        return display_byte

    def is_pointer(self, local_address: int) -> bool:
        return len(self.pointers.get_pointers_at(local_address)) > 0

    def get_pointers_at(self, local_address: int) -> list[Pointer]:
        return self.pointers.get_pointers_at(local_address)

    def is_annotation(self, local_address: int) -> QColor:
        # Just returns the first annotation, does not care about multiple overlapping
        annotations = self.annotations.get_annotations_at(local_address)
        if len(annotations) > 0:
            return annotations[0].color
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
        return local_address

    def to_local(self, virtual_address: int) -> int:
        return virtual_address

    def get_local_address_str(self, virtual_address: int) -> str:
        return hex(self.get_local_address(virtual_address) + ROM_OFFSET)

    def get_local_address(self, virtual_address: int) -> int:
        return virtual_address

    def get_bytes_str(self, range: range) -> str:
        results = []
        for local_address in map(self.get_local_address, range):
            if local_address != -1:
                results.append('%02X' % self.rom.get_byte(local_address))
        return ' '.join(results)

    def get_as_pointer(self, virtual_address: int) -> int:
        return self.rom.get_pointer(self.get_local_address(virtual_address))
'''


class HexViewerManager(QObject):
    """
    Manages all hex viewers
    """

    def __init__(self, parent) -> None:
        super().__init__(parent=parent)
        self.controllers: list[HexViewerController] = []
        self.linked_controllers: list[HexViewerController] = []
        self.linked_variants: list[RomVariant] = []

        self.constraint_manager = ConstraintManager(
            {})  # TODO make configurable
        # self.update_constraints()
        get_constraint_database().constraints_changed.connect(self.update_constraints)

        self.linked_diff_calculator = LinkedDiffCalculator(
            self.constraint_manager, self.linked_variants)

    def register_controller(self, controller: HexViewerController) -> None:
        self.controllers.append(controller)
        # Link all signals connected to linked viewers
        controller.signal_toggle_linked.connect(
            lambda linked: self.slot_toggle_linked(controller, linked))
        controller.signal_start_offset_moved.connect(
            self.slot_move_linked_start_offset)
        controller.signal_cursor_moved.connect(self.slot_move_linked_cursor)
        controller.signal_selection_updated.connect(
            self.slot_update_linked_selection)
        controller.signal_pointer_discovered.connect(
            self.add_pointers_and_constraints)
        controller.signal_only_in_current_marked.connect(
            lambda x, y: self.mark_only_in_one(controller, x, y))

    def unregister_controller(self, controller: HexViewerController) -> None:
        if controller in self.linked_controllers:
            self.unlink(controller)
        self.controllers.remove(controller)

    def unlink_all(self) -> None:
        '''
        Unlinks all currently linked controllers
        '''
        for controller in self.linked_controllers:
            controller.set_linked(False)
            controller.set_address_resolver_and_diff_calculator(
                TrivialAddressResolver(),
                NoDiffCalculator()
            )
            controller.request_repaint()
        self.linked_controllers = []
        self.linked_variants = []
        self.update_constraint_manager()

    def link_multiple(self, linked_controllers: list[HexViewerController]) -> None:
        '''
        Links all passed controllers
        '''
        for controller in linked_controllers:
            if controller.rom_variant in self.linked_variants:
                # TODO error
                return
            self.linked_controllers.append(controller)
            self.linked_variants.append(controller.rom_variant)
            controller.set_linked(True)
            controller.set_address_resolver_and_diff_calculator(
                LinkedAddressResolver(
                    self.constraint_manager, controller.rom_variant),
                self.linked_diff_calculator
            )
        self.update_constraint_manager()

    def unlink(self, controller: HexViewerController) -> None:
        self.linked_controllers.remove(controller)
        self.linked_variants.remove(controller.rom_variant)
        controller.set_linked(False)
        controller.set_address_resolver_and_diff_calculator(
            TrivialAddressResolver(),
            NoDiffCalculator()
        )
        controller.request_repaint()
        self.update_constraint_manager()

    def link(self, controller: HexViewerController) -> None:
        if controller.rom_variant in self.linked_variants:
            # TODO error
            return
        self.linked_controllers.append(controller)
        self.linked_variants.append(controller.rom_variant)
        controller.set_linked(True)
        controller.set_address_resolver_and_diff_calculator(
            LinkedAddressResolver(self.constraint_manager,
                                  controller.rom_variant),
            self.linked_diff_calculator
        )
        self.update_constraint_manager()

    def slot_toggle_linked(self, controller: HexViewerController, linked: bool) -> None:
        if linked:
            if controller.rom_variant in self.linked_variants:
                controller.set_linked(False)
                QMessageBox.warning(controller.dock, 'Link Hex Editor',
                                    'Hex editor cannot be linked, because another hex editor for the same rom variant is already linked.')
                return
            self.link(controller)
        else:
            self.unlink(controller)

    def update_constraint_manager(self):
        self.linked_diff_calculator.set_variants(self.linked_variants)
        self.constraint_manager.set_variants(self.linked_variants)
        self.update_constraints()

    def update_constraints(self):
        print('update constraints')
        print(self.linked_variants)
        self.constraint_manager.reset()
        if len(self.linked_variants) > 1:
            print('Add constraints')
            self.constraint_manager.add_all_constraints(
                get_constraint_database().get_constraints())
        for controller in self.linked_controllers:
            controller.request_repaint()

    def slot_move_linked_start_offset(self, virtual_address: int) -> None:
        for controller in self.linked_controllers:
            controller.set_start_offset(virtual_address)

    def slot_move_linked_cursor(self, virtual_address: int) -> None:
        for controller in self.linked_controllers:
            controller.set_cursor(virtual_address)

    def slot_update_linked_selection(self, selected_bytes: int) -> None:
        for controller in self.linked_controllers:
            controller.set_selected_bytes(selected_bytes)
    """

    def get_hex_editor_instance(self, rom_variant: RomVariant, linked: bool)-> HexEditorInstance:
        if linked:
            instance = HexEditorInstance(self, rom_variant, get_rom(rom_variant), self.constraint_manager)
            instance.start_offset_moved.connect(self.move_all_start_offsets)
            instance.cursor_moved.connect(self.move_all_cursors)
            instance.selection_updated.connect(self.update_all_selections)
            instance.pointer_discovered.connect(self.add_pointers_and_constraints)
            instance.only_in_current_marked.connect(lambda x,y: self.mark_only_in_one(rom_variant, x, y))
            self.instances.append(instance)
        else:
            instance = SoloHexEditorInstance(self, rom_variant, get_rom(rom_variant))
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
                # does count as a difference
                return True
            local_data = get_rom(variant).get_byte(local_address)
            if data is None:
                data = local_data
                continue
            if data != local_data:
                return True
        return False
        """

    def add_pointers_and_constraints(self, pointer: Pointer) -> None:
        # Found a pointer that is the same for all variants

        new_pointers = [pointer]
        new_constraints = []
        virtual_address = self.constraint_manager.to_virtual(
            pointer.rom_variant, pointer.address)

        for variant in self.linked_variants:
            if variant != pointer.rom_variant:
                address = self.constraint_manager.to_local(
                    variant, virtual_address)
                points_to = get_rom(variant).get_pointer(address)
                # Add a corresponding pointer for this variant
                new_pointers.append(Pointer(
                    variant, address, points_to, pointer.certainty, pointer.author, pointer.note))

                # Add a constraint for the places that these two pointers are pointing to, as the pointers should be the same
                # TODO check that it's actually a pointer into rom

                note = f'Pointer at {pointer.rom_variant} {hex(pointer.address)}'
                if pointer.note.strip() != '':
                    note += '\n' + pointer.note

                # TODO test that adding the added constraints are not invalid

                enabled = self.constraint_manager.to_virtual(
                    pointer.rom_variant, pointer.points_to-ROM_OFFSET) != self.constraint_manager.to_virtual(variant, points_to-ROM_OFFSET)
                print(f'Add constraint {enabled}')
                new_constraints.append(Constraint(pointer.rom_variant, pointer.points_to-ROM_OFFSET,
                                       variant, points_to-ROM_OFFSET, pointer.certainty, pointer.author, note, enabled))

        pointer_database = get_pointer_database()
        pointer_database.add_pointers(new_pointers)
        constraint_database = get_constraint_database()
        constraint_database.add_constraints(new_constraints)

    def mark_only_in_one(self, controller: HexViewerController, virtual_address: int, length: int) -> None:

        rom_variant = controller.rom_variant

        # TODO show dialog for inputs
        certainty = 1
        author = settings.get_username()
        note = 'Only in ' + rom_variant
        enabled = True

        # Get the end of the section only in this variant + 1
        local_address = self.constraint_manager.to_local(
            rom_variant, virtual_address + length)

        new_constraints = []
        for variant in self.linked_variants:
            if variant != rom_variant:
                # Link it to the start of the selection in all other variants
                la = self.constraint_manager.to_local(variant, virtual_address)
                constraint = Constraint(
                    rom_variant, local_address, variant, la, certainty, author, note, enabled)
                new_constraints.append(constraint)

        constraint_database = get_constraint_database()
        constraint_database.add_constraints(new_constraints)

        print(f'mark only in one {rom_variant} {virtual_address} {length}')

    # def is_already_linked(self, rom_variant: RomVariant) -> bool:
    #     return rom_variant in self.variants

    # def link(self, rom_variant: RomVariant) -> None:
    #     self.variants.append(rom_variant)
    #     self.constraint_manager.set_variants(self.variants)
    #     self.update_constraints()

    # def unlink(self, rom_variant: RomVariant) -> None:
    #     self.variants.remove(rom_variant)
    #     self.constraint_manager.set_variants(self.variants)
    #     self.update_constraints()

    # def set_linked_variants(self, linked_variants: set[RomVariant]) -> None:
    #     self.variants = linked_variants
    #     self.constraint_manager.set_variants(linked_variants)
    #     self.update_constraints()
