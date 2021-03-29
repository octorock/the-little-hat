from PySide6.QtCore import QSettings, Signal

settings = QSettings('octorock', 'the-little-hat')

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
