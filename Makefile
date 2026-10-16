# Makefile for PAM RDP Connect
# Supports building binaries with auto-incrementing build version number,
# creating pam-rdp-connect-x.x.x.x.zip containing PAM-RDP-Connect-Install-x.x.x.x.exe,
# PAM-RDP-Connect-Source-x.x.x.x.zip containing source files, installing, and uninstalling.

CC ?= gcc
WINDRES ?= windres
PYTHON ?= python
PYINSTALLER ?= pyinstaller
ZIP ?= zip
UNZIP ?= unzip
ISCC ?= ISCC.exe 

INSTALL_DIR ?= C:\Program Files\PAM-Exchange\PAM-RDP-Connect
DIST_DIR = dist
TMP_DIR = tmp

SRC_PAM_RDP = pam-rdp/src
CFG_PAM_RDP = pam-rdp/config

SRC_PAM_CONFIG = pam-rdp-config/src

SRC_PAM_SERVICE = pam-rdp-service/src
CFG_PAM_SERVICE = pam-rdp-service/config

.PHONY: all bump-version build package zip source-zip installer install uninstall clean

all: package

bump-version:
	@rm -f $(DIST_DIR)/PAM-RDP-Connect-Install*.exe 2>/dev/null || true
	@$(PYTHON) -c "import os; v = open('version').read().strip() if os.path.exists('version') else '2.9.0'; parts = v.split('.'); parts = parts[:3] + [str(int(parts[3]) + 1)] if len(parts) >= 4 else parts[:3] + ['1'] if len(parts) == 3 else ['2', '9', '0', '1']; new_v = '.'.join(parts); open('version', 'w').write(new_v + '\n'); print(f'Build version: {new_v}'); v_tuple = tuple(int(p) for p in parts[:4]); rc_content = f'#include <windows.h>\n\nVS_VERSION_INFO VERSIONINFO\nFILEVERSION    {v_tuple[0]},{v_tuple[1]},{v_tuple[2]},{v_tuple[3]}\nPRODUCTVERSION {v_tuple[0]},{v_tuple[1]},{v_tuple[2]},{v_tuple[3]}\nFILEFLAGSMASK  0x3fL\n#ifdef _DEBUG\nFILEFLAGS      0x1L\n#else\nFILEFLAGS      0x0L\n#endif\nFILEOS         0x40004L\nFILETYPE       0x1L\nFILESUBTYPE    0x0L\nBEGIN\n    BLOCK \"StringFileInfo\"\n    BEGIN\n        BLOCK \"040904b0\"\n        BEGIN\n            VALUE \"CompanyName\",      \"PAM-Exchange\"\n            VALUE \"FileDescription\",  \"PAM-RDP-Connect Service\"\n            VALUE \"FileVersion\",      \"{new_v}\"\n            VALUE \"InternalName\",     \"pam-rdp-service\"\n            VALUE \"LegalCopyright\",   \"Copyright (c) 2024-2026 PAM-Exchange\"\n            VALUE \"OriginalFilename\", \"pam-rdp-service.exe\"\n            VALUE \"ProductName\",      \"PAM RDP Connect\"\n            VALUE \"ProductVersion\",   \"{new_v}\"\n        END\n    END\n    BLOCK \"VarFileInfo\"\n    BEGIN\n        VALUE \"Translation\", 0x0409, 1200\n    END\nEND\n'; open('pam-rdp-service/src/pam-rdp-service.rc', 'w').write(rc_content); ver_txt_1 = f'# UTF-8\nVSVersionInfo(\n  ffi=FixedFileInfo(\n    filevers={v_tuple},\n    prodvers={v_tuple},\n    mask=0x3f,\n    flags=0x0,\n    OS=0x40004,\n    fileType=0x1,\n    subtype=0x0,\n    date=(0, 0)\n  ),\n  kids=[\n    StringFileInfo(\n      [\n        StringTable(\n          \'040904B0\',\n          [\n            StringStruct(\'CompanyName\', \'PAM-Exchange\'),\n            StringStruct(\'FileDescription\', \'PAM RDP Connect Application\'),\n            StringStruct(\'FileVersion\', \'{new_v}\'),\n            StringStruct(\'InternalName\', \'pam-rdp\'),\n            StringStruct(\'LegalCopyright\', \'Copyright (c) 2024-2026 PAM-Exchange\'),\n            StringStruct(\'OriginalFilename\', \'pam-rdp.exe\'),\n            StringStruct(\'ProductName\', \'PAM RDP Connect\'),\n            StringStruct(\'ProductVersion\', \'{new_v}\')\n          ]\n        )\n      ]\n    ),\n    VarFileInfo([VarStruct(\'Translation\', [1033, 1200])])\n  ]\n)\n'; open('pam-rdp/src/pam-rdp-version.txt', 'w').write(ver_txt_1); ver_txt_2 = f'# UTF-8\nVSVersionInfo(\n  ffi=FixedFileInfo(\n    filevers={v_tuple},\n    prodvers={v_tuple},\n    mask=0x3f,\n    flags=0x0,\n    OS=0x40004,\n    fileType=0x1,\n    subtype=0x0,\n    date=(0, 0)\n  ),\n  kids=[\n    StringFileInfo(\n      [\n        StringTable(\n          \'040904B0\',\n          [\n            StringStruct(\'CompanyName\', \'PAM-Exchange\'),\n            StringStruct(\'FileDescription\', \'PAM RDP Connect Configuration GUI\'),\n            StringStruct(\'FileVersion\', \'{new_v}\'),\n            StringStruct(\'InternalName\', \'pam-rdp-config\'),\n            StringStruct(\'LegalCopyright\', \'Copyright (c) 2024-2026 PAM-Exchange\'),\n            StringStruct(\'OriginalFilename\', \'pam-rdp-config.exe\'),\n            StringStruct(\'ProductName\', \'PAM RDP Connect Configuration\'),\n            StringStruct(\'ProductVersion\', \'{new_v}\')\n          ]\n        )\n      ]\n    ),\n    VarFileInfo([VarStruct(\'Translation\', [1033, 1200])])\n  ]\n)\n'; open('pam-rdp-config/src/pam-rdp-config-version.txt', 'w').write(ver_txt_2)"

build: bump-version $(DIST_DIR)/pam-rdp.exe $(DIST_DIR)/pam-rdp-config.exe $(DIST_DIR)/pam-rdp-service.exe copy-config copy-docs

$(DIST_DIR)/pam-rdp.exe: $(SRC_PAM_RDP)/pam-rdp.py $(SRC_PAM_RDP)/pam-rdp-version.txt
	@mkdir -p $(DIST_DIR) $(TMP_DIR)
	$(PYINSTALLER) --noconfirm --onefile --distpath $(DIST_DIR) --workpath $(TMP_DIR) --icon="$(SRC_PAM_RDP)/pam-rdp.ico" --version-file="$(SRC_PAM_RDP)/pam-rdp-version.txt" $(SRC_PAM_RDP)/pam-rdp.py
	@rm -rf $(TMP_DIR) pam-rdp.spec

$(DIST_DIR)/pam-rdp-config.exe: $(SRC_PAM_CONFIG)/pam-rdp-config.py $(SRC_PAM_CONFIG)/pam-rdp-config-version.txt
	@mkdir -p $(DIST_DIR) $(TMP_DIR)
	$(PYINSTALLER) --noconfirm --onefile --noconsole --distpath $(DIST_DIR) --workpath $(TMP_DIR) --icon="$(SRC_PAM_CONFIG)/pam-rdp-config.ico" --version-file="$(SRC_PAM_CONFIG)/pam-rdp-config-version.txt" $(SRC_PAM_CONFIG)/pam-rdp-config.py
	@rm -rf $(TMP_DIR) pam-rdp-config.spec

$(DIST_DIR)/pam-rdp-service.exe: $(SRC_PAM_SERVICE)/pam-rdp-service.c $(SRC_PAM_SERVICE)/pam-rdp-service.rc
	@mkdir -p $(DIST_DIR) $(TMP_DIR)
	$(WINDRES) $(SRC_PAM_SERVICE)/pam-rdp-service.rc -O coff -o $(TMP_DIR)/pam-rdp-service.res
	$(CC) -O2 -Wall -o $(DIST_DIR)/pam-rdp-service.exe $(SRC_PAM_SERVICE)/pam-rdp-service.c $(TMP_DIR)/pam-rdp-service.res -ladvapi32 -lpsapi
	@rm -rf $(TMP_DIR)

copy-config:
	@mkdir -p $(DIST_DIR)
	@cp -rf $(CFG_PAM_RDP)/* $(DIST_DIR)/ 2>/dev/null || true
	@cp -f $(CFG_PAM_SERVICE)/pam-rdp-service.properties $(DIST_DIR)/ 2>/dev/null || true

copy-docs:
	@mkdir -p $(DIST_DIR)/Docs
	@cp -rf Docs/* $(DIST_DIR)/Docs/ 2>/dev/null || true
	@cp -f version $(DIST_DIR)/ 2>/dev/null || true
	@cp -f LICENSE $(DIST_DIR)/ 2>/dev/null || true

# Installer executable (Inno Setup)
installer: build
	@VERSION_VAL=$$(cat version | tr -d '\r\n'); \
	if command -v $(ISCC) >/dev/null 2>&1; then \
		$(ISCC) /DMyAppVersion=$$VERSION_VAL /O$(DIST_DIR) pam-rdp-setup/pam-rdp-setup.iss; \
	else \
		echo "ISCC (Inno Setup) not found. Skipping installer generation."; \
	fi

# Zip target: includes all files in dist/ including installer executable
zip: installer
	@VERSION_VAL=$$(cat version | tr -d '\r\n'); \
	ZIP_NAME="PAM-RDP-Connect-$$VERSION_VAL.zip"; \
	cd $(DIST_DIR) && $(ZIP) -r ../$$ZIP_NAME *

# Source zip target: creates PAM-RDP-Connect-Source-<version>.zip containing source directories and files
source-zip: build
	@VERSION_VAL=$$(cat version | tr -d '\r\n'); \
	SRC_ZIP_NAME="PAM-RDP-Connect-Source-$$VERSION_VAL.zip"; \
	rm -f $$SRC_ZIP_NAME; \
	$(ZIP) -r $$SRC_ZIP_NAME Docs pam-rdp pam-rdp-config pam-rdp-service pam-rdp-setup build.cmd LICENSE Makefile README.md version

package: zip source-zip

install: package
	@VERSION_VAL=$$(cat version | tr -d '\r\n'); \
	ZIP_NAME="PAM-RDP-Connect-$$VERSION_VAL.zip"; \
	echo Installing PAM RDP Connect to "$(INSTALL_DIR)"...; \
	if [ -f "$(INSTALL_DIR)/pam-rdp-service.exe" ]; then \
		"$(INSTALL_DIR)/pam-rdp-service.exe" stop 2>/dev/null || true; \
		"$(INSTALL_DIR)/pam-rdp-service.exe" remove 2>/dev/null || true; \
	fi; \
	mkdir -p "$(INSTALL_DIR)"; \
	if command -v $(UNZIP) >/dev/null 2>&1; then \
		$(UNZIP) -o $$ZIP_NAME -d "$(INSTALL_DIR)"; \
	else \
		cp -rf $(DIST_DIR)/* "$(INSTALL_DIR)/"; \
	fi; \
	rm -f "$(INSTALL_DIR)"/PAM-RDP-Connect-Install-*.exe "$(INSTALL_DIR)"/PAM-RDP-Connect-Install-*.exe; \
	"$(INSTALL_DIR)/pam-rdp-service.exe" install; \
	sc config PAM-RDP-Connect-service depend= lanmanworkstation start= delayed-auto 2>/dev/null || true; \
	"$(INSTALL_DIR)/pam-rdp-service.exe" start; \
	echo Installation completed successfully.

uninstall:
	@echo Uninstalling PAM RDP Connect from "$(INSTALL_DIR)"...
	@-if [ -f "$(INSTALL_DIR)/pam-rdp-service.exe" ]; then \
		"$(INSTALL_DIR)/pam-rdp-service.exe" stop 2>/dev/null || true; \
		"$(INSTALL_DIR)/pam-rdp-service.exe" remove 2>/dev/null || true; \
	fi
	@rm -rf "$(INSTALL_DIR)"
	@echo Uninstallation completed.

clean:
	@rm -rf $(DIST_DIR) $(TMP_DIR) *.spec PAM-RDP-Connect*.zip
