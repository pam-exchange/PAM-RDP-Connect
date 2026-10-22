# Makefile for PAM RDP Connect

PYTHON ?= python
PYINSTALLER ?= pyinstaller
CC ?= gcc
WINDRES ?= windres
ZIP ?= zip
UNZIP ?= unzip
ISCC ?= ISCC.exe 

INSTALL_DIR ?= C:\Program Files\PAM-Exchange\PAM-RDP-Connect
DIST_DIR ?= dist
TMP_DIR ?= tmp

SRC_PAM_RDP = pam-rdp/src
CFG_PAM_RDP = pam-rdp/config

SRC_PAM_CONFIG = pam-rdp-config/src

SRC_PAM_SERVICE = pam-rdp-service/src
CFG_PAM_SERVICE = pam-rdp-service/config

.PHONY: all bump-version build-version build installer zip source-zip package install uninstall clean

all: package

bump-version:
	@rm -f $(DIST_DIR)/PAM-RDP-Connect-Install-*.exe $(DIST_DIR)/PAM-RDP-Connect-*.zip 2>/dev/null || true
	@$(PYTHON) bump_version.py

build-version:
	@VERSION_VAL=$$(cat version 2>/dev/null | tr -d '\r\n'); \
	rm -rf PAM-RDP-Connect-$$VERSION_VAL PAM-RDP-Connect-$$VERSION_VAL.zip PAM-RDP-Connect-source-$$VERSION_VAL.zip PAM-RDP-Connect-Source-$$VERSION_VAL.zip $(DIST_DIR)/PAM-RDP-Connect-Install-*.exe $(DIST_DIR)/PAM-RDP-Connect-*.zip 2>/dev/null || true
	@$(PYTHON) bump_version.py --no-increment

build: bump-version $(DIST_DIR)/pam-rdp.exe $(DIST_DIR)/pam-rdp-config.exe $(DIST_DIR)/pam-rdp-service.exe copy-config copy-docs

$(DIST_DIR)/pam-rdp.exe: $(SRC_PAM_RDP)/pam-rdp.py $(SRC_PAM_RDP)/pam-rdp-version.txt
	@mkdir -p $(DIST_DIR) $(TMP_DIR)
	if command -v $(PYINSTALLER) >/dev/null 2>&1; then \
		$(PYINSTALLER) --noconfirm --onefile --distpath $(DIST_DIR) --workpath $(TMP_DIR) --icon="$(SRC_PAM_RDP)/pam-rdp.ico" --version-file="$(SRC_PAM_RDP)/pam-rdp-version.txt" $(SRC_PAM_RDP)/pam-rdp.py; \
	elif [ ! -f $(DIST_DIR)/pam-rdp.exe ]; then \
		touch $(DIST_DIR)/pam-rdp.exe; \
	fi
	@rm -rf $(TMP_DIR) pam-rdp.spec

$(DIST_DIR)/pam-rdp-config.exe: $(SRC_PAM_CONFIG)/pam-rdp-config.py $(SRC_PAM_CONFIG)/pam-rdp-config-version.txt
	@mkdir -p $(DIST_DIR) $(TMP_DIR)
	if command -v $(PYINSTALLER) >/dev/null 2>&1; then \
		$(PYINSTALLER) --noconfirm --onefile --noconsole --distpath $(DIST_DIR) --workpath $(TMP_DIR) --icon="$(SRC_PAM_CONFIG)/pam-rdp-config.ico" --version-file="$(SRC_PAM_CONFIG)/pam-rdp-config-version.txt" $(SRC_PAM_CONFIG)/pam-rdp-config.py; \
	elif [ ! -f $(DIST_DIR)/pam-rdp-config.exe ]; then \
		touch $(DIST_DIR)/pam-rdp-config.exe; \
	fi
	@rm -rf $(TMP_DIR) pam-rdp-config.spec

$(DIST_DIR)/pam-rdp-service.exe: $(SRC_PAM_SERVICE)/pam-rdp-service.c $(SRC_PAM_SERVICE)/pam-rdp-service.rc
	@mkdir -p $(DIST_DIR) $(TMP_DIR)
	if command -v $(WINDRES) >/dev/null 2>&1 && command -v $(CC) >/dev/null 2>&1; then \
		$(WINDRES) $(SRC_PAM_SERVICE)/pam-rdp-service.rc -O coff -o $(TMP_DIR)/pam-rdp-service.res && \
		$(CC) -O2 -Wall -o $(DIST_DIR)/pam-rdp-service.exe $(SRC_PAM_SERVICE)/pam-rdp-service.c $(TMP_DIR)/pam-rdp-service.res -ladvapi32 -lpsapi; \
	elif [ ! -f $(DIST_DIR)/pam-rdp-service.exe ]; then \
		touch $(DIST_DIR)/pam-rdp-service.exe; \
	fi
	@rm -rf $(TMP_DIR)

copy-config:
	@mkdir -p $(DIST_DIR)
	@[ -d "$(CFG_PAM_RDP)" ] && cp -rf $(CFG_PAM_RDP)/* $(DIST_DIR)/ 2>/dev/null || true
	@[ -f "$(CFG_PAM_SERVICE)/pam-rdp-service.properties" ] && cp -f $(CFG_PAM_SERVICE)/pam-rdp-service.properties $(DIST_DIR)/ 2>/dev/null || true

copy-docs:
	@mkdir -p $(DIST_DIR)/Docs
	@[ -d Docs ] && cp -rf Docs/* $(DIST_DIR)/Docs/ 2>/dev/null || true
	@[ -f version ] && cp -f version $(DIST_DIR)/ 2>/dev/null || true
	@[ -f LICENSE ] && cp -f LICENSE $(DIST_DIR)/ 2>/dev/null || true

installer: build
	@VERSION_VAL=$$(cat version 2>/dev/null | tr -d '\r\n'); \
	rm -f $(DIST_DIR)/PAM-RDP-Connect-Install-*.exe 2>/dev/null || true; \
	if command -v $(ISCC) >/dev/null 2>&1; then \
		$(ISCC) /DMyAppVersion=$$VERSION_VAL /O$(DIST_DIR) pam-rdp-setup/pam-rdp-setup.iss; \
	else \
		echo "ISCC (Inno Setup) not found. Skipping installer generation."; \
	fi

zip: installer
	@VERSION_VAL=$$(cat version 2>/dev/null | tr -d '\r\n'); \
	ZIP_NAME="PAM-RDP-Connect-$$VERSION_VAL.zip"; \
	rm -f $$ZIP_NAME; \
	(cd $(DIST_DIR) && $(ZIP) -r ../$$ZIP_NAME *)

source-zip: build
	@VERSION_VAL=$$(cat version 2>/dev/null | tr -d '\r\n'); \
	SRC_ZIP_NAME="PAM-RDP-Connect-Source-$$VERSION_VAL.zip"; \
	rm -f $$SRC_ZIP_NAME; \
	ITEMS=""; \
	[ -d Docs ] && ITEMS="$$ITEMS Docs"; \
	[ -d pam-rdp ] && ITEMS="$$ITEMS pam-rdp"; \
	[ -d pam-rdp-config ] && ITEMS="$$ITEMS pam-rdp-config"; \
	[ -d pam-rdp-service ] && ITEMS="$$ITEMS pam-rdp-service"; \
	[ -d pam-rdp-setup ] && ITEMS="$$ITEMS pam-rdp-setup"; \
	[ -f LICENSE ] && ITEMS="$$ITEMS LICENSE"; \
	[ -f Makefile ] && ITEMS="$$ITEMS Makefile"; \
	[ -f README.md ] && ITEMS="$$ITEMS README.md"; \
	[ -f build.cmd ] && ITEMS="$$ITEMS build.cmd"; \
	[ -f bump_version.py ] && ITEMS="$$ITEMS bump_version.py"; \
	[ -f version ] && ITEMS="$$ITEMS version"; \
	$(ZIP) -r $$SRC_ZIP_NAME $$ITEMS 2>/dev/null || true

package: zip source-zip

install: package
	@VERSION_VAL=$$(cat version 2>/dev/null | tr -d '\r\n'); \
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
	rm -f "$(INSTALL_DIR)"/PAM-RDP-Connect-Install-*.exe; \
	if [ -f "$(INSTALL_DIR)/pam-rdp-service.exe" ]; then \
		"$(INSTALL_DIR)/pam-rdp-service.exe" install; \
		sc config PAM-RDP-Connect-service depend= lanmanworkstation start= delayed-auto 2>/dev/null || true; \
		"$(INSTALL_DIR)/pam-rdp-service.exe" start 2>/dev/null || true; \
	fi; \
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
	@rm -rf $(DIST_DIR) $(TMP_DIR) *.spec
