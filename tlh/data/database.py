from dataclass_csv import DataclassReader, DataclassWriter
from dataclasses import dataclass
from tlh import settings
from os import path
from tlh.data.constraints import Constraint

def get_file_in_database(filename: str) -> str:
    # TODO settings.get_database_location()
    return path.join('data', filename)


def read_constraints() -> list[Constraint]:
    constraints = []
    try:
        with open(get_file_in_database('constraints.csv'), 'r') as file:
            reader = DataclassReader(file, Constraint)
            for constraint in reader:
                constraints.append(constraint)
    except OSError:
        # file cannot be read, just supply no constraints
        pass
    return constraints

def write_constraints(constraints: list[Constraint]):
    with open(get_file_in_database('constraints.csv'), 'w') as file:
        writer = DataclassWriter(file, constraints, Constraint)
        writer.write()