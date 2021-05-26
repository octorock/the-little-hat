from csv import DictReader, DictWriter
import os
from dataclasses import dataclass
import re
import subprocess
from tlh.data.database import get_file_in_database
from tlh import settings

@dataclass
class Replacement:
    source: str
    replacement: str
    dotall: bool

def clang_format(input: str) -> None:
    '''
    Write the code into a temporary file, run clang-format on it and then read the code back.
    '''

    # Format input
    TMP_FILE ='/tmp/ghidra_code.c'
    FORMAT_FILE = '/tmp/.clang-format'

    with open(TMP_FILE, 'w') as f:
        f.write(input)

    if not os.path.isfile(FORMAT_FILE):
        # Need to copy the .clang-format file due to https://stackoverflow.com/a/46374122
        subprocess.call(['cp', os.path.join(settings.get_repo_location(), '.clang-format'), FORMAT_FILE])

    subprocess.call(['clang-format', '--style=file', '-i', TMP_FILE])

    with open(TMP_FILE, 'r') as f:
        input = f.read()
    return input

# Use https://regex101.com/ to build the regular expressions
'''
with open(get_file_in_database('ghidra.csv'), 'w') as f:
    writer = DictWriter(f, fieldnames=['source', 'replacement', 'dotall'])
    writer.writeheader()
    for replacement in replacements:
        writer.writerow({
            'source': replacement.source, 
            'replacement': replacement.replacement,
            'dotall': replacement.dotall
        })
'''

def read_replacements_from_file() -> list[Replacement]:
    replacements = []
    with open(get_file_in_database('ghidra.csv'), 'r') as f:
        reader = DictReader(f)
        for row in reader:
            replacements.append(Replacement(row['source'], row['replacement'], row['dotall'] == True))
    return replacements


def improve_decompilation(code: str) -> str:
    # TODO instead of reading the csv file every time, provide a GUI to change the replacements while the program is running
    replacements = read_replacements_from_file()
    
    input = clang_format(code)

    # Do replacements
    for replacement in replacements:
        flags = re.MULTILINE
        if replacement.dotall:
            flags |= re.DOTALL
        input = re.sub(replacement.source, replacement.replacement, input, flags=flags)

    # input = clang_format(input)
    return input