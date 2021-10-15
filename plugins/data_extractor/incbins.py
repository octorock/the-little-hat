from tlh.settings import get_repo_location
from tlh.plugin.api import PluginApi
import os

def export_incbins(api: PluginApi) -> None:
    for (root, dirs, files) in os.walk(os.path.join(get_repo_location(), 'data')):
        for file in files:
            filepath = os.path.join(root, file)
            parse_file(filepath)


def parse_file(filepath: str) -> None:
    with open(filepath, 'r') as file:
        for line in file:
            pass
            
