from enum import Enum, IntEnum

SHA1_USA = 'b4bd50e4131b027c334547b4524e2dbbd4227130'
SHA1_DEMO = '63fcad218f9047b6a9edbb68c98bd0dec322d7a1'
SHA1_EU = 'cff199b36ff173fb6faf152653d1bccf87c26fb7'
SHA1_JP = '6c5404a1effb17f481f352181d0f1c61a2765c5d'
ROM_OFFSET = 0x08000000
ROM_SIZE =     0xffffff


# Needs to be a str enum, so it can be handled by dataclass-csv
class RomVariant(str, Enum):
    USA = 'USA'
    DEMO = 'DEMO'
    EU = 'EU'
    JP = 'JP'
    CUSTOM = 'CUSTOM'

    def __repr__(self):
        return self.name