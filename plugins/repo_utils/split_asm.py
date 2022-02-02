# Split asm .s file into non_matching .inc files and output corresponding c file with ASM_FUNC macros
import sys
from typing import List
import os
from dataclasses import dataclass
from pathlib import Path
from tlh import settings
from tlh.plugin.api import PluginApi
from PySide6.QtWidgets import QApplication


@dataclass
class Func:
    name: str
    lines: List[str]


def parse_file(filepath: str) -> List[Func]:

    result = []

    with open(filepath, 'r') as f:
        current_function = None
        current_lines = []
        ignore_next_line = False

        for line in f:
            if ignore_next_line:
                ignore_next_line = False
                continue

            if 'thumb_func_start' in line:
                if current_function is not None:
                    result.append(Func(current_function, current_lines))
                    current_lines = []

                current_function = line.split()[1]
                ignore_next_line = True
            elif current_function is not None and line.strip() != '':
                current_lines.append(line)

        if current_function is not None:
            result.append(Func(current_function, current_lines))
    return result


def main():
    if len(sys.argv) != 2:
        print('usage: split_asm.py ASM_FILE_NAME')
        return


name = 'Split Asm'


def split_asm(api: PluginApi, path: str) -> str:
    filepath = os.path.join(settings.get_repo_location(), 'asm/'+path+'.s')
    if not os.path.isfile(filepath):
        api.show_error(name, f'Could not find file: {filepath}')
        return

    filename = os.path.split(filepath)[1]
    foldername = filename[:-2]
    non_matching_folder = os.path.join('asm', 'non_matching', foldername)
    non_matching_path = os.path.join(
        settings.get_repo_location(), non_matching_folder)

    funcs = parse_file(filepath)

    text = 'Found functions:\n'
    for func in funcs:
        text += f'{func.name}: {len(func.lines)} lines\n'

    text += f'\nFile: {filepath}\n'
    text += f'Output folder: {non_matching_path}\n'
    text += '\nExecute?'

    if not api.show_question(name, text):
        return

    Path(non_matching_path).mkdir(parents=True, exist_ok=True)

    lines = []

    lines.append('#include "global.h"')
    lines.append('#include "entity.h"\n')
    for func in funcs:
        funcpath = os.path.join(non_matching_folder, func.name+'.inc')
        with open(os.path.join(settings.get_repo_location(), funcpath), 'w') as f:
            f.write('\t.syntax unified\n')
            f.writelines(func.lines)
            f.write('\t.syntax divided\n')

        #print(f'ASM_FUNC("{funcpath}", void {func.name}(Entity* this))\n')
        #lines.append(f'ASM_FUNC("{funcpath}", void {func.name}())\n')
        lines.append(
            f'ASM_FUNC("{funcpath}", void {func.name}(Entity* this))\n')

    out = '\n'.join(lines)

    with open(os.path.join(settings.get_repo_location(), 'src', path + '.c'), 'w') as f:
        f.write(out)
    api.show_message(
        name, f'Created file at src/{path}.c. Now change the path in linker.ld.')
