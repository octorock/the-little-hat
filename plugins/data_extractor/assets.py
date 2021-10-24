import json
from tlh import settings
import os

from tlh.const import RomVariant

variant_map = {
    RomVariant.USA: 'USA',
    RomVariant.JP: 'JP',
    RomVariant.EU: 'EU',
    RomVariant.DEMO: 'DEMO_USA',
    RomVariant.DEMO_JP: 'DEMO_JP',
}

class Assets:
    def __init__(self, assets: any) -> None:
        self.assets = assets

    def get_asset_at_of_after(self, addr: int, variant: RomVariant) -> any:
        return self.assets[self.get_index_at_of_after(addr, variant)]

    def get_index_at_of_after(self, addr: int, variant: RomVariant) -> any:
        variant = variant_map[variant]
        current_offset = 0
        for i in range(len(self.assets)):
            asset = self.assets[i]
            if 'offsets' in asset:
                if variant != RomVariant.USA and variant in asset['offsets']:
                    current_offset = asset['offsets'][variant]
            elif 'path' in asset: # Asset definition
                if 'variants' in asset:
                    if variant not in asset['variants']:
                        # This asset is not used in the current variant
                        continue
                start = 0
                if 'start' in asset:
                    # Apply offset to the start of the USA variant
                    start = asset['start'] + current_offset
                elif 'starts' in asset:
                    # Use start for the current variant
                    start = asset['starts'][variant]

                if addr <= start:
                    return i

    def insert_before(self, asset: any, next_asset: any) -> None:
        for i in range(len(self.assets)):
            if self.assets[i] == next_asset:
                self.assets.insert(i, asset)
                break

def read_assets() -> Assets:
    with open(os.path.join(settings.get_repo_location(), 'assets.json'), 'r') as file:
        return Assets(json.load(file))

def write_assets(assets: Assets) -> None:
    with open(os.path.join(settings.get_repo_location(), 'assets.json'), 'w') as file:
        json.dump(assets.assets, file, indent=2)

