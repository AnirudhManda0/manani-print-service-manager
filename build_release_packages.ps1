param(
    [ValidateSet("windows10", "windows7")]
    [string]$Target = "windows10",
    [switch]$SkipBuild,
    [switch]$AllowUnsupportedPython
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$distDir = Join-Path $projectRoot "dist"
$releasesDir = Join-Path $projectRoot "releases"
$buildToolsDir = Join-Path $projectRoot ".build_tools"

function Invoke-BuildStep {
    param(
        [Parameter(Mandatory = $true)]
        [string]$SpecPath
    )

    if (Test-Path $buildToolsDir) {
        if ($env:PYTHONPATH) {
            $env:PYTHONPATH = "$buildToolsDir;$env:PYTHONPATH"
        } else {
            $env:PYTHONPATH = $buildToolsDir
        }
    }

    python -m PyInstaller $SpecPath
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller build failed for $SpecPath"
    }
}

$pythonVersion = (python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')").Trim()
if ($Target -eq "windows7") {
    $message = "Windows 7 legacy builds must be created with Python 3.8 on a Windows 7 or compatible legacy build environment."
    if ($pythonVersion -ne "3.8" -and -not $AllowUnsupportedPython) {
        throw "$message Current Python is $pythonVersion."
    }
    if ($pythonVersion -ne "3.8") {
        Write-Warning "$message Current Python is $pythonVersion, so this build is for packaging checks only."
    }
}

$specName = "PrintX.spec"
$outputExe = "PrintX.exe"
$releaseSubdir = "windows10"
if ($Target -eq "windows7") {
    $specName = "PrintX_Win7.spec"
    $outputExe = "PrintX_Win7.exe"
    $releaseSubdir = "windows7"
}

$specPath = Join-Path $projectRoot $specName
$exePath = Join-Path $distDir $outputExe
$releaseDir = Join-Path $releasesDir $releaseSubdir
$zipPath = Join-Path $releaseDir ([System.IO.Path]::GetFileNameWithoutExtension($outputExe) + ".zip")

if (-not $SkipBuild) {
    Write-Host "Building $outputExe from $specName..."
    Invoke-BuildStep -SpecPath $specPath
}

if (-not (Test-Path $exePath)) {
    throw "Missing $exePath. Run build first or remove -SkipBuild."
}

New-Item -ItemType Directory -Path $releaseDir -Force | Out-Null
Copy-Item $exePath (Join-Path $releaseDir $outputExe) -Force
Copy-Item (Join-Path $projectRoot "assets\logo.png") (Join-Path $releaseDir "logo.png") -Force
Copy-Item (Join-Path $projectRoot "config\settings.json") (Join-Path $releaseDir "settings.json") -Force
Copy-Item (Join-Path $projectRoot "version.txt") (Join-Path $releaseDir "version.txt") -Force

$releaseReadme = @"
PrintX release package

Target: $Target
Executable: $outputExe

1. Edit settings.json if needed
2. Keep the executable and settings.json together
3. Start the executable
4. Enable Auto Start from Settings if this is a production system
"@

Set-Content -Path (Join-Path $releaseDir "README.txt") -Value $releaseReadme -Encoding ascii
Compress-Archive -Path (Join-Path $releaseDir "*") -DestinationPath $zipPath -Force

Write-Host "Release package ready:"
Write-Host " - $releaseDir"
Write-Host " - $zipPath"
