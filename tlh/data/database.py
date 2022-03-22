from csv import DictReader, DictWriter
from os import path

from sortedcontainers.sortedlist import SortedKeyList
from tlh.data.symbols import Symbol, SymbolList
from tlh import settings

from PySide6.QtGui import QColor
from tlh.data.annotations import Annotation

from PySide6.QtCore import QObject, Signal
from tlh.data.pointer import Pointer, PointerList

from tlh.const import ALL_ROM_VARIANTS, CUSTOM_ROM_VARIANTS, ROM_OFFSET, RomVariant
from tlh.data.constraints import Constraint, ConstraintManager


def get_file_in_database(filename: str) -> str:
    # TODO settings.get_database_location()
    return path.join('data', filename)


def initialize_databases(parent) -> None:
    '''
    Initialize all database singletons
    '''
    global pointer_database_instance, constraint_database_instance, annotation_database_instance, symbol_database_instance
    if settings.is_using_constraints():
        print('pointers')
        pointer_database_instance = PointerDatabase(parent)
        print('constraints')
        constraint_database_instance = ConstraintDatabase(parent)
    print('annotations')
    annotation_database_instance = AnnotationDatabase(parent)
    print('symbols')
    symbol_database_instance = SymbolDatabase(parent)


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
        if settings.is_auto_save():
            self._write_constraints()
        else:
            # TODO Mark as dirty?
            pass
        if constraint.enabled:
            self.constraints_changed.emit()

    def add_constraints(self, constraints: list[Constraint]) -> None:
        self.constraints += constraints
        if settings.is_auto_save():
            self._write_constraints()
        else:
            # TODO Mark as dirty?
            pass
        for constraint in constraints:
            if constraint.enabled:  # Only emit change if one of the added constraints is enabled
                self.constraints_changed.emit()
                break

    def remove_constraints(self, constraints: list[Constraint]) -> None:
        for constraint in constraints:
            self.constraints.remove(constraint)
        if settings.is_auto_save():
            self._write_constraints()
        else:
            # TODO Mark as dirty?
            pass
        for constraint in constraints:
            if constraint.enabled:  # Only emit change if one of the removed constraints was enabled
                self.constraints_changed.emit()
                break

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
        with open(get_file_in_database('constraints.csv'), 'w', newline='') as file:
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
        pointers = {
            RomVariant.USA: [],
            RomVariant.DEMO: [],
            RomVariant.EU: [],
            RomVariant.JP: [],
            RomVariant.DEMO_JP: [],
            RomVariant.CUSTOM: [],
            RomVariant.CUSTOM_EU: [],
            RomVariant.CUSTOM_JP: [],
            RomVariant.CUSTOM_DEMO_USA: [],
            RomVariant.CUSTOM_DEMO_JP: [],
        }

        for pointer in self._read_pointers():
            pointers[pointer.rom_variant].append(pointer)

        self.pointers = {
            RomVariant.USA: PointerList(pointers[RomVariant.USA], RomVariant.USA),
            RomVariant.DEMO: PointerList(pointers[RomVariant.DEMO], RomVariant.DEMO),
            RomVariant.EU: PointerList(pointers[RomVariant.EU], RomVariant.EU),
            RomVariant.JP: PointerList(pointers[RomVariant.JP], RomVariant.JP),
            RomVariant.DEMO_JP: PointerList(pointers[RomVariant.DEMO_JP], RomVariant.DEMO_JP),
            RomVariant.CUSTOM: PointerList(pointers[RomVariant.CUSTOM], RomVariant.CUSTOM),
            RomVariant.CUSTOM_EU: PointerList(pointers[RomVariant.CUSTOM_EU], RomVariant.CUSTOM_EU),
            RomVariant.CUSTOM_JP: PointerList(pointers[RomVariant.CUSTOM_JP], RomVariant.CUSTOM_JP),
            RomVariant.CUSTOM_DEMO_USA: PointerList(pointers[RomVariant.CUSTOM_DEMO_USA], RomVariant.CUSTOM_DEMO_USA),
            RomVariant.CUSTOM_DEMO_JP: PointerList(pointers[RomVariant.CUSTOM_DEMO_JP], RomVariant.CUSTOM_DEMO_JP),
        }

    def get_pointers(self, rom_variant: RomVariant) -> PointerList:
        return self.pointers[rom_variant]

    def add_pointer(self, pointer: Pointer) -> None:
        self.pointers[pointer.rom_variant].append(pointer)
        if settings.is_auto_save():
            self._write_pointers()
        else:
            # TODO Mark as dirty?
            pass
        self.pointers_changed.emit()

    def add_pointers(self, pointers: list[Pointer]) -> None:
        for pointer in pointers:
            self.pointers[pointer.rom_variant].append(pointer)
        if settings.is_auto_save():
            self._write_pointers()
        else:
            # TODO Mark as dirty?
            pass
        self.pointers_changed.emit()

    def remove_pointers(self, pointers: list[Pointer]) -> None:
        for pointer in pointers:
            self.pointers[pointer.rom_variant].remove(pointer)
        if settings.is_auto_save():
            self._write_pointers()
        else:
            # TODO Mark as dirty?
            pass
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
        # TODO separate pointers into different files per variant
        with open(get_file_in_database('pointers.csv'), 'w', newline='') as file:
            writer = DictWriter(
                file, fieldnames=['rom_variant', 'address', 'points_to', 'certainty', 'author', 'note'])
            writer.writeheader()
            for variant in [RomVariant.USA, RomVariant.DEMO, RomVariant.EU, RomVariant.JP, RomVariant.CUSTOM, RomVariant.CUSTOM_EU, RomVariant.CUSTOM_JP, RomVariant.CUSTOM_DEMO_USA, RomVariant.CUSTOM_DEMO_JP]: # Name all explicitely to keep the same order
                for pointer in self.pointers[variant].get_sorted_pointers():
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


### Annotations ###
annotation_database_instance = None


class AnnotationDatabase(QObject):

    annotations_changed = Signal()

    def __init__(self, parent) -> None:
        if annotation_database_instance is not None:
            raise RuntimeError('Already initialized')
        super().__init__(parent=parent)
        self.annotations = self._read_annotations()

    def get_annotations(self) -> list[Annotation]:
        return self.annotations

    def add_annotation(self, annotation: Annotation) -> None:
        self.annotations.append(annotation)
        if settings.is_auto_save():
            self._write_annotations()
        else:
            # TODO Mark as dirty?
            pass
        self.annotations_changed.emit()

    def add_annotations(self, annotations: list[Annotation]) -> None:
        self.annotations += annotations
        if settings.is_auto_save():
            self._write_annotations()
        else:
            # TODO Mark as dirty?
            pass
        self.annotations_changed.emit()

    def _read_annotations(self) -> list[Annotation]:
        annotations = []
        try:
            with open(get_file_in_database('annotations.csv'), 'r') as file:
                reader = DictReader(file)
                for row in reader:
                    annotations.append(
                        Annotation(
                            RomVariant(row['rom_variant']),
                            int(row['address'], 16),
                            int(row['length']),
                            QColor(row['color']),
                            row['author'],
                            row['note']
                        )
                    )
        except OSError:
            # file cannot be read, just supply no annotations
            pass
        return annotations

    def _write_annotations(self):
        with open(get_file_in_database('annotations.csv'), 'w', newline='') as file:
            writer = DictWriter(
                file, fieldnames=['rom_variant', 'address', 'length', 'color', 'author', 'note'])
            writer.writeheader()
            for annotation in self.annotations:
                writer.writerow({
                    'rom_variant': annotation.rom_variant,
                    'address': hex(annotation.address),
                    'length': annotation.length,
                    'color': annotation.color.name(),
                    'author': annotation.author,
                    'note': annotation.note
                })


def get_annotation_database() -> AnnotationDatabase:
    return annotation_database_instance


### Symbols ###
symbol_database_instance = None


class SymbolDatabase(QObject):

    symbols_changed = Signal()

    def __init__(self, parent) -> None:
        if symbol_database_instance is not None:
            raise RuntimeError('Already initialized')
        super().__init__(parent=parent)
        self.symbols = self._read_symbols()

    def are_symbols_loaded(self, rom_variant: RomVariant) -> bool:
        return rom_variant in self.symbols

    def get_symbols(self, rom_variant: RomVariant) -> SymbolList:
        return self.symbols[rom_variant]

    def _read_symbols(self) -> dict[RomVariant, SymbolList]:
        symbol_dict: dict[RomVariant, SymbolList] = {}
        for rom_variant in ALL_ROM_VARIANTS:
            symbols_csv_path = get_file_in_database(f'symbols_{rom_variant}.csv')
            if path.isfile(symbols_csv_path):
                symbols = SortedKeyList([], key=lambda x:x.address)
                with open(symbols_csv_path, 'r') as file:
                    reader = DictReader(file)
                    for row in reader:
                        symbols.add(Symbol(
                            int(row['address'], 16),
                            row['name'],
                            row['file'],
                            int(row['length'], 16)
                        ))
                symbol_dict[rom_variant] = SymbolList(symbols)

        return symbol_dict

    def _write_symbols(self) -> None:
        for rom_variant in self.symbols:

            # Don't save the symbols for the custom rom as it is always changing
            if rom_variant in CUSTOM_ROM_VARIANTS:
                continue

            with open(get_file_in_database(f'symbols_{rom_variant}.csv'), 'w') as file:
                writer = DictWriter(file, fieldnames=['address', 'name', 'file', 'length'])
                writer.writeheader()
                for symbol in self.symbols[rom_variant].symbols:
                    writer.writerow({
                        'address': hex(symbol.address),
                        'name': symbol.name,
                        'file': symbol.file,
                        'length': hex(symbol.length)
                    })

    def load_symbols_from_map(self, rom_variant: RomVariant, path: str) -> None:
        symbols = SortedKeyList([], key=lambda x:x.address)
        with open(path, 'r') as map_file:

            # ignore header
            line = map_file.readline()
            while not line.startswith('rom'):
                line = map_file.readline()
            line = map_file.readline()
            while not line.startswith('rom'): # The second line starting with 'rom' is the one we need
                line = map_file.readline()

            # Parse declarations

            prev_symbol = None
            current_file = 'UNKNOWN'
            for line in map_file:
                if line.startswith(' .'):
                    # ignore this definition of filename
                    continue
                elif line.startswith('  '):
                    parts = line.split()
                    if len(parts) == 2 and parts[1] !='': # it is actually a symbol
                        addr = int(parts[0],16)-ROM_OFFSET
                        if prev_symbol is not None:
                            prev_symbol.length = addr-prev_symbol.address
                        symbol = Symbol(addr, parts[1], current_file)
                        symbols.add(symbol)
                        prev_symbol = symbol

                elif not line.startswith(' *'):
                    # this defines the name
                    current_file = line.split('(')[0].strip()
        self.symbols[rom_variant] = SymbolList(symbols)
        self.symbols_changed.emit()



def get_symbol_database() -> SymbolDatabase:
    return symbol_database_instance

def save_all_databases() -> None:
    get_pointer_database()._write_pointers()
    get_constraint_database()._write_constraints()
    get_annotation_database()._write_annotations()
    # Only manually save symbols as they seldom change
    #get_symbol_database()._write_symbols()
