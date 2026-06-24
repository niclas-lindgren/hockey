# RVV Miniputt — build helpers
#
# Usage:
#   make build-mac       Build macOS .dmg (run on macOS)
#   make build-windows   Build Windows .exe (run on Windows with PowerShell)
#   make build-linux     Build Linux .AppImage (run on Linux)
#   make release         Push a version tag to trigger CI build
#   make desktop-start   Start the desktop app in dev mode
#   make desktop-clean   Clean desktop app build artifacts

.PHONY: help build-mac build-windows build-linux release desktop-start desktop-clean

help:
	@echo "RVV Miniputt build targets:"
	@echo "  make build-mac       Build macOS .dmg          (requires macOS)"
	@echo "  make build-windows   Build Windows .exe        (requires Windows + PowerShell)"
	@echo "  make build-linux     Build Linux .AppImage     (requires Linux)"
	@echo "  make release TAG=v0.2.0  Tag and push for CI"
	@echo "  make desktop-start   Start desktop app in dev mode"
	@echo "  make desktop-clean   Clean desktop build artifacts"

build-mac:
	scripts/package-desktop-backend.sh
	cd apps/desktop && npm install && npm run dist
	@echo "✅ macOS build done — see apps/desktop/dist/"

build-windows:
	powershell -ExecutionPolicy Bypass -File scripts/package-desktop-backend.ps1 && \
	cd apps/desktop && npm install && npm run dist
	@echo "✅ Windows build done — see apps/desktop/dist/"

build-linux:
	scripts/package-desktop-backend.sh
	cd apps/desktop && npm install && npm run dist
	@echo "✅ Linux build done — see apps/desktop/dist/"

release:
	@if [ -z "$(TAG)" ]; then echo "Usage: make release TAG=v0.2.0"; exit 1; fi
	git tag $(TAG)
	git push origin $(TAG)
	@echo "✅ Pushed $(TAG) — GitHub Actions will build and release"

desktop-start:
	cd apps/desktop && npm start

desktop-clean:
	cd apps/desktop && npm run cleanup
	rm -rf dist/desktop-backend build/desktop-backend
	@echo "✅ Cleaned build artifacts"
