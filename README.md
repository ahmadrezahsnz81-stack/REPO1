# DJAR RVC Studio

Portable Windows desktop controller for the local RVC API.

## Current build

- Native Windows GUI (Tkinter)
- Local API connection: `http://127.0.0.1:7897`
- Voice/Speaker ID
- Audio file selection
- F0 method: RMVPE, CREPE, Harvest, PM
- Pitch/Transpose
- Index/Feature ratio
- Protect
- Median filter
- Resample rate
- Volume envelope mix
- Connection test
- Conversion output

## Portable build

GitHub Actions automatically creates `DJAR-RVC-Studio-Portable.zip` on pushes to `main` and on manual workflow runs.

Extract the ZIP on Windows and run `DJAR RVC Studio.exe`.

RVC itself remains local on the Windows machine. The desktop app calls the RVC API documented for port `7897`.
