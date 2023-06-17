from dataclasses import dataclass
import os
import re
from typing import List
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtCore import Qt
from tlh.plugin.api import PluginApi
from tlh import settings
from subprocess import check_call, check_output

@dataclass
class AsmFile:
    name: str
    folder: str
    size: int

@dataclass
class FolderStat:
    name: str
    size: int

class AsmStatsPlugin:
    name = 'Asm Stats'
    description = 'Calculates stats for the non_matching asm files'
    hidden = True

    def __init__(self, api: PluginApi) -> None:
        self.api = api

    def load(self) -> None:
        self.action_calculate = self.api.register_menu_entry('Calculate Stats', self.slot_calculate_stats)
        self.action_calculate.setShortcut(QKeySequence(Qt.CTRL + Qt.Key_F2))
        self.action_finished_files = self.api.register_menu_entry('Find finished files', self.slot_find_finished)

    def unload(self) -> None:
        self.api.remove_menu_entry(self.action_calculate)
        self.api.remove_menu_entry(self.action_finished_files)

    def slot_calculate_stats(self) -> None:
        #self.calc_stats_from_asm_files()
        self.calc_stats_from_map()

    def calc_stats_from_asm_files(self) -> None:
        asm_folder = os.path.join(settings.get_repo_location(), 'asm', 'non_matching')

        # Query file sizes
        asm_files: List[AsmFile] = []
        folders: List[FolderStat] = []
        for root, dirs, files in os.walk(asm_folder):
            folder_name = os.path.basename(root)
            folder_size = 0

            for file in files:
                path = os.path.join(root, file)
                size = os.path.getsize(path)
                asm_files.append(AsmFile(file, folder_name, size))
                folder_size += size
            folders.append(FolderStat(folder_name, folder_size))

        if True:
            print('--- Smallest Folders: ---')
            folders.sort(key=lambda x : x.size)
            for folder in folders:
                print('{:<26} {}'.format(folder.name, folder.size))

        if True:
            print('--- Smallest Files ---')
            asm_files.sort(key=lambda x:x.size)
            for file in asm_files:
                print('{:<26} {:<5} {}'.format(file.folder, file.size, file.name[:-4]))
                if file.size > 250:
                    break;

        if True:
            print('--- Stats ---')
            print(f'{len(asm_files)} functions')


        if True:
            foundOB=False
            foundOBF=False
            for folder in folders:
                if folder.name == 'octorokBoss':
                    print(f'OctorokBoss progress: {(1-folder.size/77453)*100:.2f}% ({77453-folder.size}/77453)')
                    foundOB = True
                if folder.name == 'octorokBossFrozen':
                    print(f'OctorokBossFrozen progress: {(1-folder.size/17832)*100:.2f}% ({17832-folder.size}/17832)')
                    foundOBF = True
                if foundOB and foundOBF:
                    break


    def slot_find_finished(self) -> None:
        src_folder = os.path.join(settings.get_repo_location(), 'src')
        finished_files = []
        for root, dirs, files in os.walk(src_folder):
            for file in files:
                if file.endswith('.c'):
                    abspath = os.path.join(root, file)
                    with open(abspath, 'r') as input:
                        unfinished = 'ASM_FUNC' in input.read()
                        if not unfinished:
                            finished_files.append(os.path.relpath(abspath, src_folder))
        print('Finished files:')
        finished_files.sort()
        #for file in finished_files:
        #    print(file)

        with open('tmp/finished_files_new.txt', 'w') as file:
            file.write('\n'.join(finished_files))

        try:
            check_call(['diff', 'tmp/finished_files.txt', 'tmp/finished_files_new.txt'])
            print('same')
        except:
            print('changed!')

    def calc_stats_from_map(self) -> None:
        src = 0
        asm = 0
        src_data = 0
        data = 0
        non_matching = 0
        still_asm = 0

        funcs = self.collect_non_matching_funcs()
        # Remove all non matching funcs from count
        non_matching_funcs = []
        asm_funcs = []
        for func in funcs:
            if func[0] == 'ASM_FUNC':
                asm_funcs.append(func[1])
            else:
                non_matching_funcs.append(func[1])

        asm_files: List[AsmFile] = []

        handwritten_files = [
            'asm/crt0.o',
            'asm/veneer.o',
            'data/data_08000360.o',
            'asm/code_08000E44.o',
            'asm/lib/libgcc.o',
            'asm/code_08000F10.o',
            'data/data_08000F54.o',
            'asm/enemy.o',
            'src/droptables.o',
            'asm/code_08001A7C.o',
            'data/gfx/sprite_ptrs.o',
            'asm/code_08003FC4.o',
            'asm/code_080043E8.o',
            'data/gfx/link_animations.o',
            'asm/code_08007CAC.o',
            'data/data_08007DF4.o',
            'asm/player.o',
            'asm/intr.o',
            'asm/lib/m4a_asm.o',
            'asm/lib/libagbsyscall.o',
        ]
        handwritten = 0

        with open(os.path.join(settings.get_repo_location(), 'tmc.map'), 'r') as map:
            # Skip to the linker script section
            line = map.readline()
            while not line.startswith('Linker script and memory map'):
                line = map.readline()
            while not line.startswith('rom'):
                line = map.readline()

            prev_symbol = None
            prev_symbol_file = None # file the previous symbol was in
            prev_addr = 0
            cur_file = None
            cur_dir = None
            cur_asm_file = None
            for line in map:
                if line.startswith(' .'):
                    arr = line.split()
                    section = arr[0]
                    size = int(arr[2], 16)
                    filepath = arr[3]
                    dir = filepath.split('/')[0]
                    file = filepath.split('/')[1] # TODO is this correct?

                    cur_file = os.path.basename(filepath)
                    cur_dir = os.path.dirname(filepath)

                    if section == '.text':
                        if dir == 'src':
                            src += size
                        elif dir == 'asm':
                            if filepath.find("asm/src/") != -1 or filepath.find("asm/lib/") != -1:
                                src += size
                            elif filepath in handwritten_files:
                                print('HANDWRITTEN', filepath, size)
                                handwritten += size
                            else:
                                asm_files.append(AsmFile(os.path.basename(filepath), os.path.dirname(filepath), size))
                                asm += size
                        elif dir == 'data':
                            # scripts
                            src_data += size
                        elif dir == '..':
                            # libc
                            src += size
                    elif section == '.rodata':
                        if dir == 'src':
                            src_data += size
                        elif dir == 'data':
                            data += size

                elif line.startswith('  '):
                    arr = line.split()
                    if len(arr) == 2 and arr[1] != '':  # It is actually a symbol


                        if prev_symbol in non_matching_funcs or prev_symbol in asm_funcs:
                            if prev_symbol_file == 'kingDaltus.o':
                                print(prev_symbol_file, prev_symbol)
                            if cur_asm_file is None or cur_asm_file.name != prev_symbol_file:
                                cur_asm_file = AsmFile(prev_symbol_file, cur_dir, 0)
                                asm_files.append(cur_asm_file)
                            size = int(arr[0], 16) - prev_addr
                            cur_asm_file.size += size
                            if prev_symbol in non_matching_funcs:
                                non_matching += size
                            else:
                                still_asm += size


                        # if prev_symbol in non_matching_funcs:
                        #     # Calculate the length for non matching function
                        #     non_matching += int(arr[0], 16) - prev_addr
                        #     print(arr[1])
                        #     # TODO split into non_matching and asm_func

                        prev_symbol = arr[1]
                        prev_symbol_file = cur_file
                        prev_addr = int(arr[0], 16)
                elif line.strip() == '':
                    # End of linker script section
                    break

        src -= non_matching + still_asm
        asm += non_matching + still_asm

        #print(src, asm, src_data, data)

        if False:
            print('--- Smallest Files ---')
            asm_files.sort(key=lambda x:x.size)
            for file in asm_files:
                print('{:<26} {:<5} {}'.format(file.folder, file.size, file.name[:-2]))
                if file.size > 250:
                    break;

        if True:
            with open('/tmp/code.csv', 'w') as f:
                f.write(f'non_matching,{non_matching}\n')
                f.write(f'asm_funcs,{still_asm}\n')
                f.write(f'handwritten,{handwritten}\n')
                f.write('\n')

                for file in asm_files:
                    f.write(f'{file.folder},{file.name[:-2]},{file.size}\n')

        if False:
            print('--- Results ---')
            # print(f'src: {src}')
            # print(f'asm: {asm}')
            print(f'total: {src+asm}')
            print(f'non_matching: {non_matching}')
            print(f'asm_funcs: {still_asm}')
            print(f'handwritten: {handwritten}')

        #return (src, asm, src_data, data)

    def collect_non_matching_funcs(self):
        result = []
        for root, dirs, files in os.walk(os.path.join(settings.get_repo_location(), 'src')):
            for file in files:
                if file.endswith('.c'):
                    with open(os.path.join(root, file), 'r') as f:
                        data = f.read()
                        # Find all NONMATCH and ASM_FUNC macros
                        for match in re.findall(r'(NONMATCH|ASM_FUNC)\(".*",\W*\w*\W*(\w*).*\)', data):
                            result.append(match)
        return result


