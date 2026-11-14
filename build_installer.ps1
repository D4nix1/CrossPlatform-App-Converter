$ErrorActionPreference = 'Stop'
$project = Split-Path -Parent $MyInvocation.MyCommand.Path
$nsisVersion = '3.13'
$nsisSha256 = 'ba63dffc4410ee89193e1cb5a41989991bd77c61068da17e3156d136b7b0b3d8'
$nsisArchive = Join-Path $project "work\tool-downloads\nsis-$nsisVersion.zip"
$nsisRoot = Join-Path $project "work\tools\nsis-$nsisVersion\nsis-$nsisVersion"
$compiler = Join-Path $nsisRoot 'makensis.exe'

if (-not (Test-Path -LiteralPath $compiler)) {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $nsisArchive) | Out-Null
    Invoke-WebRequest -Uri "https://github.com/tauri-apps/binary-releases/releases/download/nsis-$nsisVersion/nsis-$nsisVersion.zip" -OutFile $nsisArchive
    $actualHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $nsisArchive).Hash.ToLowerInvariant()
    if ($actualHash -ne $nsisSha256) { throw "Checksum NSIS inválido: $actualHash" }
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $nsisRoot) | Out-Null
    Expand-Archive -LiteralPath $nsisArchive -DestinationPath (Split-Path -Parent $nsisRoot) -Force
}

& (Join-Path $project 'build_windows.ps1')
$app = Get-ChildItem (Join-Path $project 'distributions') -Directory |
    Sort-Object LastWriteTime -Descending |
    ForEach-Object { Join-Path $_.FullName 'dist\CrossPlatformAppConverter' } |
    Where-Object { Test-Path -LiteralPath (Join-Path $_ 'CrossPlatformAppConverter.exe') } |
    Select-Object -First 1
if (-not $app) { throw 'A pasta compilada do aplicativo não foi encontrada.' }

$outputDirectory = Join-Path $project 'work\installer-release'
New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
$manifest = Join-Path $outputDirectory 'install-manifest.txt'
$uninstallList = Join-Path $outputDirectory 'uninstall-files.nsh'
$appRoot = (Resolve-Path -LiteralPath $app).Path.TrimEnd('\')
$entries = Get-ChildItem -LiteralPath $appRoot -Force -Recurse | Sort-Object FullName
$manifestLines = foreach ($entry in $entries) {
    $relative = $entry.FullName.Substring($appRoot.Length).TrimStart('\').Replace('/', '\')
    if ($entry.PSIsContainer) { "[Pasta] $relative\" } else { "[Arquivo] $relative" }
}
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[IO.File]::WriteAllLines($manifest, [string[]]$manifestLines, $utf8NoBom)
$fileDeletes = foreach ($entry in ($entries | Where-Object { -not $_.PSIsContainer } | Sort-Object { $_.FullName.Length } -Descending)) {
    $relative = $entry.FullName.Substring($appRoot.Length).TrimStart('\').Replace('/', '\').Replace('$', '$$').Replace('"', '$"')
    "  Delete `"`$INSTDIR\$relative`""
}
$directoryDeletes = foreach ($entry in ($entries | Where-Object { $_.PSIsContainer } | Sort-Object { $_.FullName.Length } -Descending)) {
    $relative = $entry.FullName.Substring($appRoot.Length).TrimStart('\').Replace('/', '\').Replace('$', '$$').Replace('"', '$"')
    "  RMDir `"`$INSTDIR\$relative`""
}
Set-Content -LiteralPath $uninstallList -Value (@($fileDeletes) + @($directoryDeletes)) -Encoding ascii

$installer = Join-Path $outputDirectory 'CrossPlatformAppConverter-0.15.0-Windows-Setup.exe'
$script = Join-Path $project 'installer\setup.nsi'
& $compiler "/DAPP_DIR=$app" "/DMANIFEST_FILE=$manifest" "/DUNINSTALL_LIST=$uninstallList" "/DOUTPUT_FILE=$installer" $script
if ($LASTEXITCODE -ne 0) { throw "makensis falhou com código $LASTEXITCODE" }
Write-Host "Instalador criado: $installer"
Write-Host "Itens exibidos na tela: $($entries.Count)"
