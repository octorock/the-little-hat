from PySide6.QtCore import QSettings, Signal
from getpass import getuser
settings = QSettings('octorock', 'the-little-hat')


# General
def get_username():
    return settings.value('username', getuser())

def set_username(username):
    settings.setValue('username', username)

def get_repo_location():
    return settings.value('repo_location', '../tmc')

def set_repo_location(repo):
    settings.setValue('repo_location', repo)

def get_build_command():
    return settings.value('build_command', 'make -j8')

def set_build_command(command):
    settings.setValue('build_command', command)

def get_tidy_command():
    return settings.value('tidy_command', 'make tidy')

def set_tidy_command(command):
    settings.setValue('tidy_command', command)

# ROMs
def get_rom_usa():
    return settings.value('rom_usa')

def set_rom_usa(rom):
    settings.setValue('rom_usa', rom)

def get_rom_demo():
    return settings.value('rom_demo')

def set_rom_demo(rom):
    settings.setValue('rom_demo', rom)

def get_rom_eu():
    return settings.value('rom_eu')

def set_rom_eu(rom):
    settings.setValue('rom_eu', rom)

def get_rom_jp():
    return settings.value('rom_jp')

def set_rom_jp(rom):
    settings.setValue('rom_jp', rom)

# Layouts
def get_window_state():
    return settings.value('windowState')

def set_window_state(windowState):
    settings.setValue('windowState', windowState)

def get_geometry():
    return settings.value('geometry')

def set_geometry(geometry):
    settings.setValue('geometry', geometry)

class Layout:
    name = ''
    windowState = None


def get_layouts() -> list[Layout]:
    layouts = []
    size = settings.beginReadArray('layouts')
    for i in range(size):
        settings.setArrayIndex(i)
        layout = Layout()
        layout.name = settings.value('name')
        layout.windowState = settings.value('windowState')
        layouts.append(layout)
    settings.endArray()
    # layouts = settings.value('layouts', [])
    # if not isinstance(layouts, list): # https://bugreports.qt.io/browse/PYSIDE-1010?focusedCommentId=462175&page=com.atlassian.jira.plugin.system.issuetabpanels%3Acomment-tabpanel#comment-462175
    #     layouts = [layouts]
    return layouts 

def set_layouts(layouts: list[Layout]):
    settings.beginWriteArray('layouts')
    for i in range(len(layouts)):
        settings.setArrayIndex(i)
        settings.setValue('name', layouts[i].name)
        settings.setValue('windowState', layouts[i].windowState)
    settings.endArray()
