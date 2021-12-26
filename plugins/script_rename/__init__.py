import os
from tlh import settings
from tlh.plugin.api import PluginApi


class ScriptRenamePlugin:
    name = 'Script Rename'
    description = 'Renaming all the scripts'
    hidden = True

    def __init__(self, api: PluginApi) -> None:
        self.api = api

    def load(self) -> None:
        self.action_script_rename = self.api.register_menu_entry(
            'Script Rename', self.slot_script_rename)

    def unload(self) -> None:
        self.api.remove_menu_entry(self.action_script_rename)

    def slot_script_rename(self) -> None:

        # Generate csv
        if False:
            for root, dirs, files in os.walk(os.path.join(settings.get_repo_location(), 'data', 'scripts')):
                for file in files:
                    path = os.path.join(root, file)
                    comment = ''
                    with open(path, 'r') as input:
                        comment = input.readline().strip()
                    print(f'{file[:-4]},{comment},,{file[:-4]}')

        # Read csv
        if True:
            scripts = []
            with open('tmp/scripts.csv', 'r') as file:
                for line in file:
                    scripts.append(line.strip().split(','))

        # List folders
        if False:
            folders = {}
            for script in scripts:
                folder = script[2]
                if folder in folders:
                    folders[folder] += 1
                else:
                    folders[folder] = 1

            for key in folders:
                print(f'{key}: {folders[key]}')

        # Find duplicate script names
        if False:
            symbols = {}
            for script in scripts:
                symbol = script[3]
                if symbol in symbols:
                    print(f'Duplicate symbol: {symbol}')
                symbols[symbol] = True

        # Create folders
        if False:
            for script in scripts:
                folder = script[2]
                path = os.path.join(
                    settings.get_repo_location(), 'data', 'scripts', folder)
                os.makedirs(path, exist_ok=True)

        # Move script files
        if False:
            for script in scripts:
                old_path = os.path.join(
                    settings.get_repo_location(), 'data', 'scripts', script[0] + '.inc')
                new_path = os.path.join(settings.get_repo_location(
                ), 'data', 'scripts', script[2], script[3] + '.inc')

                print(old_path + ' -> ' + new_path)
                os.rename(old_path, new_path)

        # Generate replacements
        if True:
            for script in scripts:
                # print(f'{script[0]},{script[3]}')
                old_path = os.path.join(
                    'data', 'scripts', script[3] + '.inc').replace('\\', '/')
                new_path = os.path.join(
                    'data', 'scripts', script[2], script[3] + '.inc').replace('\\', '/')
                print(f'{old_path},{new_path}')
        print('done')
