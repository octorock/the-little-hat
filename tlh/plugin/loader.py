from dataclasses import dataclass
import os
from importlib import import_module
from typing import Optional
from tlh import settings
from tlh.plugin.api import PluginApi
import inspect

plugin_folder = './plugins'
main_module = '__init__'

@dataclass
class Plugin:
    name: str
    description: str
    class_name: str
    pkg_name: str
    enabled: bool
    cls: any
    instance: any

    def get_settings_name(self) -> str:
        return self.pkg_name + ':' + self.class_name

plugins: list[Plugin] = []
api: PluginApi = None

def load_plugins(main_window):
    global plugins, api

    api = PluginApi(main_window)

    plugins = []
    possibleplugins = os.listdir(plugin_folder)
    for i in possibleplugins:
        if i == '__pycache__':
            continue
        location = os.path.join(plugin_folder, i)
        if not os.path.isdir(location) or not main_module + '.py' in os.listdir(location):
            print(f'{main_module}.py not found in plugin {i}')
            continue
        mod = import_module('plugins.' + i)

        clsmembers = inspect.getmembers(mod, inspect.isclass)

        found = False
        for name, cls in clsmembers:
            if name.endswith('Plugin'):
                if not hasattr(cls, 'name'):
                    print(f'Plugin class {name} is missing attribute "name"')
                    continue
                if not hasattr(cls, 'description'):
                    print(f'Plugin class {name} is missing attribute "description"')
                    continue
                
                found = True
                enabled = settings.is_plugin_enabled(i + ':' + name)
                instance = None
                plugin = Plugin(cls.name, cls.description, name, i, enabled, cls, instance)
                plugins.append(plugin)

                if enabled:
                    enable_plugin(plugin)

                break
        if not found:
            print(f'No class ending with "Plugin" found in plugin {i}')
        

    #return plugins

def enable_plugin(plugin: Plugin) -> None:
    plugin.instance = plugin.cls(api)
    plugin.enabled = True
    if (hasattr(plugin.instance, 'load')):
        plugin.instance.load()

def disable_plugin(plugin: Plugin) -> None:
    if (hasattr(plugin.instance, 'unload')):
        plugin.instance.unload()
    plugin.instance = None
    plugin.enabled = False

def get_plugins() -> list[Plugin]:
    return plugins