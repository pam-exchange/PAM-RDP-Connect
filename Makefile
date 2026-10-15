# Makefile for PAM RDP Connect
# Supports building, packaging, installing, and uninstalling on Windows

CC ?= gcc
WINDRES ?= windres
PYTHON ?= python
PYINSTALLER ?= pyinstaller
ZIP ?= zip
ISCC ?= ISCC.exe

INSTALL_DIR ?= C:\Program Files\PAM-Exchange\PAM-RDP-Connect
DIST_DIR = dist
TMP_DIR = tmp

SRC_PAM_RDP = pam-rdp/src
CFG_PAM_RDP = pam-rdp/config

SRC_PAM_CONFIG = pam-rdp-config/src

SRC_PAM_SERVICE = pam-rdp-service/src
CFG_PAM_SERVICE = pam-rdp-service/config

.PHONY: all build package install uninstall clean

all: build

build: $(DIST_DIR)/pam-rdp.exe $(DIST_DIR)/pam-rdp-config.exe $(DIST_DIR)/pam-rdp-service.exe copy-config copy-docs

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

package: build
	@if command -v $(ISCC) >/dev/null 2>&1; then \
		$(ISCC) /O$(DIST_DIR) pam-rdp-setup/pam-rdp-setup.iss; \
	fi
	@rm -f PAM-RDP-Connect.zip
	@cd $(DIST_DIR) && $(ZIP) -r ../PAM-RDP-Connect.zip *

install: build
	@echo Installing PAM RDP Connect to "$(INSTALL_DIR)"...
	@-if [ -f "$(INSTALL_DIR)/pam-rdp-service.exe" ]; then \
		"$(INSTALL_DIR)/pam-rdp-service.exe" stop 2>/dev/null || true; \
		"$(INSTALL_DIR)/pam-rdp-service.exe" remove 2>/dev/null || true; \
	fi
	@mkdir -p "$(INSTALL_DIR)"
	@cp -rf $(DIST_DIR)/* "$(INSTALL_DIR)/"
	@"$(INSTALL_DIR)/pam-rdp-service.exe" install
	@sc config pam-rdp-connect-service depend= lanmanworkstation start= delayed-auto 2>/dev/null || true
	@"$(INSTALL_DIR)/pam-rdp-service.exe" start
	@echo Installation completed successfully.

uninstall:
	@echo Uninstalling PAM RDP Connect from "$(INSTALL_DIR)"...
	@-if [ -f "$(INSTALL_DIR)/pam-rdp-service.exe" ]; then \
		"$(INSTALL_DIR)/pam-rdp-service.exe" stop 2>/dev/null || true; \
		"$(INSTALL_DIR)/pam-rdp-service.exe" remove 2>/dev/null || true; \
	fi
	@rm -rf "$(INSTALL_DIR)"
	@echo Uninstallation completed.

clean:
	@rm -rf $(DIST_DIR) $(TMP_DIR) *.spec PAM-RDP-Connect.zip
