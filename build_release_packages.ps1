param(
    [switch]$SkipBuild,
    [switch]$AllowUnsupportedPython
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$distDir = Join-Path $projectRoot "dist"
$releaseDir = Join-Path $projectRoot "release"
$serverDir = Join-Path $releaseDir "CyberCafeServer"
$clientDir = Join-Path $releaseDir "CyberCafeClient"

$serverExe = Join-Path $distDir "CyberCafeServer.exe"
$clientExe = Join-Path $distDir "CyberCafeClient.exe"

$pythonVersion = (python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')").Trim()
if ($pythonVersion -ne "3.9") {
    $message = "Current Python is $pythonVersion. Windows 7 production builds must be created with Python 3.9."
    if (-not $AllowUnsupportedPython) {
        throw "$message Re-run with -AllowUnsupportedPython only for non-Windows-7 testing builds."
    }
    Write-Warning "$message Continuing because -AllowUnsupportedPython was provided."
}

if (-not $SkipBuild) {
    Write-Host "Building server executable..."
    python -m PyInstaller (Join-Path $projectRoot "CyberCafeServer.spec")
    Write-Host "Building client executable..."
    python -m PyInstaller (Join-Path $projectRoot "CyberCafeClient.spec")
}

if (-not (Test-Path $serverExe)) {
    throw "Missing $serverExe. Run build first or remove -SkipBuild."
}
if (-not (Test-Path $clientExe)) {
    throw "Missing $clientExe. Run build first or remove -SkipBuild."
}

if (Test-Path $releaseDir) {
    Remove-Item -Recurse -Force $releaseDir
}

New-Item -ItemType Directory -Path $serverDir | Out-Null
New-Item -ItemType Directory -Path $clientDir | Out-Null
New-Item -ItemType Directory -Path (Join-Path $serverDir "config") | Out-Null
New-Item -ItemType Directory -Path (Join-Path $serverDir "database") | Out-Null
New-Item -ItemType Directory -Path (Join-Path $clientDir "config") | Out-Null
New-Item -ItemType Directory -Path (Join-Path $clientDir "database") | Out-Null

Copy-Item $serverExe (Join-Path $serverDir "CyberCafeServer.exe")
Copy-Item $clientExe (Join-Path $clientDir "CyberCafeClient.exe")
Copy-Item (Join-Path $projectRoot "config\settings.json") (Join-Path $serverDir "config\settings.json")
Copy-Item (Join-Path $projectRoot "config\settings.json") (Join-Path $clientDir "config\settings.json")
Copy-Item (Join-Path $projectRoot "database\schema.sql") (Join-Path $serverDir "database\schema.sql")
Copy-Item (Join-Path $projectRoot "database\schema.sql") (Join-Path $clientDir "database\schema.sql")
Copy-Item (Join-Path $projectRoot "version.txt") (Join-Path $serverDir "version.txt")
Copy-Item (Join-Path $projectRoot "version.txt") (Join-Path $clientDir "version.txt")

$serverQuickstart = @"
CyberCafeServer Package

1. Edit config\settings.json
2. Set mode=server and server_ip/server_port
3. Keep auto_discovery_enabled=true for easier client connection
4. Start CyberCafeServer.exe
"@

$clientQuickstart = @"
CyberCafeClient Package

1. Edit config\settings.json
2. Set mode=client
3. Keep auto_discovery_enabled=true or set central_server_url manually
4. Set unique computer_name
5. Start CyberCafeClient.exe
"@

Set-Content -Path (Join-Path $serverDir "QUICKSTART.txt") -Value $serverQuickstart -Encoding ascii
Set-Content -Path (Join-Path $clientDir "QUICKSTART.txt") -Value $clientQuickstart -Encoding ascii

$serverZip = Join-Path $releaseDir "CyberCafeServer.zip"
$clientZip = Join-Path $releaseDir "CyberCafeClient.zip"

Compress-Archive -Path (Join-Path $serverDir "*") -DestinationPath $serverZip -Force
Compress-Archive -Path (Join-Path $clientDir "*") -DestinationPath $clientZip -Force

Write-Host "Release packages created:"
Write-Host " - $serverZip"
Write-Host " - $clientZip"
