$ErrorActionPreference = 'Stop'
$project = Split-Path -Parent $MyInvocation.MyCommand.Path
$envDir = Join-Path $project 'work\build-env'
$fetchJadx = Join-Path $project 'fetch_jadx.ps1'
& $fetchJadx
$python = (Get-Command py -ErrorAction SilentlyContinue)
if (-not $python) { throw 'O launcher py do Python não foi encontrado.' }
& py -3.11 -m venv $envDir
$venvPython = Join-Path $envDir 'Scripts\python.exe'
& $venvPython -m pip install 'pyinstaller==6.22.3'
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$releaseRoot = Join-Path $project "distributions\CrossPlatformAppConverter-$stamp"
$suffix = 1
while (Test-Path -LiteralPath $releaseRoot) {
    $suffix++
    $releaseRoot = Join-Path $project "distributions\CrossPlatformAppConverter-$stamp-$suffix"
}
$workRoot = Join-Path $releaseRoot 'build'
$distRoot = Join-Path $releaseRoot 'dist'
$specRoot = Join-Path $releaseRoot 'spec'
New-Item -ItemType Directory -Path $releaseRoot,$workRoot,$distRoot,$specRoot -Force | Out-Null
Push-Location $project
try {
    & $venvPython -m PyInstaller --clean --windowed --onedir --name CrossPlatformAppConverter --workpath $workRoot --distpath $distRoot --specpath $specRoot run_gui.py
} finally {
    Pop-Location
}
$appDist = Join-Path $distRoot 'CrossPlatformAppConverter'
$sourceJadx = Join-Path $project 'work\tools\jadx-1.5.6'
$targetJadx = Join-Path $appDist 'tools\jadx-1.5.6'
New-Item -ItemType Directory -Path $targetJadx -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $sourceJadx 'jre') -Destination $targetJadx -Recurse
Copy-Item -LiteralPath (Join-Path $sourceJadx 'lib') -Destination $targetJadx -Recurse
Copy-Item -LiteralPath (Join-Path $sourceJadx 'JADX-LICENSE.txt') -Destination $targetJadx
Copy-Item -LiteralPath (Join-Path $project 'README.md') -Destination $appDist
Copy-Item -LiteralPath (Join-Path $project 'THIRD_PARTY_NOTICES.md') -Destination $appDist
Write-Host "Executável criado em: $(Join-Path $distRoot 'CrossPlatformAppConverter\CrossPlatformAppConverter.exe')"
Write-Host "Recuperação experimental APK com JADX: $(Join-Path $targetJadx 'lib\jadx-gui-1.5.6-all.jar')"
