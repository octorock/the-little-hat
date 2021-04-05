from csv import DictReader, DictWriter
from os import path
from tlh.data.pointer import Pointer

from tlh.const import RomVariant
from tlh.data.constraints import Constraint


def get_file_in_database(filename: str) -> str:
    # TODO settings.get_database_location()
    return path.join('data', filename)

### Constraints ###


def read_constraints() -> list[Constraint]:
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
                        row['note']
                    )
                )
    except OSError:
        # file cannot be read, just supply no constraints
        pass
    return constraints


def write_constraints(constraints: list[Constraint]):
    with open(get_file_in_database('constraints.csv'), 'w') as file:
        writer = DictWriter(
            file, fieldnames=['romA', 'addressA', 'romB', 'addressB', 'certainty', 'author', 'note'])
        writer.writeheader()
        for constraint in constraints:
            writer.writerow({
                'romA': constraint.romA,
                'addressA': hex(constraint.addressA),
                'romB': constraint.romB,
                'addressB': hex(constraint.addressB),
                'certainty': constraint.certainty,
                'author': constraint.author,
                'note': constraint.note
            })

### Pointers ###


def read_pointers() -> list[Pointer]:
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


def write_pointers(pointers: list[Pointer]):
    with open(get_file_in_database('pointers.csv'), 'w') as file:
        writer = DictWriter(
            file, fieldnames=['rom_variant', 'address', 'points_to', 'certainty', 'author', 'note'])
        writer.writeheader()
        for pointer in pointers:
            writer.writerow({
                'rom_variant': pointer.rom_variant,
                'address': hex(pointer.address),
                'points_to': hex(pointer.points_to),
                'certainty': pointer.certainty,
                'author': pointer.author,
                'note': pointer.note
            })
