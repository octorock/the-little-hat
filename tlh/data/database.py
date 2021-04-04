from csv import DictReader, DictWriter
from os import path

from tlh.const import RomVariant
from tlh.data.constraints import Constraint


def get_file_in_database(filename: str) -> str:
    # TODO settings.get_database_location()
    return path.join('data', filename)


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
            writer.writerow(
                {
                    'romA': constraint.romA,
                    'addressA': hex(constraint.addressA),
                    'romB': constraint.romB,
                    'addressB': hex(constraint.addressB),
                    'certainty': constraint.certainty,
                    'author': constraint.author,
                    'note': constraint.note
                })