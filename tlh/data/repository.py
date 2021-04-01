from dataclass_csv import DataclassReader, DataclassWriter
from dataclasses import dataclass
from tlh import settings
from os import path
from tlh.data.constraints import Constraint

def get_file_in_repo(filename: str) -> str:
    return path.join(settings.get_repo_location(), filename)


def read_constraints() -> list[Constraint]:
    constraints = []
    with open(get_file_in_repo('constraints.csv'), 'r') as file:
        reader = DataclassReader(file, Constraint)
        for constraint in reader:
            constraints.append(constraint)
    return constraints

def write_constraints(constraints: list[Constraint]):
    with open(get_file_in_repo('constraints.csv'), 'w') as file:
        writer = DataclassWriter(file, constraints, Constraint)
        writer.write()