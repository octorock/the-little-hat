from tlh.const import RomVariant
from dataclasses import dataclass

class Constraint:
    """
    A constraint defines that two local addresses of different rom variants should be at the same virtual address
    """
    romA: RomVariant = None
    addressA: int = 0
    romB: RomVariant = None
    addressB: int = 0
    certainty: int = 0
    note: str = None

class RomRelation:
    def __init__(self, local_address: int, virtual_address: int):
        self.local_address = local_address
        self.virtual_address = virtual_address

class RomRelations:
    """
    A rom relation defines the relation between a local address for this rom variant and the corresponding virtual address
    """
    def __init__(self, romVariant: RomVariant) -> None:
        self.romVariant = romVariant
        self.relations: list[RomRelation] = []
    
    def add_relation(self, local_address: int, virtual_address: int):
        # TODO keep relations list sorted
        self.relations.append(RomRelation(local_address, virtual_address))

    def clear(self):
        self.relations.clear()

    def get_previous_relation_for_local_address(self, local_address: int) -> RomRelation:
        prev = None

        # TODO use binary search
        for relation in self.relations:
            if relation.local_address > local_address:
                return prev
            prev = relation

        print('not found', local_address, prev, self.romVariant)
        return prev

    def get_prev_and_next_relation_for_virtual_address(self, virtual_address: int) -> (RomRelation, RomRelation):
        prev = None
        
        # TODO use binary search
        for relation in self.relations:
            if relation.virtual_address > virtual_address:
                print('PREV')
                return (prev, relation)
            prev = relation
        print('last', virtual_address)
        return (prev, None)

@dataclass
class Hint:
    local_address: int
    rom_variant: RomVariant
    rom_address: int

class ConstraintManager:
    def __init__(self, variants: set[RomVariant]) -> None:
        """
        Pass a set of all RomVariants that should be linked using this constraint manager
        """
        self.variants = variants
        self.constraints: list[Constraint] = []
        self.rom_relations: dict[str, RomRelations] = {}
        for variant in variants:
            self.rom_relations[variant] = RomRelations(variant)
            


    def add_constraint(self, constraint: Constraint) -> None:
        self.constraints.append(constraint) # TODO add at the correct place
        self.rebuild_relations()

    def rebuild_relations(self) -> None:
        """
        Builds relations between local addresses for each variation and the virtual address based on the constraints
        """
        virtual_address = 0
        local_addresses: dict[str, int] = {}
        local_hints: dict[str, Hint] = {}
        for variant in self.variants:
            local_addresses[variant] = 0
            local_hints[variant] = []
            self.rom_relations[variant].clear()


        constraints = self.constraints.copy()

        while constraints: # not empty

            # get constraint with the lowest virtual address
            # TODO is there a way to keep the list sorted by these virtual addresses which are constantly changing with each new constraint?
            selected_constraint = constraints[0]
            selected_variant = constraints[0].romA
            selected_local_address = constraints[0].addressA
            selected_virtual_address = self.to_virtual(selected_variant, selected_local_address)

            for constraint in constraints:
                # handle A
                variant_a = constraint.romA
                local_address_a = constraint.addressA
                virtual_address_a = self.to_virtual(variant_a, local_address_a)
                if virtual_address_a < selected_virtual_address:
                    selected_constraint = constraint
                    selected_variant = variant_a
                    selected_local_address = local_address_a
                    selected_virtual_address = virtual_address_a
                # handle B
                variant_b = constraint.romB
                local_address_b = constraint.addressB
                virtual_address_b = self.to_virtual(variant_b, local_address_b)
                if virtual_address_b < selected_virtual_address:
                    selected_constraint = constraint
                    selected_variant = variant_b
                    selected_local_address = local_address_b
                    selected_virtual_address = virtual_address_b

            # Remove constraint
            constraints.remove(selected_constraint)

            virtual_address_offset = selected_virtual_address - virtual_address
            # Advance all local addresses to this virtual address
            for variant in self.variants:
                local_address = local_addresses[variant] + virtual_address_offset
                local_addresses[variant] = local_address
                # TODO handle hints

            # for the lower address of the constraint, add a relation to the current virtual address
            virtual_address_a = self.to_virtual(selected_variant, selected_constraint.addressA)
            virtual_address_b = self.to_virtual(selected_variant, selected_constraint.addressB)
            if virtual_address_a < virtual_address_b:
                self.rom_relations[selected_constraint.romA].add_relation(selected_constraint.addressA, virtual_address_b)
            else:
                self.rom_relations[selected_constraint.romB].add_relation(selected_constraint.addressB, virtual_address_a)
            # TODO addresses are the same -> insert both constraints here

        # while constraints exist
            # get constraints that has the lowest virtual address
            # advance all local addresses to this virtual address
            # TODO if there are hints left until there, handle them
            # for the lower address of the constraint, add a relation to the current virtual address
            # add a hint for the higher address to be inserted later


        # for constraint in self.constraints:
        #     # Add relation to rom variant with the lower address
        #     # TODO check the difference of the virtual constraints!
        #     if constraint.addressA < constraint.addressB:
        #         print('a')
        #         virtual_address = constraint.addressB
        #         self.rom_relations[constraint.romA].add_relation(constraint.addressA, virtual_address)
        #     else:
        #         print('b')
        #         virtual_address = constraint.addressA
        #         self.rom_relations[constraint.romB].add_relation(constraint.addressB, virtual_address)
        #     # TODO continue until we are at the other constraint

    def to_local(self, rom: RomVariant, virtual_address: int) -> int:
        """
        Convert from a virtual address to a local address for a certain rom variant
        """
        if not rom in self.variants:
            raise RomVariantNotAddedError()

        (prev, next) = self.rom_relations[rom].get_prev_and_next_relation_for_virtual_address(virtual_address)
        if prev is None:
            if next is not None:
                if virtual_address >= next.local_address:
                    # No local address at this virtual address
                    return -1
            return virtual_address
        else:
            # Calculate offset to virtual_address
            offset = virtual_address - prev.virtual_address
            local_address = prev.local_address + offset
            print(prev.virtual_address)
            if next is not None:
                if local_address > next.local_address:
                    # No local address at this virtual address
                    return -1
                elif local_address == next.local_address:
                    # This should not happen, if it's equal, the relation should be the prev relation
                    # TODO maybe this can happen, because only the virtual address needs to be prev?
                    assert False
            return local_address

    def to_virtual(self, rom: RomVariant, local_address: int) -> int:
        """
        Convert from a local address for a certain rom variant to a virtual address
        """
        if not rom in self.variants:
            raise RomVariantNotAddedError()

        relation = self.rom_relations[rom].get_previous_relation_for_local_address(local_address)
        if relation is None:
            print('passing')
            return local_address
        else:
            # Calculate offset to local_address
            offset = local_address - relation.local_address
            print('got offset', offset, relation.virtual_address)
            return relation.virtual_address + offset


class RomVariantNotAddedError(Exception):
    pass

# TODO pass the other constraint(s) it is invalid against?
class InvalidConstraintError(Exception):
    pass