from enum import Enum, IntEnum

SHA1_USA = 'b4bd50e4131b027c334547b4524e2dbbd4227130'
SHA1_DEMO = '63fcad218f9047b6a9edbb68c98bd0dec322d7a1'
SHA1_EU = 'cff199b36ff173fb6faf152653d1bccf87c26fb7'
SHA1_JP = '6c5404a1effb17f481f352181d0f1c61a2765c5d'
SHA1_DEMO_JP = '9cdb56fa79bba13158b81925c1f3641251326412'
ROM_OFFSET = 0x08000000
ROM_SIZE =     0xffffff


# Needs to be a str enum, so it can be handled by dataclass-csv
class RomVariant(str, Enum):
    USA = 'USA'
    DEMO = 'DEMO'
    EU = 'EU'
    JP = 'JP'
    DEMO_JP = 'DEMO_JP'
    CUSTOM = 'CUSTOM'
    CUSTOM_EU = 'CUSTOM_EU'
    CUSTOM_JP = 'CUSTOM_JP'
    CUSTOM_DEMO_USA = 'CUSTOM_DEMO_USA'
    CUSTOM_DEMO_JP = 'CUSTOM_DEMO_JP'

    def __repr__(self):
        return self.name

ALL_ROM_VARIANTS = [RomVariant.USA, RomVariant.DEMO, RomVariant.EU, RomVariant.JP, RomVariant.DEMO_JP, RomVariant.CUSTOM, RomVariant.CUSTOM_EU, RomVariant.CUSTOM_JP, RomVariant.CUSTOM_DEMO_USA, RomVariant.CUSTOM_DEMO_JP]
CUSTOM_ROM_VARIANTS= [RomVariant.CUSTOM, RomVariant.CUSTOM_EU, RomVariant.CUSTOM_JP, RomVariant.CUSTOM_DEMO_USA, RomVariant.CUSTOM_DEMO_JP]