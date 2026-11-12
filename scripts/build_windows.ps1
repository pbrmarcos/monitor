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
Invoke-Checked { & 'app/desktop/src-tauri/binaries/monitor-backend.exe' --browser-smoke }
Invoke-Checked { & $Python scripts/reminder_sidecar_smoke.py }
$targetTriple = ((rustc -vV | Select-String '^host:').ToString() -split ': ')[1].Trim()
if (-not $targetTriple) { throw 'Não foi possível identificar o target Rust.' }
Copy-Item -LiteralPath 'app/desktop/src-tauri/binaries/monitor-backend.exe' -Destination "app/desktop/src-tauri/binaries/monitor-backend-$targetTriple.exe" -Force
# Os pacotes de atualização precisam da chave privada (segredo TAURI_SIGNING_PRIVATE_KEY).
# Sem ela o build continua, só não gera as assinaturas nem o latest.json.
if ($env:TAURI_SIGNING_PRIVATE_KEY) {
    Invoke-Checked { npm.cmd run tauri -- build }
} else {
    Write-Warning 'TAURI_SIGNING_PRIVATE_KEY ausente: instaladores sem assinatura de atualização.'
    $override = Join-Path ([IO.Path]::GetTempPath()) 'monitor-no-updater.json'
    Set-Content -LiteralPath $override -Value '{"bundle":{"createUpdaterArtifacts":false}}' -Encoding ascii
    Invoke-Checked { npm.cmd run tauri -- build --config $override }
}
New-Item -ItemType Directory -Force dist | Out-Null
New-Item -ItemType Directory -Force dist/portable | Out-Null
Copy-Item -LiteralPath 'app/desktop/src-tauri/target/release/monitor.exe' -Destination dist/portable -Force
Copy-Item -LiteralPath 'app/desktop/src-tauri/binaries/monitor-backend.exe' -Destination dist/portable -Force
Copy-Item -LiteralPath 'app/desktop/src-tauri/Cargo.lock' -Destination dist/portable -Force
Invoke-Checked { & $Python scripts/collect_browser_licenses.py }
$config = Get-Content -LiteralPath 'app/desktop/src-tauri/tauri.conf.json' -Raw | ConvertFrom-Json
$prefix = "$($config.productName)_$($config.version)_"
# The Rust cache may retain installers from previous versions. Export only this build.
$installers = @(Get-ChildItem -LiteralPath 'app/desktop/src-tauri/target/release/bundle' -Recurse -File | Where-Object { $_.Extension -in '.exe','.msi' -and $_.Name.StartsWith($prefix) })
if ($installers.Count -ne 2) { throw "Esperados dois instaladores da versão $($config.version)." }
$installers | Copy-Item -Destination dist -Force
# Manifesto lido pelo botão "Verificar atualizações" (release fixa "updates" no GitHub).
$platforms = [ordered]@{}
foreach ($installer in $installers) {
    $signature = "$($installer.FullName).sig"
    if (-not (Test-Path -LiteralPath $signature)) { continue }
    $entry = [ordered]@{
        signature = (Get-Content -LiteralPath $signature -Raw).Trim()
        url = "https://github.com/pbrmarcos/monitor/releases/download/v$($config.version)/$($installer.Name)"
    }
    if ($installer.Extension -eq '.exe') { $platforms['windows-x86_64'] = $entry; $platforms['windows-x86_64-nsis'] = $entry }
    else { $platforms['windows-x86_64-msi'] = $entry }
}
if ($platforms.Count) {
    if (-not $platforms.Contains('windows-x86_64')) { throw 'Assinatura do instalador NSIS ausente.' }
    $manifest = [ordered]@{
        version = $config.version
        notes = "Monitor $($config.version)"
        pub_date = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
        platforms = $platforms
    }
    $manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath dist/latest.json -Encoding utf8
    Write-Host 'Manifesto de atualização gerado em dist/latest.json'
}
Write-Host 'Instaladores gerados em dist/'
