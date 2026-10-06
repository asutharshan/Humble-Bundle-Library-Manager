# Troubleshooting

## YouTube: "Sign in to confirm you're not a bot"

1. Sign into YouTube normally in a supported browser.
2. In Media Utility choose that browser under **Browser cookies**.
3. Choose **Test YouTube Auth**.
4. If the test passes, retry Scan / Load Library or the download.

If one browser cannot expose usable cookies, another supported browser may work better.

Do not export or publish your raw cookies.

## YouTube: "No supported JavaScript runtime could be found"

Modern YouTube extraction can require a JavaScript runtime.

Media Utility v2.1 uses **Deno**.

Run `INSTALL_AND_RUN.bat` again. It will attempt to install Deno automatically.

Then launch Media Utility and check the runtime line. It should show a Deno version rather than:

```text
Deno: NOT FOUND
```

## EJS / challenge solver

The installer uses:

```text
yt-dlp[default]
```

which installs the matching `yt-dlp-ejs` dependency expected by yt-dlp.

Keep these packages updated together.

## No module named pip / Tkinter

Repair or reinstall the normal Windows Python distribution with:

- pip
- tcl/tk and IDLE
- Python Launcher
- Add Python to PATH

## Duplicates

History is stored at:

```text
%APPDATA%\MediaUtility\download_history.json
```

Reset it from the History tab if required.
