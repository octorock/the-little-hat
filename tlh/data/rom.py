class Rom:
    def __init__(self, filename: str):
        with open(filename, 'rb') as rom:
            self.bytes = bytearray(rom.read())

    def get_bytes(self, from_index: int, to_index: int) -> bytearray:
        # TODO apply constraints here?
        return self.bytes[from_index:to_index]

    def length(self) -> int:
        return len(self.bytes)
