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
Invoke-Checked { & $Python -m PyInstaller --clean --noconfirm --onefile --name monitor-backend --paths app/backend --distpath app/desktop/src-tauri/binaries app/backend/run_backend.py }
Invoke-Checked { & $Python scripts/desktop_smoke.py }
$targetTriple = ((rustc -vV | Select-String '^host:').ToString() -split ': ')[1].Trim()
if (-not $targetTriple) { throw 'Não foi possível identificar o target Rust.' }
Copy-Item -LiteralPath 'app/desktop/src-tauri/binaries/monitor-backend.exe' -Destination "app/desktop/src-tauri/binaries/monitor-backend-$targetTriple.exe" -Force
Invoke-Checked { npm.cmd run tauri -- build }
New-Item -ItemType Directory -Force dist | Out-Null
Get-ChildItem -LiteralPath 'app/desktop/src-tauri/target/release/bundle' -Recurse -File | Where-Object Extension -In '.exe','.msi' | Copy-Item -Destination dist -Force
Write-Host 'Instaladores gerados em dist/'
