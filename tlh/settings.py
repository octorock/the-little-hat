from PySide6.QtCore import QSettings


class Settings:
    def __init__(self):
        self.settings = QSettings('octorock', 'the-little-hat')

    def get_window_state(self):
        return self.settings.value('windowState')

    def set_window_state(self, windowState):
        self.settings.setValue('windowState', windowState)

    def get_geometry(self):
        return self.settings.value('geometry')

    def set_geometry(self, geometry):
        self.settings.setValue('geometry', geometry)
