# CExplore Bridge
To use the CExplore Bridge plugin, click on the <kbd>Tools | Settings</kbd> menu. In the <kbd>Plugins</kbd> tab activate the plugin.

Then click on <kbd>Tools | Plugins | CExplore Bridge</kbd>. Click on <kbd>Start Server</kbd>. Copy the JavaScript code using the button and create a bookmark with it. Open [CExplore](http://cexplore.henny022.de/) and click on the bookmark (or directly copy the JavaScript code to the address bar and add `javascript:` in front of it). If everything works a message `Connected` should appear in the top bar of CExplore.

To upload a function with the `NONMATCH` or `ASM_FUNC` macros to CExplore, enter its name into the `Function name` field and press <kbd>Upload to CExplore</kbd>. The asm code and if available the nonmatching C code should appear in CExplore. 

While editing add new includes and external definitions below the `// end of existing headers` line. If the function is (almost) matching, put it back to the corresponding file by pressing the <kbd>Download to file</kbd> button and then reviewing the code.