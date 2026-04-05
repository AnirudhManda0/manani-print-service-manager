# Installation

## Windows 10 and Above

1. Copy `releases/windows10/PrintX.exe` to the target PC.
2. Keep `settings.json` beside the executable if you use the packaged release folder.
3. Install required printer drivers in Windows.
4. Start `PrintX.exe`.
5. Open Settings and configure:
   - server IP
   - server port
   - operator ID
   - B&W price per page
   - color price per page
   - auto-start preference

## Windows 7 Legacy

Use the `windows7-legacy` branch and build in a Python 3.8 Windows 7 environment.

1. Install Python 3.8.
2. Run:

```powershell
pip install -r requirements-win7.txt
python -m PyInstaller PrintX_Win7.spec
```

3. Copy `dist/PrintX_Win7.exe` to the target machine.

Important:
- do not use the Windows 10 build on Windows 7
- this avoids the `api-ms-win-core-path-l1-1-0.dll` runtime error shown in the reported screenshot

## First-Run Folders

PrintX creates these folders automatically beside the executable when needed:

- `config/`
- `database/`
- `logs/`
- `backup/`

## Auto Start

Auto-start is configured from Settings.
When enabled, PrintX writes a registry entry under:

`HKCU\Software\Microsoft\Windows\CurrentVersion\Run`
