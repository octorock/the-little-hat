# Create Plugin

## Set up a new plugin
A simple example plugin is available at [plugins/test/](../plugins/test/__init__.py).

To create a plugin, create a new folder with a unique name in the `plugins` folder.
In the new folder create a `__init__.py` file which contains the main entry point for the plugin.

The name of the main class of the plugin needs to end in `Plugin` and have a constructor that takes a `tlh.plugin.api.PluginApi` which is an easy way for plugins to interact with the rest of the program. Optionally it can also have methods `load` and `unload` which are called when the plugin is loaded and unloaded.

The barebones plugin should now look like this:
```py
from tlh.plugin.api import PluginApi

class MyFirstPlugin:
    name = 'My first plugin'
    description = 'This is going to be the plugin to rule them all'

    def __init__(self, api: PluginApi) -> None:
        self.api = api

    def load(self) -> None:
        pass

    def unload(self) -> None:
        pass
```

## Add a menu item
Create a method and then use `register_menu_entry` on the `PluginApi` to register a menu entry in the `Tools`->`Plugins` menu:

```py
    def do_something_cool(self) -> None:
        print('Called')

    def load(self) -> None:
        self.menu_entry = self.api.register_menu_entry('Something cool', self.do_something_cool)
```

Don't forget to remove the menu entry when the plugin is unloaded:
```py
    def unload(self) -> None:
        self.api.remove_menu_entry(self.menu_entry)
```