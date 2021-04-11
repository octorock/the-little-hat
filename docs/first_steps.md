# First Steps

## Setting up
After cloning the repository and getting the program to run, the first step is to adapt the settings. Click on the <kbd>Tools | Settings</kbd> menu.

In the <kbd>General</kbd> tab enter your username and select the location of your tmc repository.

In the <kbd>ROMs</kbd> tab select the locations to the roms you have available. The SHA1 of the roms will be checked.

## Viewing hex

Close the settings and use <kbd>Tools | Hex Viewer | ...</kbd> to open the hex viewers for the roms.

If you have the `tmc.map` file built, you can load the symbols for the USA rom using the <kbd>Tools | Load Symbols</kbd> menu entry.

You can scroll around the file using the scroll bar or the mouse wheel.

The blue square marks the cursor. You can move it by clicking or <kbd>&uparrow;</kbd> <kbd>&downarrow;</kbd> <kbd>&leftarrow;</kbd> <kbd>&rightarrow;</kbd>. To select more than one byte, use click and drag or press <kbd>Shift</kbd> with <kbd>&leftarrow;</kbd> or <kbd>&rightarrow;</kbd>.

To jump to a specific address in the file, press the <kbd>goto</kbd> button or use the <kbd>Ctrl + g</kbd> keyboard shortcut.

## Comparing
To compare two files, the <kbd>link</kbd> button on top needs to be activated for both files.

Bytes that differ in the linked files will be shown with a red background. The files will be layed out according to the _constraints_ between them. A _constraint_ defines that a certain address in one rom should be linked to a certain address in another rom and that both should be displayed at the same position when the hex viewers are linked. To achieve empty space in one rom is introduced before the _constraint_ address to move the linked addresses to the same position.

## Saving layouts
When you exit the program the layout of your viewers should be saved and restored when you start the program again. Using the <kbd>Layouts | Save Layout...</kbd> menu you can also save the current layout and give it a name. You can then quickly change to this layout using the <kbd>Layouts | ...</kbd> menu.

To rename, reorder or delete layouts, use the <kbd>Layouts</kbd> tab in the settings dialog.