# Genera los distribuibles de Windows en dist\ y los prueba:
#   NihongoDesk-<v>-setup.exe            instalador (sin administrador)
#   NihongoDesk-<v>-windows-portable.zip carpeta lista para usar, sin instalar
#
#   powershell -ExecutionPolicy Bypass -File packaging\windows\build_windows.ps1
#
# Requisitos (solo en el PC que compila): Python 3.10+ (python.org o «py»),
# Inno Setup 6 para el instalador (si falta, se intenta con winget/choco; sin
# él se genera solo el ZIP portable).
$ErrorActionPreference = "Stop"
$Root = Resolve-Path "$PSScriptRoot\..\.."
Set-Location $Root
$Build = "$Root\build\windows"
$Dist = "$Root\dist"
New-Item -ItemType Directory -Force $Build, $Dist | Out-Null

# --- Python y dependencias en un entorno propio de compilación
$Py = "$Build\venv\Scripts\python.exe"
if (-not (Test-Path $Py)) {
    $base = if (Get-Command py -ErrorAction SilentlyContinue) { "py" } else { "python" }
    & $base -m venv "$Build\venv"
}
& $Py -m pip install -q --upgrade pip
& $Py -m pip install -q -r requirements.txt "pyinstaller>=6.10"
$Version = (& $Py packaging\windows\make_version_info.py).Trim()
Write-Host "==> Nihongo Desk $Version"

# --- PyInstaller
Write-Host "==> PyInstaller"
& $Py -m PyInstaller packaging\nihongo_desk.spec --noconfirm --clean --distpath "$Build\pyi-dist" --workpath "$Build\pyi-work"
if ($LASTEXITCODE -ne 0) { throw "PyInstaller falló" }
$App = "$Build\pyi-dist\NihongoDesk"

# --- autoprueba del ejecutable (datos en una carpeta temporal)
function Test-Exe($exe, $report) {
    $p = Start-Process -FilePath $exe -ArgumentList "--selftest=$report" -Wait -PassThru
    Get-Content $report | Write-Host
    if ($p.ExitCode -ne 0) { throw "La autoprueba de $exe falló (código $($p.ExitCode))" }
}
Write-Host "==> Autoprueba del ejecutable"
Test-Exe "$App\NihongoDesk.exe" "$Build\selftest.txt"

# --- ZIP portable
Write-Host "==> ZIP portable"
$Portable = "$Dist\NihongoDesk-$Version-windows-portable.zip"
$Stage = "$Build\portable\NihongoDesk"
Remove-Item -Recurse -Force "$Build\portable" -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force $Stage | Out-Null
Copy-Item -Recurse "$App\*" $Stage
Copy-Item packaging\windows\LEEME-portable.txt "$Stage\LEEME.txt"
Remove-Item $Portable -ErrorAction SilentlyContinue
Compress-Archive -Path $Stage -DestinationPath $Portable

# --- Instalador (Inno Setup)
$Iscc = @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
          "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $Iscc) {
    Write-Host "==> Inno Setup no encontrado: intentando instalarlo"
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        winget install --id JRSoftware.InnoSetup -e --silent --accept-package-agreements --accept-source-agreements | Out-Null
    } elseif (Get-Command choco -ErrorAction SilentlyContinue) {
        choco install innosetup -y --no-progress | Out-Null
    }
    $Iscc = @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
              "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
}
if ($Iscc) {
    Write-Host "==> Instalador"
    & $Iscc /Q "/DAppVersion=$Version" "/DSourceDir=$App" "/DOutputDir=$Dist" packaging\windows\installer.iss
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup falló" }
} else {
    Write-Warning "Sin Inno Setup: solo se ha generado el ZIP portable. Instálalo desde https://jrsoftware.org/isdl.php"
}
Get-ChildItem $Dist | Format-Table Name, @{n="MB"; e={[math]::Round($_.Length / 1MB, 1)}}
