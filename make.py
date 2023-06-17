from pathlib import Path
import subprocess

# TODO os specific
PYUIC = ['venv/Scripts/python', 'venv/Scripts/pyside6-uic.exe']
PYRCC = ['venv/Scripts/python', 'venv/Scripts/pyside6-rcc.exe']
RESOURCE_DIR = Path('resources')
COMPILED_DIR = Path('tlh/ui')

def create_venv() -> None:
    pass # TODO

def compile_resources() -> None:
    for path in RESOURCE_DIR.glob('*.qrc'):
        print(f'Compile {path}...')
        target = COMPILED_DIR / (path.stem + '_rc.py')
        subprocess.check_call(PYRCC + [path, '-o', target])

def compile_ui() -> None:
    for path in RESOURCE_DIR.glob('*.ui'):
        print(f'Compile {path}...')
        target = COMPILED_DIR / ('ui_' + path.stem + '.py')
        subprocess.check_call(PYUIC + ['--from-imports', path, '-o', target])


def main() -> None:
    create_venv()
    compile_resources()
    compile_ui()
    print('done')

if __name__ == '__main__':
    main()