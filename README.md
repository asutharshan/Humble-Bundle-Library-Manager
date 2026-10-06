# Media Utility v2.1.1

Windows desktop utility for scanning supported media URLs, loading channel/playlist libraries, selecting individual items, and exporting authorised media to MP3 and/or MP4.

**Author:** Arun Sutharshan  
**Version:** 2.1.1  
**Date:** 06 October 2026  
**Licence:** Media Utility Personal & Non-Commercial License

> **Authorised Use Notice:** Use only with media you own, created, are licensed to use, or are otherwise authorised to access and download. Media Utility does not grant rights to third-party content and does not bypass DRM or technical access controls.

## What's new in v2.1

v2.1 addresses newer YouTube extraction requirements.

### YouTube JavaScript challenge support

Modern `yt-dlp` YouTube extraction can require an external JavaScript runtime.

Media Utility v2.1:

- installs/updates `yt-dlp[default]`, which includes the compatible `yt-dlp-ejs` package;
- checks for the recommended **Deno** runtime;
- attempts to install Deno automatically on Windows when it is missing;
- detects Deno when installed through PATH, WinGet, or the standard `%USERPROFILE%\.deno\bin` location;
- passes the Deno path directly to the `yt-dlp` Python API;
- displays runtime status in the GUI.

The yt-dlp project currently recommends Deno 2.3+ for YouTube JavaScript challenge solving.

### YouTube authentication / anti-bot handling

The UI now has:

- browser-cookie selector;
- **Test YouTube Auth** button;
- authentication status;
- clearer handling of the YouTube message:
  `Sign in to confirm you're not a bot`;
- guidance to choose the browser where the user is already legitimately signed into YouTube.

Media Utility never intentionally writes raw cookies or authentication tokens into its activity log.

### Detailed percentage logging

In addition to the progress bar, the activity log records progress at approximately 5% intervals:

```text
PROGRESS | MP4 | 35.0% | Speed=... | ETA=... | ID=... | title
```

Each queued job logs:

- source;
- media ID;
- title;
- duration;
- URL;
- output format;
- live percentage;
- speed;
- ETA;
- completion/failure/authentication status.

## Existing v2 features

- multiple URLs;
- YouTube video/playlist/channel scanning;
- selectable library table;
- MP3 and MP4 multi-select;
- MP3 quality selection;
- MP4 maximum-resolution selection;
- thumbnails and metadata;
- persistent duplicate detection;
- history reset;
- queue pause/resume;
- stop-after-current-file;
- browser-cookie access for legitimate authenticated content;
- Windows EXE build script.

## Channel/library workflow

Paste a YouTube channel, playlist, or supported collection URL and choose:

```text
Scan / Load Library
```

Media Utility enumerates the library without downloading the media and allows individual selection before downloading.

## Duplicate detection

History is stored locally under:

```text
%APPDATA%\MediaUtility\download_history.json
```

Duplicate keys primarily use source/extractor + media ID + requested output format.

History persists until:

```text
History → Reset Duplicate History
```

## Installation

Run:

```text
INSTALL_AND_RUN.bat
```

The installer:

1. verifies Python/pip;
2. updates pip;
3. installs/updates `yt-dlp[default]` and `imageio-ffmpeg`;
4. checks for Deno;
5. attempts to install Deno when missing;
6. checks Tkinter;
7. starts Media Utility.

A normal Python installation containing pip and Tkinter is required.

## Browser cookies

Select the browser where you are already signed into the relevant service:

- Chrome
- Edge
- Firefox
- Brave
- Opera
- Vivaldi

Then use **Test YouTube Auth** or retry the library scan.

Browser-cookie access is provided only for content the user is already authorised to access.

## Standalone EXE

Run:

```text
BUILD_EXE.bat
```

This builds:

```text
dist\MediaUtility.exe
```

Deno remains an external runtime and should also be installed on the destination Windows machine for reliable modern YouTube extraction.

## Public GitHub repository

This package includes:

- `LICENSE`
- `DISCLAIMER.md`
- `NOTICE.md`
- `SECURITY.md`
- `CONTRIBUTING.md`
- `CODE_OF_CONDUCT.md`
- `CHANGELOG.md`
- `.gitignore`
- GitHub issue templates
- pull request template
- installation/troubleshooting documentation

## Commercial/licensing position

Media Utility is source-available under the **Media Utility Personal & Non-Commercial License**.

Limited internal organisational use with content owned or properly licensed by that organisation is permitted under the licence. Commercial redistribution, paid-service use, OEM integration, or commercial exploitation of the software itself requires written permission from the copyright holder.

See `LICENSE` for the controlling terms.


## v2.1.1 UI maintenance

- Test YouTube Auth remains permanently visible after failed or successful tests.
- Authentication status is kept short; detailed errors remain in the dialog and activity log.
- Changing the cookie browser immediately refreshes the displayed browser/runtime state.
- URL input now has vertical and horizontal scrollbars.
- Channel/library results now have vertical and horizontal scrollbars.
- Activity log now also has scrollbars.
- Download Selected / Execute is positioned above the library table so it remains visible on smaller displays.
- Reduced minimum window size and compacted the footer/log area.
