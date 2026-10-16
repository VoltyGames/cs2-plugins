---
name: build-local
description: Build the CS2 plugins on Windows, run their tests, and install them into the local CS2 server. Use for "build", "compile", "does it compile", "rebuild", "run the tests", or "deploy to my local server". Run it before calling any C++ change verified.
---

# Build locally

## Compile and test

The Bash tool has no MSVC. Use the PowerShell tool and load the dev shell in the same call:

```powershell
$env:PATH = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer;$env:PATH"
& "$(vswhere -latest -property installationPath)\Common7\Tools\Launch-VsDevShell.ps1" -Arch amd64 -HostArch amd64 -SkipAutomaticLocation | Out-Null
uv run poe test          # compiles, then CTest; -R <regex> narrows. `poe build` only compiles
```

Output: `build/windows-msvc-release/plugins/<name>/windows-x86_64/<name>.dll`. `windows-msvc-debug`
does not link (the prebuilt protobuf is Release). Linux builds only in the CI container; see
`deploy-test`. `uv run poe lint` runs ruff, the source conventions, the Panorama and schema checks.

## Against the voltmod checkout

`conan.lock` pins a released voltmod. To build against `voltmod/`, register it once (check with
`uv run conan editable list`):

```powershell
uv run conan editable add voltmod   # poe build/test now compile the checkout first
uv run poe build --relock           # before committing, from the repo root
```

`--relock` exports the checkout, pins it in `conan.lock`, drops the editable and fails if the build
did not use it. Commit `conan.lock` with the change; CI resolves it only after a voltmod release
(`release` skill). The framework's own tests: `uv run poe test` inside `voltmod`.

## Install into the local server

```powershell
uv run poe run <plugin>        # build, install, launch
uv run poe install [plugin]    # copy only; no name copies every plugin and the host
uv run poe panorama            # compile the Panorama screens into your own client
```

Install seeds each file under `configs/` once and keeps later edits. Stop `cs2.exe` first, or the
copy fails with `WinError 32`. A plugin with a custom UI shows nothing until `poe panorama` has run
(needs CS2 Workshop Tools). Confirm the load with `volt list` (`rcon-debug`).

## Failures

- `CreateProcess failed: The system cannot find the file specified`: Strawberry was removed from
  `PATH`; ccache lives in `C:\Strawberry\c\bin`.
- `Access is denied` on `voltmod\.venv\Scripts\voltmod.exe`: a hung build holds the venv. Stop
  `Get-Process | ? Path -like "*voltmod\.venv*"`.
- `--relock` says the build tree is not configured against the package: delete
  `build/windows-msvc-release` and rerun.
- SDK binaries missing from the Conan cache: `uv run poe release build sdk` inside `voltmod`.
- Profiles or remote missing: `uv run poe bootstrap`.
- An include compiles here and fails on Linux CI: fix its case; s2sdk's headers are lower case
  (`color.h`, `keyvalues.h`, `commandbuffer.h`).

## Report

Preset, whether voltmod was relocked, the CTest result, the output path, and anything skipped.
