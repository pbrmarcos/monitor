param([string]$Python = 'python', [switch]$SkipInstall)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $projectRoot
function Invoke-Checked { param([scriptblock]$Action) & $Action; if ($LASTEXITCODE -ne 0) { throw "Comando falhou: $Action" } }
if (-not $SkipInstall) {
    Invoke-Checked { & $Python -m pip install -c app/backend/requirements-dev.lock -e 'app/backend[dev]' }
    Invoke-Checked { npm.cmd ci }
}
Invoke-Checked { & $Python -m pytest app/backend/tests }
Invoke-Checked { npm.cmd test }
Invoke-Checked { & $Python -m PyInstaller --clean --noconfirm --onefile --name monitor-backend --hidden-import keyring.backends.Windows --collect-data tzdata --paths app/backend --distpath app/desktop/src-tauri/binaries app/backend/run_backend.py }
Invoke-Checked { & $Python scripts/desktop_smoke.py }
$targetTriple = ((rustc -vV | Select-String '^host:').ToString() -split ': ')[1].Trim()
if (-not $targetTriple) { throw 'Não foi possível identificar o target Rust.' }
Copy-Item -LiteralPath 'app/desktop/src-tauri/binaries/monitor-backend.exe' -Destination "app/desktop/src-tauri/binaries/monitor-backend-$targetTriple.exe" -Force
Invoke-Checked { npm.cmd run tauri -- build }
New-Item -ItemType Directory -Force dist | Out-Null
New-Item -ItemType Directory -Force dist/portable | Out-Null
Copy-Item -LiteralPath 'app/desktop/src-tauri/target/release/monitor.exe' -Destination dist/portable -Force
Copy-Item -LiteralPath 'app/desktop/src-tauri/binaries/monitor-backend.exe' -Destination dist/portable -Force
Copy-Item -LiteralPath 'app/desktop/src-tauri/Cargo.lock' -Destination dist/portable -Force
$config = Get-Content -LiteralPath 'app/desktop/src-tauri/tauri.conf.json' -Raw | ConvertFrom-Json
$prefix = "$($config.productName)_$($config.version)_"
# The Rust cache may retain installers from previous versions. Export only this build.
$installers = @(Get-ChildItem -LiteralPath 'app/desktop/src-tauri/target/release/bundle' -Recurse -File | Where-Object { $_.Extension -in '.exe','.msi' -and $_.Name.StartsWith($prefix) })
if ($installers.Count -ne 2) { throw "Esperados dois instaladores da versão $($config.version)." }
$installers | Copy-Item -Destination dist -Force
Write-Host 'Instaladores gerados em dist/'
