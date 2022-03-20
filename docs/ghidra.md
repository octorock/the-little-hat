# Ghidra

## Create new project
In the start window of Ghidra click the <kbd>File | New Project...</kbd> menu entry and create a new project.

Import new file `tmc.elf`.

```
Processor: ARM
Variant: v4t
Size: 32
Endian: little
Compiler: default
```
![Select Language and Compiler Specification dialog](img/language.png)

Import using the format `Executable and Linking Format (ELF)`.  
![Import dialog](img/import.png)

Now click on the elf file in the project view to update the code browser. Click Yes that you want to auto-analyze the file. Uncheck the `DWARF` analyzer and let it auto-analyze the file. (This takes a while).

## Import data types
Switch to *The Little Hat* and click on the <kbd>Tools | Settings</kbd> menu. In the Plugins tab activate the `Ghidra Bridge` plugin.

Then click on <kbd>Tools | Plugins | Export headers to Ghidra</kbd>.

Switch to Ghidra and click on
<kbd>File | Parse C Source...</kbd>.

Click on the <kbd>Clear profile</kbd> button in the top right.
In `Source files to parse` click on the <kbd>Display file chooser to select files to add</kbd> button. Navigate to the `tmp/ghidra_types` folder of *The Little Hat* and select all files and click <kbd>OK</kbd>. Do the same for all files in the `gba` subfolder.

Click on <kbd>Parse to Program</kbd>.
Click on <kbd>Continue?</kbd> in the `Use Open Archives?` dialog.

In the `Data Type Manager` dock right-click on `tmc.elf` and select <kbd>Apply Function Data Types</kbd>.

## Create bridge script
In Ghidra open the Script Manager using the menu entry <kbd>Window | Script Manager</kbd>.
Click on <kbd>Create New Script</kbd> button in the top right.
Select `Java` script type.

Copy contents of `the-little-hat/plugins/cexplore_bridge/CExploreBridge.java`.

Or directly create a symlink from the `ghidra_scripts` directory.

After starting the script, press `No` to keep it running in the background. It starts a webserver on port `10242` that can be used by the CExplore Bridge in *The Little Hat* to fetch the decompilation for a function and transfer it to CExplore.

## Apply types to global vars
Set up the CExplore Bridge in *The Little Hat* as described in [Using the CExplore Bridge plugin](cexplore_bridge.md). Start the CExplore Bridge webserver in Ghidra.

Click the <kbd>Set Ghidra global types</kbd> button in the CExplore Bridge dock.