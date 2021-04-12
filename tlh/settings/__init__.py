from tlh.common.ui.layout import Layout
from tlh.const import RomVariant
from PySide6.QtCore import QSettings, Signal
from getpass import getuser
import multiprocessing
from typing import Optional
settings = QSettings('octorock', 'the-little-hat')

# TODO introduce caching of settings values

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
    command = settings.value('build_command', '__default__')
    if command == '__default__':
        # Build command using cpu count
        command = 'make -j' + str(multiprocessing.cpu_count())
    return command


def set_build_command(command):
    settings.setValue('build_command', command)


def get_tidy_command():
    return settings.value('tidy_command', 'make tidy')


def set_tidy_command(command):
    settings.setValue('tidy_command', command)

def get_default_selection_size() -> int:
    return int(settings.value('default_selection_size', 1))

def set_default_selection_size(size: int) -> None:
    settings.setValue('default_selection_size', size)

def is_always_load_symbols() -> bool:
    return str(settings.value('always_load_symbols', False)).lower() == 'true'

def set_always_load_symbols(load_symbols: bool) -> None:
    settings.setValue('always_load_symbols', load_symbols)

def is_highlight_8_bytes() -> bool:
    return str(settings.value('highlight_8_bytes', False)).lower() == 'true'

def set_highlight_8_bytes(highlight: bool) -> None:
    settings.setValue('highlight_8_bytes', highlight)

def get_bytes_per_line() -> int:
    return int(settings.value('bytes_per_line', 16))

def set_bytes_per_line(bytes_per_line: int) -> None:
    settings.setValue('bytes_per_line', bytes_per_line)


# ROMs

def get_rom(variant: RomVariant) -> Optional[str]:
    if variant == RomVariant.USA:
        return get_rom_usa()
    elif variant == RomVariant.DEMO:
        return get_rom_demo()
    elif variant == RomVariant.EU:
        return get_rom_eu()
    elif variant == RomVariant.JP:
        return get_rom_jp()
    else:
        raise RuntimeError(f'Unknown rom variant {variant}')


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


def get_session_layout() -> Layout:
    settings.beginGroup('session_layout')
    layout = Layout(settings.value('name', ''), settings.value(
        'state', None), settings.value('geometry', None), settings.value('dock_state', ''))
    settings.endGroup()
    return layout


def set_session_layout(layout: Layout) -> None:
    settings.beginGroup('session_layout')
    settings.setValue('name', layout.name)
    settings.setValue('state', layout.state)
    settings.setValue('geometry', layout.geometry)
    settings.setValue('dock_state', layout.dock_state)
    settings.endGroup()


def get_layouts() -> list[Layout]:
    layouts = []
    size = settings.beginReadArray('layouts')
    for i in range(size):
        settings.setArrayIndex(i)
        layout = Layout(settings.value('name'), settings.value(
            'state'), settings.value('geometry'), settings.value('dock_state'))
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
        settings.setValue('state', layouts[i].state)
        settings.setValue('geometry', layouts[i].geometry)
        settings.setValue('dock_state', layouts[i].dock_state)
    settings.endArray()


def is_plugin_enabled(name: str) -> bool:
    settings.beginGroup('plugins')
    enabled = str(settings.value(name, False)).lower() == 'true'
    settings.endGroup()
    return enabled

def set_plugin_enabled(name: str, enabled: bool) -> None:
    settings.beginGroup('plugins')
    settings.setValue(name, enabled)
    settings.endGroup()

