from os import walk, mkdir, path
from pathlib import Path
from tlh import settings



def patch_extern_struct(lines):
    for i,line in enumerate(lines):
        if '} extern' in line:
            lines[i] = line.replace('} extern', '}')
    return lines

def patch_extern_arrays(lines):
    # For now just remove extern arrays as Ghidra cannot parse them?
    for i,line in enumerate(lines):
        if 'extern' in line and '[' in line and ']' in line:
            lines[i] = ''
    return lines

def patch_types_h(lines):
    return map(lambda line: line.replace('uint8_t', 'unsigned char')
    .replace('uint16_t', 'unsigned short')
    .replace('uint32_t', 'unsigned int')
    .replace('uint64_t', 'unsigned long long')
    .replace('int8_t', 'signed char')
    .replace('int16_t', 'signed short')
    .replace('int32_t', 'signed int')
    .replace('int64_t', 'signed long long')
    , lines)

def patch_entity_h(lines):
    for i,line in enumerate(lines):
        if 'struct Entity' in line:
            lines.insert(i, '#pragma pack(1)\n')
            break
    return lines

file_specific_patches = {
    'structures.h': patch_extern_arrays,
    'gba/types.h': patch_types_h,
    'entity.h': patch_entity_h
}

general_patches = [
    patch_extern_struct
]


def export_headers():
    INCLUDE_FOLDER = settings.get_repo_location()+'/include'
    OUTPUT_FOLDER = 'tmp/ghidra_types'
    Path(OUTPUT_FOLDER).mkdir(parents=True, exist_ok=True)

    for (dirpath, dirnames, filenames) in walk(INCLUDE_FOLDER):
        for filepath in filenames:
            rel_dirpath = dirpath[len(INCLUDE_FOLDER)+1:]
            abs_path = path.join(dirpath, filepath)
            rel_path = path.join(rel_dirpath, filepath)
            lines = open(abs_path, 'r').readlines()

            # Apply general patches
            for patch in general_patches:
                lines = patch(lines)

            # Apply file-specific patches
            if rel_path in file_specific_patches:
                lines = file_specific_patches[rel_path](lines)

            with open(OUTPUT_FOLDER+'/'+rel_path.replace('/', '_'), 'w') as file:
                file.writelines(lines)
