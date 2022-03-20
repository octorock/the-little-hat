# CExplore Bridge
To use the CExplore Bridge plugin, click on the <kbd>Tools | Settings</kbd> menu. In the <kbd>Plugins</kbd> tab activate the plugin.

Then click on <kbd>Tools | Plugins | CExplore Bridge</kbd>. Click on <kbd>Start Server</kbd>.
It starts a websocket server on port `10241` that the CExplore instance in the webbrowser can connect to for communication.

Copy the JavaScript code using the button and create a bookmark with it. Open [CExplore](https://cexplore.henny022.eu.ngrok.io/) and click on `Inject tlh`. If everything works a message `Connected` should appear in the top bar of CExplore.

To upload a function with the `NONMATCH` or `ASM_FUNC` macros to CExplore, enter its name into the `Function name` field and press <kbd>Upload to CExplore</kbd>. The asm code and if available the nonmatching C code should appear in CExplore.

While editing add new includes and external definitions below the `// end of existing headers` line. If the function is (almost) matching, put it back to the corresponding file by pressing the <kbd>Download to file</kbd> button and then reviewing the code.