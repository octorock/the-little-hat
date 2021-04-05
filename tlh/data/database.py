from csv import DictReader, DictWriter
from os import path

from PySide6.QtCore import QObject, Signal
from tlh.data.pointer import Pointer

from tlh.const import RomVariant
from tlh.data.constraints import Constraint, ConstraintManager


def get_file_in_database(filename: str) -> str:
    # TODO settings.get_database_location()
    return path.join('data', filename)


def initialize_databases(parent) -> None:
    '''
    Initialize all database singletons
    '''
    global pointer_database_instance, constraint_database_instance
    pointer_database_instance = PointerDatabase(parent)
    constraint_database_instance = ConstraintDatabase(parent)

### Constraints ###
constraint_database_instance = None
class ConstraintDatabase(QObject):

    constraints_changed = Signal()

    def __init__(self, parent) -> None:
        if constraint_database_instance is not None:
            raise RuntimeError('Already initialized')
        super().__init__(parent=parent)
        self.constraints = self._read_constraints()

    def get_constraints(self) -> list[Constraint]:
        return self.constraints

    def add_constraint(self, constraint: Constraint) -> None:
        self.constraints.append(constraint)
        # TODO don't save every time?
        self._write_constraints()
        self.constraints_changed.emit()

    def add_constraints(self, constraints: list[Constraint]) -> None:
        self.constraints += constraints
        # TODO don't save every time?
        self._write_constraints()
        self.constraints_changed.emit()

    def _read_constraints(self) -> list[Constraint]:
        constraints = []
        try:
            with open(get_file_in_database('constraints.csv'), 'r') as file:
                reader = DictReader(file)
                for row in reader:
                    constraints.append(
                        Constraint(
                            RomVariant(row['romA']),
                            int(row['addressA'], 16),
                            RomVariant(row['romB']),
                            int(row['addressB'], 16),
                            row['certainty'],
                            row['author'],
                            row['note'],
                            row['enabled'] == 'True'
                        )
                    )
        except OSError:
            # file cannot be read, just supply no constraints
            pass
        return constraints


    def _write_constraints(self):
        with open(get_file_in_database('constraints.csv'), 'w') as file:
            writer = DictWriter(
                file, fieldnames=['romA', 'addressA', 'romB', 'addressB', 'certainty', 'author', 'note', 'enabled'])
            writer.writeheader()
            for constraint in self.constraints:
                writer.writerow({
                    'romA': constraint.romA,
                    'addressA': hex(constraint.addressA),
                    'romB': constraint.romB,
                    'addressB': hex(constraint.addressB),
                    'certainty': constraint.certainty,
                    'author': constraint.author,
                    'note': constraint.note,
                    'enabled': constraint.enabled
                })

    def disable_redundant_constraints(self):
        '''
        Disables all constraints that only contain redundant information and don't create more relations
        '''

        # Test using a constraint manager with all variations
        manager = ConstraintManager({RomVariant.USA, RomVariant.JP, RomVariant.EU, RomVariant.DEMO})
        for constraint in self.constraints:
            if not constraint.enabled:
                continue

            # test if constraint is redundant
            va_a = manager.to_virtual(constraint.romA, constraint.addressA)
            va_b = manager.to_virtual(constraint.romB, constraint.addressB)
            if va_a == va_b:
                print(f'Disable {constraint}')
                constraint.enabled = False
            else:
                print(f'Keep {constraint}')
                manager.add_constraint(constraint)
                manager.rebuild_relations()
        self._write_constraints()


def get_constraint_database():
    return constraint_database_instance

### Pointers ###
pointer_database_instance = None
class PointerDatabase(QObject):

    pointers_changed = Signal()

    def __init__(self, parent) -> None:
        if pointer_database_instance is not None:
            raise RuntimeError('Already initialized')
        super().__init__(parent=parent)
        self.pointers = self._read_pointers()

    def get_pointers(self) -> list[Pointer]:
        return self.pointers

    def add_pointer(self, pointer: Pointer) -> None:
        self.pointers.append(pointer)
        # TODO don't save every time?
        self._write_pointers()
        self.pointers_changed.emit()

    def add_pointers(self, pointers: list[Pointer]) -> None:
        self.pointers += pointers
        # TODO don't save every time?
        self._write_pointers()
        self.pointers_changed.emit()


    def _read_pointers(self) -> list[Pointer]:
        pointers = []
        try:
            with open(get_file_in_database('pointers.csv'), 'r') as file:
                reader = DictReader(file)
                for row in reader:
                    pointers.append(
                        Pointer(
                            RomVariant(row['rom_variant']),
                            int(row['address'], 16),
                            int(row['points_to'], 16),
                            row['certainty'],
                            row['author'],
                            row['note']
                        )
                    )
        except OSError:
            # file cannot be read, just supply no pointers
            pass
        return pointers


    def _write_pointers(self):
        with open(get_file_in_database('pointers.csv'), 'w') as file:
            writer = DictWriter(
                file, fieldnames=['rom_variant', 'address', 'points_to', 'certainty', 'author', 'note'])
            writer.writeheader()
            for pointer in self.pointers:
                writer.writerow({
                    'rom_variant': pointer.rom_variant,
                    'address': hex(pointer.address),
                    'points_to': hex(pointer.points_to),
                    'certainty': pointer.certainty,
                    'author': pointer.author,
                    'note': pointer.note
                })


def get_pointer_database() -> PointerDatabase:
    return pointer_database_instance


