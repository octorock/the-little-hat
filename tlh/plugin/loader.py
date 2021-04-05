import os
from importlib import import_module
from tlh.plugin.api import PluginApi
import inspect

plugin_folder = './plugins'
main_module = '__init__'

plugins = []

def load_plugins(main_window):
    global plugins

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
                instance = cls(api)
                found = True
                plugins.append({
                    'name': i,
                    'instance':  instance
                })
                break
        if not found:
            print(f'No class ending with "Plugin" found in plugin {i}')
        

    #return plugins