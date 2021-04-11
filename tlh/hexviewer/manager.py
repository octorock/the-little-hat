from dataclasses import dataclass
from typing import Optional
from PySide6.QtCore import QObject
from PySide6.QtWidgets import QMessageBox
from tlh import settings
from tlh.const import ROM_OFFSET, RomVariant
from tlh.data.constraints import Constraint, ConstraintManager
from tlh.data.database import get_constraint_database, get_pointer_database
from tlh.data.pointer import Pointer
from tlh.data.rom import get_rom
from tlh.hexviewer.address_resolver import (LinkedAddressResolver,
                                            TrivialAddressResolver)
from tlh.hexviewer.controller import HexViewerController
from tlh.hexviewer.diff_calculator import (LinkedDiffCalculator,
                                           NoDiffCalculator)

@dataclass
class LocalAddress:
    rom_variant: RomVariant
    local_address: int


class HexViewerManager(QObject):
    """
    Manages all hex viewers
    """

    def __init__(self, parent) -> None:
        super().__init__(parent=parent)
        self.controllers: list[HexViewerController] = []
        self.linked_controllers: list[HexViewerController] = []
        self.linked_variants: list[RomVariant] = []

        self.constraint_manager = ConstraintManager({})
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
        unlinked_local_address = controller.get_local_address(controller.cursor)
        self.linked_controllers.remove(controller)
        self.linked_variants.remove(controller.rom_variant)

        local_address = self.collect_local_address()

        controller.set_address_resolver_and_diff_calculator(
            TrivialAddressResolver(),
            NoDiffCalculator()
        )
        controller.set_linked(False)
        controller.request_repaint()
        self.update_constraint_manager()
        controller.setup_scroll_bar()

        if local_address is not None:
            # Apply local address
            self.apply_local_address(local_address)

        # Apply local address for now unlinked controller (virtual address is now equal to local address)
        controller.set_cursor(unlinked_local_address)


    def link(self, controller: HexViewerController) -> None:
        if controller.rom_variant in self.linked_variants:
            # TODO error
            return
        
        local_address = self.collect_local_address()

        self.linked_controllers.append(controller)
        self.linked_variants.append(controller.rom_variant)
        controller.set_linked(True)
        controller.set_address_resolver_and_diff_calculator(
            LinkedAddressResolver(self.constraint_manager,
                                  controller.rom_variant),
            self.linked_diff_calculator
        )
        self.update_constraint_manager()

        if local_address is not None:
            # Apply local address
            self.apply_local_address(local_address)

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
            controller.setup_scroll_bar()

    def slot_move_linked_start_offset(self, virtual_address: int) -> None:
        for controller in self.linked_controllers:
            controller.set_start_offset(virtual_address)

    def slot_move_linked_cursor(self, virtual_address: int) -> None:
        for controller in self.linked_controllers:
            controller.set_cursor(virtual_address)

    def slot_update_linked_selection(self, selected_bytes: int) -> None:
        for controller in self.linked_controllers:
            controller.set_selected_bytes(selected_bytes)

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


    def collect_local_address(self) -> Optional[LocalAddress]:
        '''
        Returns the local address of the linked controllers
        '''
        if len(self.linked_controllers) < 1:
            return None
        # TODO don't choose the controller that is currently being unlinked

        # Simply return the local address for the first linked controller
        # This should have the same virtual address as the other linked controller now,
        # but after linking/unlinking those might differ.
        # User experience might be improved by choosing the last focussed controller instead.
        controller = self.linked_controllers[0]
        # Maybe using the start offset instead of the cursor gives a better experience as the
        # user might have scrolled away from the cursor. Maybe even set both?
        return LocalAddress(controller.rom_variant, controller.get_local_address(controller.cursor))

    def apply_local_address(self, local_address: LocalAddress) -> None:
        virtual_address = self.constraint_manager.to_virtual(local_address.rom_variant, local_address.local_address)
        for controller in self.linked_controllers:
            controller.update_cursor(virtual_address)