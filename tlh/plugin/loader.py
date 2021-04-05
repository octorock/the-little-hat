import os
from importlib import import_module
from tlh.plugin.api import PluginApi

plugin_folder = './plugins'
main_module = '__init__'

def load_plugins(main_window):

    api = PluginApi(main_window)

    #plugins = []
    possibleplugins = os.listdir(plugin_folder)
    for i in possibleplugins:
        if i == '__pycache__':
            continue
        location = os.path.join(plugin_folder, i)
        if not os.path.isdir(location) or not main_module + '.py' in os.listdir(location):
            print(f'{main_module}.py not found in plugin {i}')
            continue
        mod = import_module('plugins.' + i)
        main = getattr(mod, 'main', None)
        if main is None:
            print(f'main function not found in plugin {i}')
            continue
        #plugins.append({'name': i, 'mod': mod, 'main': main})
        main(api)

    #return plugins