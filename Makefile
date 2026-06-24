RULES_REPORT_SCRIPT := ./scripts/rules-report.sh
INSTALL_SCRIPT := ./scripts/install.sh
DESKTOP_PACKAGE_SCRIPT := ./scripts/package-desktop-local.sh
DESKTOP_DIR := apps/desktop

.PHONY: rules-report install desktop-package desktop-start desktop-clean
rules-report:
	$(RULES_REPORT_SCRIPT)

install:
	$(INSTALL_SCRIPT)

desktop-package:
	$(DESKTOP_PACKAGE_SCRIPT)

desktop-start:
	cd $(DESKTOP_DIR) && npm start

desktop-clean:
	cd $(DESKTOP_DIR) && npm run cleanup
