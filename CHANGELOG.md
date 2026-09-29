# Changelog

## [2.1.1] - 2026-09-29

### Fixed
- Windows `WinError 206` failures from long nested archive paths.
- Long path components now use deterministic shortening with hashes.
- Individual path creation errors no longer terminate the whole download worker.
- Catalogue local paths follow the shortened archive naming convention.


## [2.1.0] - 2026-09-29

### Added
- Offline searchable HTML library catalogue.
- Individual purchase/product detail pages.
- File type, platform, size, status and local links.
- JSON and YAML machine-readable catalogue exports.
- Versioned catalogue schema metadata.
- Community/open-source repository documentation.
- Maintainer, security, contribution and development guidance.
- AI-assisted development disclosure.

## [2.0.0] - 2026-09-29

### Added
- Local browser UI.
- Cookie validation and purchase loading.
- Search and 20/50/100 pagination.
- Purchase/product/file selection.
- Download progress, logging, resume and checksum support.
