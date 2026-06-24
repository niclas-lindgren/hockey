RULES_REPORT_SCRIPT := ./scripts/rules-report.sh
INSTALL_SCRIPT := ./scripts/install.sh

.PHONY: rules-report install
rules-report:
	$(RULES_REPORT_SCRIPT)

install:
	$(INSTALL_SCRIPT)
