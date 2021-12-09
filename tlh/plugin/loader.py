from dataclasses import dataclass
import os
from importlib import import_module, reload
from typing import List, Optional
from tlh import settings
from tlh.plugin.api import PluginApi
import inspect
import traceback
import sys

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
    mod: any

    def get_settings_name(self) -> str:
        return self.pkg_name + ':' + self.class_name

plugins: list[Plugin] = []
api: PluginApi = None

def load_plugins(main_window):
    global plugins, api

    api = PluginApi(main_window)

    plugins = []
    possibleplugins = os.listdir(plugin_folder)
     # Sort plugins by folder name. This determines the order the plugins are loaded in, the order they are displayed in the settings menu and the order of their menu entries.
    possibleplugins.sort()
    for i in possibleplugins:
        if i == '__pycache__':
            continue
        location = os.path.join(plugin_folder, i)
        if not os.path.isdir(location) or not main_module + '.py' in os.listdir(location):
            print(f'{main_module}.py not found in plugin {i}')
            continue
        try:
            mod = import_module('plugins.' + i)
        except Exception as e:
            print(f'Exception occurred during loading plugin {i}:')
            traceback.print_exc()

        initialize_plugin(i, mod, plugins)


    #return plugins

def initialize_plugin(i: str, mod: any, plugins: List[Plugin]) -> Optional[Plugin]:
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
                plugin = Plugin(cls.name, cls.description, name, i, False, cls, None, mod)
                plugins.append(plugin)

                if settings.is_plugin_enabled(i + ':' + name):
                    enable_plugin(plugin)

                break
        if not found:
            print(f'No class ending with "Plugin" found in plugin {i}')


def enable_plugin(plugin: Plugin) -> bool:
    try:
        plugin.instance = plugin.cls(api)
        if (hasattr(plugin.instance, 'load')):
            plugin.instance.load()
        plugin.enabled = True
        return True
    except Exception as e:
        print(f'Exception occurred during enabling plugin {plugin.get_settings_name()}:')
        traceback.print_exc()
        print('Plugin was disabled and has to be enabled again manually.')
        settings.set_plugin_enabled(plugin.get_settings_name(), False)
        return False


def disable_plugin(plugin: Plugin) -> None:
    try:
        if (hasattr(plugin.instance, 'unload')):
            plugin.instance.unload()
    except Exception as e:
        print(f'Exception occurred during unloading plugin {plugin.get_settings_name()}:')
        traceback.print_exc()
    plugin.instance = None
    plugin.enabled = False

def get_plugins() -> list[Plugin]:
    return plugins


def get_plugin(pkg_name: str, class_name: str) -> Optional[Plugin]:
    for plugin in plugins:
        if plugin.pkg_name == pkg_name and plugin.class_name == class_name:
            return plugin
    return None

def reload_plugins() -> None:
    global plugins
    # Disable all enabled plugins
    for plugin in plugins:
        if plugin.enabled:
            disable_plugin(plugin)


    old_modules = []

    for plugin in plugins:
        old_modules.append((plugin.pkg_name, plugin.mod))

    plugins = []

    # Reload all modules
    for (pkg_name, mod) in old_modules:
        # Reload any children of this module first
        children = []

        # TODO correctly bring the 
        for module_name in sys.modules.keys():
            if module_name != mod.__name__ and module_name.startswith(mod.__name__):
                children.append(module_name)

        try:
            for child in children:
                print(f'Reloading child {child}')
                reload(sys.modules[child])
            print(f'Reloading {mod.__name__}')
            mod = reload(mod)
            initialize_plugin(pkg_name, mod, plugins)
        except Exception as e:
            print(f'Exception occurred during reloading plugins:')
            traceback.print_exc()
