from tlh.const import RomVariant
from dataclasses import dataclass


@dataclass
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


@dataclass
class RomRelation:
    local_address: int
    virtual_address: int


class RomRelations:
    """
    A rom relation defines the relation between a local address for this rom variant and the corresponding virtual address
    """

    def __init__(self, romVariant: RomVariant) -> None:
        self.romVariant = romVariant
        self.relations: list[RomRelation] = []

    def add_relation(self, local_address: int, virtual_address: int):
        if local_address > virtual_address:
            print(f'{self.romVariant} l{local_address} v{virtual_address}')
            assert False
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

        return prev

    def get_prev_and_next_relation_for_virtual_address(self, virtual_address: int) -> tuple[RomRelation, RomRelation]:
        prev = None

        # TODO use binary search
        for relation in self.relations:
            if relation.virtual_address > virtual_address:
                return (prev, relation)
            prev = relation
        return (prev, None)

    def print_relations(self):
        for relation in self.relations:
            print(f'l{relation.local_address} v{relation.virtual_address}')

@dataclass(frozen=True, eq=True)
class Blocker:
    """
    Blocks the progression of this rom until another rom has reached a local variant
    """
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
        self.rom_relations: dict[RomVariant, RomRelations] = {}
        for variant in variants:
            self.rom_relations[variant] = RomRelations(variant)

    def add_constraint(self, constraint: Constraint) -> None:
        self.constraints.append(constraint)  # TODO add at the correct place
        #TODO add #self.rebuild_relations()

    def rebuild_relations(self) -> None:
        """
        Builds relations between local addresses for each variation and the virtual address based on the constraints
        """
        virtual_address = 0
        local_addresses: dict[str, int] = {}
        local_blockers: dict[str, list[Blocker]] = {}
        local_blockers_count = 0
        for variant in self.variants:
            local_addresses[variant] = 0
            local_blockers[variant] = []
            self.rom_relations[variant].clear()

        constraints = self.constraints.copy()

        while constraints:  # not empty

            # get constraint with the lowest virtual address
            # TODO is there a way to keep the list sorted by these virtual addresses which are constantly changing with each new constraint?
            selected_constraint = constraints[0]
            selected_variant = constraints[0].romA
            selected_local_address = constraints[0].addressA
            selected_virtual_address = self.to_virtual(
                selected_variant, selected_local_address)

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

            print(f'\nNext constraint: {selected_constraint}')
            # Handle everything before this virtual address
            selected_virtual_address -= 1
            print(f'Handle everything up to {selected_virtual_address}')

            # Remove constraint
            constraints.remove(selected_constraint)

            virtual_address_offset = selected_virtual_address - virtual_address

            # Advance all local addresses to th virtual address before this
            next_local_addresses = {}
            for variant in self.variants:
                next_local_addresses[variant] = local_addresses[variant] + virtual_address_offset

            print(f'v{selected_virtual_address}')
            for variant in self.variants:

                still_blocking = False
                for blocker in local_blockers[variant]:
                    if next_local_addresses[blocker.rom_variant] < blocker.rom_address:
                        print(f'{variant} is still blocked by {blocker}')
                        still_blocking = True
                        break
                    else:
                        local_blockers[variant].remove(blocker)
                        local_blockers_count -= 1
                        # Insert relation here
                        blocked_bytes = next_local_addresses[variant] - blocker.local_address - 1
                        self.rom_relations[variant].add_relation(blocker.local_address, self.to_virtual(blocker.rom_variant, blocker.rom_address))
                        next_local_addresses[variant] -= blocked_bytes # TODO what to actually substract here?
            
                if still_blocking:
                    # This variant can not advance yet
                    continue
                    
                local_addresses[variant] = next_local_addresses[variant]
                print(f'{variant} {next_local_addresses[variant]}')

            # for the lower address of the constraint, add a relation to the current virtual address
            virtual_address_a = self.to_virtual(
                selected_variant, selected_constraint.addressA)
            virtual_address_b = self.to_virtual(
                selected_variant, selected_constraint.addressB)
            if virtual_address_a < virtual_address_b:
                local_blockers[selected_constraint.romA].append(Blocker(
                    selected_constraint.addressA, selected_constraint.romB, selected_constraint.addressB))
            else:
                local_blockers[selected_constraint.romB].append(Blocker(
                    selected_constraint.addressB, selected_constraint.romA, selected_constraint.addressA))
            local_blockers_count += 1
            # TODO addresses are the same -> insert both constraints here

            virtual_address = selected_virtual_address

        print('done with constraints')





        while local_blockers_count > 0:
            # Select nearest local blocker
            selected_local_blocker = None
            selected_virtual_address = 0xffffffff
            selected_variant = None

            for variant in self.variants:
                for blocker in local_blockers[variant]:
                    # TODO only need to look at first one, if the list stays ordered?
                    virtual_address_x = self.to_virtual(blocker.rom_variant, blocker.rom_address)
                    if virtual_address_x < selected_virtual_address:
                        selected_local_blocker = blocker
                        selected_virtual_address = virtual_address_x
                        selected_variant = variant
            assert selected_local_blocker != None

            local_blockers[selected_variant].remove(selected_local_blocker)
            local_blockers_count -= 1

            print(f'Resolve l {selected_local_blocker}')

            virtual_address_offset = selected_local_blocker.rom_address - local_addresses[selected_local_blocker.rom_variant]

            virtual_address = virtual_address + virtual_address_offset
            self.rom_relations[selected_variant].add_relation(selected_local_blocker.local_address, self.to_virtual(selected_local_blocker.rom_variant, selected_local_blocker.rom_address))
            # advance all local addresses
            next_local_addresses = {}
            for variant in self.variants:
                next_local_addresses[variant] = local_addresses[variant] + virtual_address_offset


            print(f'v{selected_virtual_address}')
            for variant in self.variants:

                still_blocking = False
                for blocker in local_blockers[variant]:
                    if next_local_addresses[blocker.rom_variant] < blocker.rom_address:
                        print(f'{variant} is still blocked by {blocker}')
                        still_blocking = True
                        break
                    else:
                        local_blockers[variant].remove(blocker)
                        local_blockers_count -= 1
                        # Insert relation here
                        offset = next_local_addresses[blocker.rom_variant] - blocker.rom_address
                        self.rom_relations[variant].add_relation(blocker.local_address, selected_virtual_address - offset)
            
                if still_blocking:
                    # This variant can not advance yet
                    continue

                local_addresses[variant] = next_local_addresses[variant]
                print(f'{variant} {next_local_addresses[variant]}')

            # TODO handle blockers

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

        (prev, next) = self.rom_relations[rom].get_prev_and_next_relation_for_virtual_address(
            virtual_address)
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
            if next is not None:
                if local_address >= next.local_address:
                    # No local address at this virtual address
                    return -1
            return local_address

    def to_virtual(self, rom: RomVariant, local_address: int) -> int:
        """
        Convert from a local address for a certain rom variant to a virtual address
        """
        if not rom in self.variants:
            raise RomVariantNotAddedError()

        relation = self.rom_relations[rom].get_previous_relation_for_local_address(
            local_address)
        if relation is None:
            virtual_address = local_address
        else:
            # Calculate offset to local_address
            offset = local_address - relation.local_address
            virtual_address = relation.virtual_address + offset

        #print(f'{virtual_address} >= {local_address} {rom}')
        assert virtual_address >= local_address
        return virtual_address


    def print_relations(self) -> None:
        for variant in self.variants:
            print(f'--- {variant} ---')
            self.rom_relations[variant].print_relations()

class RomVariantNotAddedError(Exception):
    pass


class InvalidConstraintError(Exception):
    # TODO pass the other constraint(s) it is invalid against?
    pass
