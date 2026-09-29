# Humble Library Manager

**Browse, catalogue and back up downloadable content from your own Humble library.**

**Version 2.1.3 · 29 September 2026**

Originally created by **Arun Sutharshan**  
Website: https://www.sutharshan.co.uk  
Contact: arun@sutharshan.co.uk

> An independent community open-source project. Not affiliated with or endorsed by Humble Bundle, Inc.

## What it does

Humble Library Manager provides a local browser interface for reviewing purchases and downloadable files exposed to your authenticated account.

- Cookie validation without deliberately persisting `_simpleauth_sess`.
- Purchase search and 20 / 50 / 100 pagination.
- Select all matching, current page, individual purchases or individual files.
- Supports all exposed file types. ZIP/PDF/EPUB/EXE/etc. are formats, not categories.
- Preserves purchase → product → platform → file relationships.
- Existing-file skipping, `.part` resume attempts and checksum validation where available.
- Live download progress and logs.
- Searchable offline HTML catalogue.
- Individual purchase/product pages with file type, size, status and local links.
- JSON and YAML catalogue exports for future management-system integration.

## Windows quick start

1. Install Python 3.10+.
2. Download/extract the repository.
3. Run `START_HUMBLE_MANAGER.bat`.
4. Open `http://127.0.0.1:8765` if it does not open automatically.
5. Sign into Humble normally and obtain the `_simpleauth_sess` cookie value from your browser developer tools.
6. Paste the value into **Authentication** and select **Validate & Load**.
7. Review/select purchases and files.
8. Use **Export Catalogue** to create the offline HTML/JSON/YAML catalogue.
9. Use **Download Selected** to create your local archive.

**Treat `_simpleauth_sess` like a password. Never commit or share it.**

## Archive/catalogue

```text
HumbleLibrary/
├── index.html
├── catalogue/
│   ├── library.json
│   ├── library.yml
│   ├── assets/
│   └── purchases/
├── Books/
├── Software/
├── Games & Software/
├── Audio/
├── Other/
└── _library/
```

`library.json` is the preferred machine-readable format. YAML mirrors the catalogue in a more human-readable form. A versioned schema is included for future integrations.

Generated catalogues can contain source download URLs. Keep them private unless reviewed/redacted.

## Community development

This project was started as a personal project but is intended for continued development and maintenance by the open-source community. Bug fixes, compatibility work, documentation, tests, UI improvements and new features are welcome.

See `CONTRIBUTING.md`, `MAINTAINERS.md`, `SECURITY.md` and `CODE_OF_CONDUCT.md`.

## AI-assisted development

AI-assisted development tools, including ChatGPT, have been used to support coding, documentation, review, debugging and design exploration. Human maintainers remain responsible for requirements, architectural decisions, testing and released code. See `DEVELOPMENT.md`.

## License

Released under the **MIT License**. See `LICENSE`.

## Disclaimer

This is unofficial software using interfaces that may change without notice. It does not bypass DRM or access controls and is intended only for content the user is legitimately entitled to access.

The software is provided **as-is and without warranty**. Use it at your own risk. See `DISCLAIMER.md`.


## Windows path handling

Version 2.1.3 shortens long generated archive path components using deterministic hashes. Full Humble names remain in catalogue metadata. A path creation failure is logged against that file rather than stopping the complete download job.

## Retry and checksum behaviour

Version 2.1.3 numbers final file outcomes (`1 of N`, `2 of N`, etc.). Genuine HTTP/network/filesystem failures are placed at the end of a rotational retry queue for up to five total attempts per file. Checksum mismatches are not repeatedly downloaded: the completed file is retained and clearly flagged with the expected and calculated checksum.


## v2.1.3 reliability and UI

Adds a fixed catalogue exporter using shared path utilities, an in-app cookie help guide, custom favicon, credits footer, persistent download-session metadata, Resume Previous Download, and Windows sleep prevention while an active download worker is running. Screen locking/display-off remain unaffected.
