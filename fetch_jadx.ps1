$ErrorActionPreference = 'Stop'
$project = Split-Path -Parent $MyInvocation.MyCommand.Path
$tools = Join-Path $project 'work\tools'
$root = Join-Path $tools 'jadx-1.5.6'
$archive = Join-Path $tools 'jadx-gui-1.5.6-with-jre-win.zip'
$expectedHash = '56A870460D03D3D6F22EB0908C33E298BC7370C952A6B7FA48C22A187ECD690B'
$releaseUrl = 'https://github.com/skylot/jadx/releases/download/v1.5.6/jadx-gui-1.5.6-with-jre-win.zip'
$licensePath = Join-Path $root 'JADX-LICENSE.txt'
$licenseUrl = 'https://raw.githubusercontent.com/skylot/jadx/v1.5.6/LICENSE'

New-Item -ItemType Directory -Path $tools -Force | Out-Null
if (-not (Test-Path -LiteralPath $archive)) {
    Write-Host 'Baixando JADX 1.5.6 portátil com Java incluído (aproximadamente 99 MB)...'
    Invoke-WebRequest -Uri $releaseUrl -OutFile $archive
}
$actualHash = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash
if ($actualHash -ne $expectedHash) {
    throw "O SHA-256 do arquivo JADX não confere. Esperado: $expectedHash; recebido: $actualHash"
}

$jar = Join-Path $root 'lib\jadx-gui-1.5.6-all.jar'
$java = Join-Path $root 'jre\bin\java.exe'
if (-not (Test-Path -LiteralPath $jar) -or -not (Test-Path -LiteralPath $java)) {
    if (Test-Path -LiteralPath $root) {
        throw "A pasta portátil JADX já existe, mas está incompleta: $root"
    }
    New-Item -ItemType Directory -Path $root | Out-Null
    Expand-Archive -LiteralPath $archive -DestinationPath $root
}

if (-not (Test-Path -LiteralPath $licensePath)) {
    Invoke-WebRequest -Uri $licenseUrl -OutFile $licensePath
}
Write-Host "JADX 1.5.6 validado e pronto em: $root"
Write-Host "SHA-256: $actualHash"
