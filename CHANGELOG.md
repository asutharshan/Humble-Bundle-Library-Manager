# Changelog

## [2.1.5] - 2026-09-29

### Added
- Local-only Scan Existing Library.
- Local-only Repair / Update Catalogue for libraries created by earlier releases.
- Audit counts for matched, missing, unmapped, ambiguous, partial and zero-file purchases.
- Conservative recovery of stale catalogue links using existing files.
- Search across purchases, product/book titles and filenames.
- Complete, Partial, Missing locally and No files discovered catalogue filters.
- Up to four available product images per catalogue card with a built-in generic book cover fallback.
- Explicit messages on empty purchase/product pages.
- `_library/catalogue_audit.json` audit record.

### Changed
- Existing audited paths are preferred during later catalogue reconciliation.
- Local catalogue repair is separate from Humble metadata refresh and download actions.

### Safety
- Local repair does not download, move or delete ebook files.
- Ambiguous matches are reported rather than automatically linked.


## [2.1.4] - 2026-09-29

### Added
- Existing-library detection and incremental library workflow.
- Overall `[X of total] Purchase — filename` progress.
- Separate current-file progress bar with downloaded bytes, total size and percentage.
- Periodic large-file progress messages in the log.
- Persistent per-file download/checksum status.
- Catalogue reconciliation across current Humble metadata, previous catalogue and local files.

### Changed
- Previously retained checksum-mismatch files are treated as downloaded and are not automatically downloaded again.
- Catalogue main and purchase pages are rebuilt with existing local files and relative local links.
- Historical catalogue purchases no longer returned by Humble are retained.
- Main action is labelled Download New / Missing Selected.

### Fixed
- Existing/previously downloaded files being omitted from regenerated catalogue pages.
- Catalogue local links now use the reconciled actual archive path.


## [2.1.3] - 2026-09-29

### Added
- In-app Chrome/Edge/Firefox guide for copying `_simpleauth_sess`.
- Custom Humble Library Manager browser favicon.
- Credits/About footer and creator/community attribution.
- Persistent download-session metadata and Resume Previous Download control.
- Windows system-sleep prevention while a download worker is active.

### Fixed
- Catalogue export `safe() takes 1 positional argument but 2 were given`.
- Downloader and catalogue now share the same path-sanitising functions.
- File checkbox choices remain visually consistent after re-rendering.

### Notes
- Display-off and Windows lock are still allowed while downloads run.
- Normal Windows sleep behaviour is restored when the download job ends.


## [2.1.2] - 2026-09-29

### Added
- `1 of N` progress numbering in download logs/current-file status.
- Rotational retry queue for genuine transfer/filesystem failures.
- Up to five total attempts per failed file with increasing delay between rounds.
- Final run summary including verified, checksum-mismatch, skipped and failed counts.

### Changed
- Successfully transferred checksum-mismatch files are retained rather than discarded.
- Checksum mismatch logs record both expected and locally calculated hashes.
- Checksum mismatches do not enter the five-attempt retry queue.


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
