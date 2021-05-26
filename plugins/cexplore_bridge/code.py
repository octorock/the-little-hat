from typing import List, Optional, Tuple
from tlh.settings import get_repo_location
import os
import re


def find_inc_file(name: str) -> Optional[str]:
    filename = name + '.inc'
    search_path = os.path.join(get_repo_location(), 'asm', 'non_matching')
    for root, dirs, files in os.walk(search_path):
        if filename in files:
            return os.path.join(root, filename)
    return None


def find_source_file(name: str) -> Optional[str]:
    # Get the source file from tmc.map
    with open(os.path.join(get_repo_location(), 'tmc.map'), 'r') as f:
        current_file = None
        for line in f:
            if line.startswith(' .text'):
                current_file = line.split()[3]
            elif line.strip().endswith(name):
                return current_file[0:-2] + '.c'
        return None


def extract_nonmatching_section(inc_path: str, src_file: str) -> Optional[str]:
    (headers, data) = read_file_split_headers(src_file)

    # match nonmatching section
    match = re.search(
        r'NONMATCH\(\"'+inc_path+r'\", ?(.*?)\) ?{(.*?)END_NONMATCH', ''.join(data), re.MULTILINE | re.DOTALL)
    if match:
        return ''.join(headers) + '// end of existing headers\n\n' + match.group(1) + ' {' + match.group(2)

    match = re.search(
        r'ASM_FUNC\(\"'+inc_path+r'\", ?(.*?)\)', ''.join(data), re.MULTILINE | re.DOTALL)
    if match:
        return ''.join(headers) + '// end of existing headers\n\n' + match.group(1) + ') {\n\n}'
    return None


def prepare_asm(inc_file: str, name: str) -> str:
    lines = []
    with open(inc_file, 'r') as f:
        for line in f:
            l = line.strip()
            if l == '' and len(lines) == 0:  # ignore empty lines at the beginning
                continue
            if l != '.text' and l != '.syntax unified' and l != '.syntax divided':
                lines.append(line)
    return 'thumb_func_start ' + name + '\n' + name + ':\n' + (''.join(lines))


def get_code(name: str) -> Tuple[bool, str, str]:
    # Find the .inc file for the non matching function
    inc_file = find_inc_file(name)
    if inc_file is None:
        return (True, f'No {name}.inc found in asm/non_matching folder.', '')

    src_file = find_source_file(name)
    if src_file is None:
        return (True, f'Source file for {name} not found in tmc.map.', '')
    src_file = os.path.join(get_repo_location(), src_file)

    if not os.path.isfile(src_file):
        return(True, f'{src_file} is not a file.', '')

    inc_path = inc_file.replace(get_repo_location() + '/', '')

    src = extract_nonmatching_section(inc_path, src_file)
    if src is None:
        return(True, f'No NONMATCH or ASM_FUNC section found for {inc_path} in {src_file}.', '')

    asm = prepare_asm(inc_file, name)

    return (False, asm, src)


def split_code(code: str) -> Tuple[str, str]:
    if '// end of existing headers' in code:
        code = code.split('// end of existing headers')[1].strip()

    headers = []
    data = []
    lines = code.split('\n')
    in_headers = True
    for line in lines:
        if in_headers:
            if '{' in line and not 'struct' in line:
                in_headers = False
                data.append(line)
            elif 'NONMATCH' in line or 'ASM_FUNC' in line:
                in_headers = False
                data.append(line)
            else:
                headers.append(line)
        else:
            data.append(line)
    return ('\n'.join(headers).strip(), '\n'.join(data).strip())


def read_file_split_headers(src_file: str) -> Tuple[List[str], List[str]]:
    with open(src_file, 'r') as f:
        data = []
        headers = []

        in_headers = True
        # match headers
        for line in f:
            if in_headers:
                if '{' in line and not 'struct' in line:
                    in_headers = False
                    data.append(line)
                elif 'NONMATCH' in line or 'ASM_FUNC' in line:
                    in_headers = False
                    data.append(line)
                else:
                    headers.append(line)
            else:
                data.append(line)
    return (headers, data)


def store_code(name: str, header: str, src: str, matching: bool) -> Tuple[bool, str]:
    # Find the .inc file for the non matching function
    inc_file = find_inc_file(name)
    if inc_file is None:
        return (True, f'No {name}.inc found in asm/non_matching folder.')

    src_file = find_source_file(name)
    if src_file is None:
        return (True, f'Source file for {name} not found in tmc.map.')
    src_file = os.path.join(get_repo_location(), src_file)

    if not os.path.isfile(src_file):
        return(True, f'{src_file} is not a file.')

    inc_path = inc_file.replace(get_repo_location() + '/', '')

    (headers, data) = read_file_split_headers(src_file)

    # Append headers
    if header.strip() != '':
        headers.append(header.strip() + '\n\n')

    # Add NONMATCH macro to replacement string when not matching
    if not matching:
        src = re.sub(r'(.*?)\s*{', r'NONMATCH("' +
                     inc_path + r'", \1) {', src, 1) + '\nEND_NONMATCH'

    match = re.search(
        r'NONMATCH\(\"'+re.escape(inc_path)+r'\", ?(.*?)\) ?{(.*?)END_NONMATCH', ''.join(data), re.MULTILINE | re.DOTALL)
    if match:
        data = re.sub(
            r'NONMATCH\(\"'+re.escape(inc_path)+r'\", ?(.*?)\) ?{(.*?)END_NONMATCH', src, ''.join(data), flags=re.MULTILINE | re.DOTALL)
    else:
        match = re.search(
            r'ASM_FUNC\(\"'+re.escape(inc_path)+r'\", ?(.*?)\)$', ''.join(data), re.MULTILINE | re.DOTALL)
        if match:
            data = re.sub(
                r'ASM_FUNC\(\"'+re.escape(inc_path)+r'\", ?(.*?)\)$', src, ''.join(data), flags=re.MULTILINE | re.DOTALL)
        else:
            return (True, f'No NONMATCH or ASM_FUNC section found for {inc_path} in {src_file}.')

    with open(src_file, 'w') as f:
        f.write(''.join(headers))
        f.write(data)


    if matching:
        # Remove the .inc file as its no longer neede
        os.remove(inc_file)
        

    return (False, '')
