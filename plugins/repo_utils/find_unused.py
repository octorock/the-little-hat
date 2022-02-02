from typing import List
import os
import re
from tlh import settings

from tlh.plugin.api import PluginApi

static_included_files = [
    'asm/rom_header.inc',
    'asm/macros.inc',
    'asm/macros/sounds.inc',
    'asm/macros/music_voice.inc',
    'asm/macros/scripts.inc',
    'asm/macros/entity.inc',
    'asm/macros/asm.inc',
    'asm/macros/m4a.inc',
    'asm/macros/map.inc',
    'asm/macros/function.inc',
    'asm/macros/gfx.inc',
    'asm/macros/ram.inc',
]


def list_all_asm_files() -> List[str]:
    result = []
    for root, dirs, files in os.walk(os.path.join(settings.get_repo_location(), 'asm')):
        for file in files:
            result.append(os.path.join(root, file))

    # TODO would also need to search for .include macros in asm files
    # Also search unused data asm files
    for root, dirs, files in os.walk(os.path.join(settings.get_repo_location(), 'data')):
        for file in files:
            # TODO maybe check for .inc as well
            if file.endswith('.s'):
                result.append(os.path.join(root, file))
    return result


def get_linker_files() -> List[str]:
    result = []
    with open(os.path.join(settings.get_repo_location(), 'linker.ld'), 'r') as f:
        for line in f:
            if '.o' in line:
                result.append(os.path.join(
                    settings.get_repo_location(), line.split('.o')[0].strip() + '.s'))
    return result


def list_all_nonmatch_files() -> List[str]:
    result = []
    for root, dirs, files in os.walk(os.path.join(settings.get_repo_location(), 'src')):
        for file in files:
            with open(os.path.join(root, file), 'r') as f:

                data = f.read()
                for match in re.findall(r'(?:NONMATCH|ASM_FUNC)\("(.*)"', data):
                    result.append(os.path.join(settings.get_repo_location(), match))

    return result


name = 'Find Unused Files'


def find_unused(api: PluginApi):
    all_asm_files = list_all_asm_files()
    linker_files = get_linker_files()

    included_files = [os.path.join(settings.get_repo_location(), x)
                      for x in static_included_files]

    nonmatch_files = list_all_nonmatch_files()

    # Remove linker files
    unused_asm_files = [
        x for x in all_asm_files if not x in linker_files and not x in included_files and not x in nonmatch_files]

    if len(unused_asm_files) == 0:
        api.show_message(name, 'No unused files found.')
        return

    text = f'Found {len(unused_asm_files)} unused files:\n'
    text += '\n'.join(unused_asm_files)
    text += '\n\nDelete all?'

    if not api.show_question(name, text):
        return

    for file in unused_asm_files:
        os.remove(file)

    api.show_message(name, f'Removed {len(unused_asm_files)} unused files.')