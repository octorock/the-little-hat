from typing import Dict, List, Set, Tuple
from tlh.const import RomVariant
from dataclasses import dataclass
from sortedcontainers import SortedKeyList
from bisect import bisect_left, bisect_right
from intervaltree import Interval, IntervalTree

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
    author: str = ''
    note: str = ''
    enabled: bool = True


@dataclass
class RomRelation:
    local_address: int
    virtual_address: int


def log(*argv):
    # print(*argv)
    pass


class RomRelations:
    """
    A rom relation defines the relation between a local address for this rom variant and the corresponding virtual address
    """

    def __init__(self, romVariant: RomVariant) -> None:
        self.romVariant = romVariant

        # We basically want a SortedKeyList. However there are two different keys we need to access using bisect, local_address and virtual_address.
        # So instead we need to store sorted key lists for local and virtual addresses as well, see https://stackoverflow.com/a/27673073.
        self.relations: List[RomRelation] = []
        self.keys_local: List[int] = []
        self.keys_virtual: List[int] = []

    def add_relation(self, local_address: int, virtual_address: int):
        if local_address > virtual_address:
            log(f'{self.romVariant} l{local_address} v{virtual_address}')
            assert False

        log(f'-> Add relation {self.romVariant} l{local_address} v{virtual_address}')

        # keep relations list (and both keys lists) sorted
        index = bisect_left(self.keys_local, local_address)
        self.keys_local.insert(index, local_address)
        self.keys_virtual.insert(index, virtual_address)
        self.relations.insert(index, RomRelation(local_address, virtual_address))

    def clear(self):
        self.relations.clear()
        self.keys_local.clear()
        self.keys_virtual.clear()

    def get_previous_relation_for_local_address(self, local_address: int) -> RomRelation:
        index = bisect_right(self.keys_local, local_address) - 1
        if index >= 0 and index < len(self.relations):
            return self.relations[index]
        return None

    def get_prev_and_next_relation_for_virtual_address(self, virtual_address: int) -> Tuple[RomRelation, RomRelation]:
        index = bisect_right(self.keys_virtual, virtual_address) - 1

        prev = None
        next = None
        if index >= 0 and index < len(self.relations):
            prev = self.relations[index]

        if index + 1 < len(self.relations):
            next = self.relations[index+1]

        return (prev, next)


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


class NoConstraintManager:
    """
    Class that replaces the ConstraintManager when no constraints are loaded.
    virtual and local addresses now are the same
    """

    def set_variants(self, variants: Set[RomVariant]) -> None:
        pass

    def reset(self):
        pass

    def add_constraint(self, constraint: Constraint) -> None:
        pass

    def add_all_constraints(self, constraints: List[Constraint]) -> None:
        pass

    def rebuild_relations(self) -> None:
        pass

    def to_local(self, variant: RomVariant, virtual_address: int) -> int:
        return virtual_address

    def to_virtual(self, variant: RomVariant, local_address: int) -> int:
        return local_address

    def print_relations(self) -> None:
        pass


class ConstraintManager:
    def __init__(self, variants: Set[RomVariant]) -> None:
        """
        Pass a set of all RomVariants that should be linked using this constraint manager
        """
        self.variants = variants
        self.constraints: List[Constraint] = []
        self.rom_relations: Dict[RomVariant, RomRelations] = {}
        for variant in variants:
            self.rom_relations[variant] = RomRelations(variant)

    def set_variants(self, variants: Set[RomVariant]) -> None:
        self.variants = variants
        self.rom_relations = {}
        for variant in variants:
            self.rom_relations[variant] = RomRelations(variant)

    def reset(self):
        self.constraints = []
        for variant in self.variants:
            self.rom_relations[variant].clear()

    def add_constraint(self, constraint: Constraint) -> None:
        if constraint.enabled:
            # TODO add at the correct place
            self.constraints.append(constraint)
        # TODO add #self.rebuild_relations()

    def add_all_constraints(self, constraints: List[Constraint]) -> None:
        for constraint in constraints:

            if constraint.romA in self.variants and constraint.romB in self.variants:
                self.add_constraint(constraint)
            # TODO handle transitive constraints here?
        print(f'Added {len(self.constraints)} of {len(constraints)}')
        self.rebuild_relations()

        # print('Num of relations')
        # for variant in self.variants:
        #     print(variant, len(self.rom_relations[variant].relations))

    def rebuild_relations(self) -> None:
        """
        Builds relations between local addresses for each variation and the virtual address based on the constraints
        """

        local_addresses: Dict[str, int] = {}
        local_blockers: Dict[str, List[Blocker]] = {}
        local_blockers_count = 0
        for variant in self.variants:
            self.rom_relations[variant].clear()
            local_addresses[variant] = -1
            local_blockers[variant] = []

        constraints = self.constraints.copy()

        virtual_address = -1
        # TODO at that point all roms should have been resolved
        for tmp_counter in range(0, 0x0fffffff):

            log('')

            # Stop the loop if all constraints and blockers are resolved
            if not constraints and local_blockers_count == 0:
                break

            # Optimization? Jump to the next interesting virtual address
            # - next blocker with blocker.rom_variant:blocker.rom_address
            # - next constraint with romA:addressA or romB:addressB
            next_virtual_address = 0xffffffff
            # Store the blocker/constraint that was responsible for this va to be selected TODO only for debugging, remove later
            responsible_object = None

            def to_virtual_based_on_current_local(variant, address):
                # Don't return a virtual address before the local_address of anything
                # that is blocking this
                # TODO more correct would be to test against the virtual address of the thing
                # blocking us and then only advance to that position instead of simply returning
                # 0xfffffff, but that would lead to loops of calculation if both variants are
                # blocked.
                # if len(local_blockers[variant]) > 0:
                # return 0xfffffff
                for blocker in local_blockers[variant]:
                    if blocker.rom_address > address:
                        return 0xfffffff

                return virtual_address + address - local_addresses[variant]

            for variant in self.variants:
                for blocker in local_blockers[variant]:
                    va = to_virtual_based_on_current_local(
                        blocker.rom_variant, blocker.rom_address)
                    if va < next_virtual_address:
                        next_virtual_address = va
                        responsible_object = blocker
                    # Also test the address that we are blocking

            for constraint in constraints:
                va_a = to_virtual_based_on_current_local(
                    constraint.romA, constraint.addressA)
                va_b = to_virtual_based_on_current_local(
                    constraint.romB, constraint.addressB)

                # as both have the same virtual addresses after this constraint, we need to take the maximum
                va = min(va_a, va_b)
                if va < next_virtual_address:
                    next_virtual_address = va
                    responsible_object = constraint

            offset = next_virtual_address - virtual_address

            if offset == 0:
                # This is okay now and will happen if a possibly_done_constraint is blocked after adding the other constraints
                # Might still lead to endless loops in the future D:
                pass
            elif offset < 0:  # TODO why is this necessary? should the corresponding constraint/blocker not have been removed in the previous iteration?
                log(f'Negative offset: {next_virtual_address} - {virtual_address}')
                log(responsible_object)
                log(local_addresses)
                log(local_blockers)

                # TODO this is still triggered in test_four_roms due to the va calculation for EU not being aware that it is blocked
                # TODO now also happending in test_bug_2, making it very slow
                assert False
                #offset = 1
            virtual_address += offset

            log(f'-- Go to {virtual_address} (+{offset})')
            log(f'Due to {responsible_object}')

            # Advance all local_addresses where there is no blocker
            next_local_addresses = {}
            can_advance = {}
            for variant in self.variants:
                next_local_addresses[variant] = local_addresses[variant] + offset
                log(
                    f'{variant} wants to {local_addresses[variant]} -> {next_local_addresses[variant]}')
                can_advance[variant] = True

            # TODO do a semi-shallow copy?
            local_blockers_copy = {}
            for variant in self.variants:
                local_blockers_copy[variant] = local_blockers[variant].copy()

            # We cannot fully be sure that a blocker is resolved as a constraint might be added afterwards that stops the resolution of this blocker
            possibly_resolved_blockers: Dict[RomVariant, List[Blocker]] = {}
            for variant in self.variants:
                possibly_resolved_blockers[variant] = []

            for variant in self.variants:

                still_blocking = False
                # https://stackoverflow.com/a/10665800
                for blocker in local_blockers[variant]:
                    log(f'Blocker {blocker}')
                    if next_local_addresses[variant] >= blocker.local_address:
                        if next_local_addresses[blocker.rom_variant] < blocker.rom_address:
                            log(f'{variant} is still blocked by {blocker}')
                            can_advance[variant] = False

                            # Needed to add the following line for test_bug_4_simplified
                            next_local_addresses[variant] = local_addresses[variant]

                        # TODO After the introduction of the return in to_virtual_based_on_current_local
                        # this no longer produces invalid constraints, instead this can happen when multiple
                        # blockers need to be resolved at the same address and the order of the variants
                        # does not align with the inverse order of the local addresses
                        # Maybe invalid constraints that were previously found by this are now only found by
                        # the checking of all constraints at the end?
                        # elif next_local_addresses[blocker.rom_variant] < blocker.rom_address:
                            #log(f'{blocker} {variant} creates invalid constraint: {next_local_addresses[blocker.rom_variant]} > {blocker.rom_address}:')
                            #raise InvalidConstraintError()
                        else:
                            log(f'Possibly resolve {blocker}')
                            next_local_addresses[variant] = blocker.local_address
                            possibly_resolved_blockers[variant].append(blocker)
                            # local_blockers_copy[variant].remove(blocker)
                            #local_blockers_count -= 1
                    else:
                        # Cannot be blocked, but reverse another blocker that would be resolved here
                        if next_local_addresses[blocker.rom_variant] > blocker.rom_address:
                            # TODO does this ever happen?
                            assert False
                        elif next_local_addresses[blocker.rom_variant] == blocker.rom_address:
                            local_blockers_copy[variant].remove(blocker)
                            new_blocker = Blocker(
                                blocker.rom_address, variant, blocker.local_address)
                            local_blockers_copy[blocker.rom_variant].append(
                                new_blocker)

                            # TODO does this not create one virtual address that is unused?
                            next_local_addresses[blocker.rom_variant] = blocker.rom_address - 1
                            log(
                                f'Would resolve {blocker}, but local not advanced enough, add opposing blocker {new_blocker}')

            local_blockers = local_blockers_copy

            possibly_done_constraints = []
            # Handle all constraints TODO sort them somehow
            # https://stackoverflow.com/a/10665800
            for constraint in reversed(constraints):
                virtual_address_a = virtual_address + constraint.addressA - \
                    next_local_addresses[
                        constraint.romA]  # self.to_virtual(constraint.romA, constraint.addressA)
                virtual_address_b = virtual_address + constraint.addressB - \
                    next_local_addresses[
                        constraint.romB]  # self.to_virtual(constraint.romB, constraint.addressB)

                if virtual_address_a == virtual_address_b == virtual_address:
                    possibly_done_constraints.append(constraint)
                    log(f'Possibly already done {constraint}')
                elif virtual_address_a == virtual_address:
                    constraints.remove(constraint)
                    log(f'Handle A {constraint}')

                    # log(f'{constraint.addressA} > {local_addresses[constraint.romA]}')
                    # if constraint.addressA > local_addresses[constraint.romA]:
                    #     raise InvalidConstraintError()
                    # elif constraint.addressA == local_addresses[constraint.romA] and constraint.addressB != local_addresses[constraint.romB]:
                    #     raise InvalidConstraintError()

                    blocker = Blocker(constraint.addressA,
                                      constraint.romB, constraint.addressB)
                    log(f'add blocker {blocker}')
                    local_blockers[constraint.romA].append(blocker)
                    local_blockers_count += 1
                    # reduce advancement
                    next_local_addresses[constraint.romA] = constraint.addressA-1

                elif virtual_address_b == virtual_address:
                    constraints.remove(constraint)
                    log(f'Handle B {constraint}')

                    # if constraint.addressB > local_addresses[constraint.romB]:
                    #     raise InvalidConstraintError()
                    # elif constraint.addressB == local_addresses[constraint.romB] and constraint.addressA != local_addresses[constraint.romA]:
                    #     raise InvalidConstraintError()

                    blocker = Blocker(constraint.addressB,
                                      constraint.romA, constraint.addressA)
                    log(f'add blocker {blocker}')
                    local_blockers[constraint.romB].append(blocker)
                    local_blockers_count += 1
                    # reduce advancement
                    next_local_addresses[constraint.romB] = constraint.addressB-1

            for constraint in possibly_done_constraints:
                if next_local_addresses[constraint.romA] < constraint.addressA or next_local_addresses[constraint.romB] < constraint.addressB:
                    log(f'Do not yet handle {constraint}')
                    continue
                constraints.remove(constraint)
                log(f'Handle done {constraint}')
                continue
                # TODO don't need to insert a relation, because it's already correct?
                log(virtual_address_a, virtual_address_b)

            # Resolve possibly resolved blockers
            for variant in self.variants:
                for blocker in possibly_resolved_blockers[variant]:
                    if next_local_addresses[variant] < blocker.local_address or not can_advance[variant] or next_local_addresses[blocker.rom_variant] < blocker.rom_address or not can_advance[blocker.rom_variant]:
                        # An added constraint prevents us from advancing
                        log(f'Don\'t resolve {blocker}')
                        can_advance[variant] = False

            # We need to do this in two loops as the previous setting of can_advance to false might be a new blocker
            for variant in self.variants:
                for blocker in possibly_resolved_blockers[variant]:
                    if next_local_addresses[variant] < blocker.local_address or not can_advance[variant] or next_local_addresses[blocker.rom_variant] < blocker.rom_address or not can_advance[blocker.rom_variant]:
                        pass
                    else:
                        log(f'Resolve {blocker}')
                        # Insert corresponding relation
                        self.rom_relations[variant].add_relation(
                            blocker.local_address, virtual_address)
                        local_blockers[variant].remove(blocker)
                        local_blockers_count -= 1
                        # reduce advancement
                        next_local_addresses[variant] = blocker.local_address

            can_continue = False
            for variant in self.variants:

                if can_advance[variant]:
                    log(
                        f'{variant} advances to {next_local_addresses[variant]}')
                    local_addresses[variant] = next_local_addresses[variant]
                    can_continue = True
                else:
                    log(f'{variant} stays at {local_addresses[variant]}')
                    # TODO check that this is correct
                    next_local_addresses[variant] = local_addresses[variant]

            if not can_continue:
                # every variation is blocked, invalid constraints
                raise InvalidConstraintError()

        log('Algorithm finished\n')

        # Check all constraints again
        # TODO remove this once we always find all invalid constraints before
        # currently not detected: two differing constraints for the same address (test_conflicting_constraint)
        for constraint in self.constraints:
            if self.to_virtual(constraint.romA, constraint.addressA) != self.to_virtual(constraint.romB, constraint.addressB):
                log(f'{constraint} not fulfilled')
                log(f'{self.to_virtual(constraint.romA, constraint.addressA)} != {self.to_virtual(constraint.romB, constraint.addressB)}')
                self.print_relations()
                # assert False
                raise InvalidConstraintError()
            # assert self.to_virtual(constraint.romA, constraint.addressA) == self.to_virtual(constraint.romB, constraint.addressB)

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

    def to_local(self, variant: RomVariant, virtual_address: int) -> int:
        """
        Convert from a virtual address to a local address for a certain rom variant
        """
        if not variant in self.variants:
            raise RomVariantNotAddedError()

        (prev, next) = self.rom_relations[variant].get_prev_and_next_relation_for_virtual_address(
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

    def to_virtual(self, variant: RomVariant, local_address: int) -> int:
        """
        Convert from a local address for a certain rom variant to a virtual address
        """
        if not variant in self.variants:
            raise RomVariantNotAddedError()

        relation = self.rom_relations[variant].get_previous_relation_for_local_address(
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


"""
New idea:

insert constraints one at a time as they come in and only move all existing relations accordingly

- calculate the current virtual addresses for both sides of the constraint
- take the lesser one and at a relation to place it at the higher one
TODO what other relations need to be affected?
 - later virtual addresses for the lesser side
 - everything that references the virtual addresses from the lesser side
  -> too complicated to detect all without keeping all constraints around?

"""



@dataclass
class RomConstraint:
    addr: int
    constraint: Constraint

class ConstraintList:
    '''
    List of constraints for a single rom variant
    '''
    def __init__(self, constraints: List[Constraint], rom_variant: RomVariant) -> None:

        self.constraints = SortedKeyList(key=lambda x:x.addr)

        for constraint in constraints:

            if constraint.romA == rom_variant:
                self.constraints.add(RomConstraint(constraint.addressA, constraint))
            elif constraint.romB == rom_variant:
                self.constraints.add(RomConstraint(constraint.addressB, constraint))

    def get_constraints_at(self, local_address: int) -> List[Constraint]:
        constraints = []
        index = self.constraints.bisect_key_left(local_address)

        while index < len(self.constraints) and self.constraints[index].addr == local_address:
            constraints.append(self.constraints[index].constraint)
            index += 1
        return constraints