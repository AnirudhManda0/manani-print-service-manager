# Deployment

## Branch Strategy

- `main`
  Windows 10 and above production lane
- `windows7-legacy`
  Windows 7 legacy lane

## Windows 10 Release Build

```powershell
pip install -r requirements.txt
python -m PyInstaller PrintX.spec
powershell -ExecutionPolicy Bypass -File .\build_release_packages.ps1 -Target windows10
```

Output:

- `dist/PrintX.exe`
- `releases/windows10/PrintX.exe`

## Windows 7 Legacy Release Build

Build only inside a Python 3.8 Windows 7 or legacy-compatible VM environment.

```powershell
pip install -r requirements-win7.txt
python -m PyInstaller PrintX_Win7.spec
powershell -ExecutionPolicy Bypass -File .\build_release_packages.ps1 -Target windows7
```

Output:

- `dist/PrintX_Win7.exe`
- `releases/windows7/PrintX_Win7.exe`

## Shop Deployment Pattern

### Admin PC

- mode: `server` or `single`
- stores SQLite database
- runs dashboard and reports
- can also monitor local prints

### Client PC

- mode: `client`
- monitors installed printers
- sends print transactions to the central server

## Backup Strategy

- PrintX creates daily backups under `backup/`
- keep periodic external backups of the `database/` folder
- update executables without deleting `database/` or `config/`
