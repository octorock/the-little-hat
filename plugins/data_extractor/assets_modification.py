
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

from plugins.data_extractor.assets import Assets
from tlh.const import ALL_ROM_VARIANTS, RomVariant
from tlh.data.symbols import Symbol

@dataclass
class Asset:
    '''
    New asset that we want to add to the asset list.
    '''
    name: str
    type: str
    offset: int # Offset from the graphics start in the current variant
    size: int
    compressed: bool

@dataclass
class NewAsset:
    '''
    Asset for the current variant that is already as in the asset list.
    '''
    path: str
    type: str
    start: int
    size: int

def insert_new_assets_to_list(assets: Assets, start_symbol: Symbol, new_assets: List[Asset], variant: RomVariant) -> Assets:
    '''
    Insert the new assets into the asset list for the current variant.
    '''
    result: List = []

    # Convert assets with offset relative to graphics start into assets with a fixed start point (relative to the current variant).
    to_insert: List[NewAsset] = []
    for asset in new_assets:
        path = build_path(asset)
        start = start_symbol.address + asset.offset
        to_insert.append(NewAsset(path, asset.type, start, asset.size))

    # Sort the list of assets to be inserted.
    to_insert.sort(key=lambda x:x.start)

    # Remove gfx_unknown assets from the result list. They will be added again later (but the numbering might be different).
    for asset in assets.assets:
        if 'path' in asset and asset['path'].startswith('assets/gfx_unknown'):
            continue
        if 'path' in asset and not 'type' in asset:
            asset['type'] = 'unknown'
        result.append(asset)

    offsets = {}
    for a_variant in ALL_ROM_VARIANTS:
        offsets[a_variant] = 0

    # just prevent typing errors
    asset = None

    # Iterate over the results
    insert_index = 0
    result_index = 0
    last_used_byte = -1
    unknown_id = 0
    while result_index < len(result):
        old_asset = result[result_index]
        if 'offsets' in old_asset:
            for key in old_asset['offsets']:
                offsets[key] = old_asset['offsets'][key]
        elif 'path' in old_asset:
            if belongs_to_variant(old_asset, variant):
                if insert_index < len(to_insert):
                    new_asset = to_insert[insert_index]
                    if new_asset.start < calculate_offset(old_asset['start'], variant, offsets):


                        if last_used_byte != -1 and new_asset.start > last_used_byte:
                            last_used_byte, unknown_id, result_index = insert_unknown_if_necessary(new_asset.start, last_used_byte, unknown_id, result, result_index, variant, offsets)
                        elif last_used_byte != -1 and new_asset.start < last_used_byte:
                            prev_asset = result[result_index-1]

                            if prev_asset['start'] == new_asset.start:
                                if prev_asset['size'] != new_asset.size:
                                    print(f'Asset {new_asset.path} at same position as {prev_asset["path"]} but with different size.')

                                    if prev_asset['type'] != new_asset.type:
                                        raise Exception('Cannot resolve due to different types.')
                                    new_size = max(new_asset.size, prev_asset['size'])
                                    print(f'Adapt size to {new_size}')
                                    prev_asset['size'] = new_size
                                    last_used_byte = new_asset.start + new_size
                                # Same asset. Ignore the new one.
                                insert_index += 1
                                continue
                            else:
                                if prev_asset['type'] == 'unknown':
                                    # The size of the previous unknown asset can be adapted.
                                    new_size = new_asset.start - prev_asset['start']
                                    print(f'Adapt size of {prev_asset["path"]} from {prev_asset["size"]} to {new_size}.')
                                    prev_asset['size'] = new_size
                                else:
                                    raise Exception(f'Overlap of {new_asset.path} and {prev_asset["path"]} cannot be resolved.')

                        # Insert the new_asset before
                        result.insert(result_index, {
                            'path': new_asset.path,
                            'start': invert_offset(new_asset.start, variant, offsets),
                            'size': new_asset.size,
                            'type': new_asset.type,
                        })

                        last_used_byte = new_asset.start + new_asset.size
                        insert_index += 1
                        result_index += 1
                        # Do not increase the result_index, so that multiple new_assets can be inserted before.
                        continue
                    elif new_asset.start == calculate_offset(old_asset['start'], variant, offsets):
                        if new_asset.size != old_asset['size']:
                            print(f'Asset {new_asset.path} at same position as {old_asset["path"]}, but with different size {new_asset.size} != {old_asset["size"]}.')
                            old_asset['size'] = max(new_asset.size, old_asset['size'])
                        # Ignore this asset as it is the same
                        print(f'Ignore {new_asset.path}')
                        insert_index += 1
                        continue
                    #else:
                        #raise Exception(f'Asset {new_asset.path} is overlapping {old_asset["path"]}')
                    # TODO check for equality
                    # TODO Add new unknownsG
                #print(result[result_index])
                old_res = result_index
                last_used_byte, unknown_id, result_index = insert_unknown_if_necessary(calculate_offset(old_asset['start'], variant, offsets), last_used_byte, unknown_id, result, result_index, variant, offsets)
                #print('>', result[result_index])
                #print(old_asset)
                #if result_index != old_res:
                    #break
                last_used_byte = calculate_offset(old_asset['start'], variant, offsets) + old_asset['size']
        result_index += 1

    write_assets_assembly(result)
    return Assets(result)

def calculate_offset(start: int, variant: RomVariant, offsets: str) -> int:
    return start + offsets[variant]

def invert_offset(start: int, variant: RomVariant, offsets: str) -> int:
    return start - offsets[variant]

def belongs_to_variant(asset: dict, variant: RomVariant) -> bool:
    '''Is this asset entry relevant to the current variant?'''
    if 'variants' in asset:
        return variant in asset['variants']
    return True

def insert_unknown_if_necessary(new_start: int, last_used_byte: int, unknown_id: int, result: List, result_index: int, variant: RomVariant, offsets: dict) -> Tuple[int, int, int]:
    if last_used_byte != -1 and new_start > last_used_byte:
        result.insert(result_index, {
            'path': f'assets/gfx_unknown_{unknown_id}.bin',
            'start': invert_offset(last_used_byte, variant, offsets),
            'size': new_start - last_used_byte,
            'type': 'unknown',
        })
        result_index += 1
        unknown_id += 1
        last_used_byte = new_start
    return last_used_byte, unknown_id, result_index

def build_path(asset: Asset) -> str:
    '''Return the path to the asset.'''
    if asset.type == 'tileset_gfx':
        asset.type = 'tileset'
        if asset.compressed:
            return 'tilesets/' + asset.name + '.4bpp.lz'
        else:
            return 'tilesets/' + asset.name + '.4bpp'
    elif asset.type == 'gfx':
        if asset.compressed:
            return 'gfx/' + asset.name + '.4bpp.lz'
        else:
            return 'gfx/' + asset.name + '.4bpp'
    elif asset.type == 'palette':
        return 'palettes/' + asset.name + '.gbapal'
    else:
        return 'assets/' + asset.name + '.bin'

def write_assets_assembly(assets: List[dict]) -> None:
    with open('/tmp/assets/assets.s', 'w') as file:
        file.write('''\t.include "asm/macros.inc"
\t.include "constants/constants.inc"

\t.section .rodata
\t.align 2

gGlobalGfxAndPalettes:: @ 085A2E80
''')
        for asset in assets:
            if 'path' in asset:
                path = Path(asset["path"])
                file.write(f'{path.name.split(".")[0]}::\n')
                file.write(f'\t.incbin "{asset["path"]}"\n')