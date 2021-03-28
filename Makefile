# https://mplicka.cz/en/blog/compiling-ui-and-resource-files-with-pyqt
# Directory with ui and resource files
RESOURCE_DIR = resources
 
# Directory for compiled resources
COMPILED_DIR = tlh/ui
 
# UI files to compile
UI_FILES =  $(notdir $(wildcard $(RESOURCE_DIR)/*.ui))
# Qt resource files to compile
RESOURCES = $(notdir $(wildcard $(RESOURCE_DIR)/*.qrc))

ifeq ($(OS),Windows_NT)
	PYUIC = python venv/Scripts/pyside6-uic.exe
	PYRCC = python venv/Scripts/pyside6-rcc.exe
else
	PYUIC = python venv/bin/pyside6-uic
	PYRCC = python venv/bin/pyside6-rcc
endif
 
 
COMPILED_UI = $(UI_FILES:%.ui=$(COMPILED_DIR)/ui_%.py)
COMPILED_RESOURCES = $(RESOURCES:%.qrc=$(COMPILED_DIR)/%_rc.py)
 
all: init resources ui 
 
resources: $(COMPILED_RESOURCES) 
 
ui: $(COMPILED_UI)
 
$(COMPILED_DIR)/ui_%.py: $(RESOURCE_DIR)/%.ui
	$(PYUIC) --from-imports $< -o $@
 
$(COMPILED_DIR)/%_rc.py: $(RESOURCE_DIR)/%.qrc
	$(PYRCC) $< -o $@
 
clean:
	tidy
	rm -rf venv

tidy:
	$(RM) $(COMPILED_UI) $(COMPILED_RESOURCES) $(COMPILED_UI:.py=.pyc) $(COMPILED_RESOURCES:.py=.pyc)

# https://stackoverflow.com/a/46188210
init: venv/touchfile

venv/touchfile: requirements.txt
	test -d venv || python -m venv venv
ifeq ($(OS),Windows_NT)
	venv/Scripts/activate.bat; pip install -Ur requirements.txt
else
	. venv/bin/activate; pip install -Ur requirements.txt
endif
	touch venv/touchfile

run: all
ifeq ($(OS),Windows_NT)
	venv/Scripts/activate.bat; python main.py
else
	. venv/bin/activate; python main.py
endif
.PHONY: init clean tidy run