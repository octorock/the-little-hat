from PySide6.QtCore import QByteArray


class Layout:
    def __init__(self, name: str, state: QByteArray, geometry: QByteArray, dock_state: str) -> None:
        self.name = name
        self.state = state
        self.geometry = geometry
        self.dock_state = dock_state