$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$setupScript = Join-Path $PSScriptRoot "setup-windows.ps1"
$transcriber = Join-Path $projectRoot ".venv\Scripts\transcriber.exe"

if (-not (Test-Path $transcriber)) {
    Write-Host "Первый запуск: подготавливаем программу..."
    & $setupScript
}

$machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
$env:Path = "$machinePath;$userPath"

if (-not (Test-Path $transcriber)) {
    throw "Программа не установлена. Запустите scripts\setup-windows.ps1 и проверьте сообщение об ошибке."
}

$url = "http://127.0.0.1:8000"
Write-Host "Запускаем Local Transcriber: $url"
Write-Host "Не закрывайте это окно, пока программа работает. Для остановки нажмите Ctrl+C."
Start-Process powershell.exe -WindowStyle Hidden -ArgumentList @(
    "-NoProfile",
    "-Command",
    "Start-Sleep -Seconds 2; Start-Process '$url'"
)

& $transcriber web
if ($LASTEXITCODE -ne 0) {
    throw "Программа завершилась с кодом $LASTEXITCODE."
}
