$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$venvDirectory = Join-Path $projectRoot ".venv"

Write-Host "Проверяем Python..."
if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 -m venv $venvDirectory
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    & python -m venv $venvDirectory
} else {
    throw "Python 3.11 или новее не найден. Установите Python с https://www.python.org/downloads/windows/"
}

if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Host "FFmpeg не найден. Устанавливаем через winget..."
        & winget install --id Gyan.FFmpeg --exact --accept-package-agreements --accept-source-agreements
        $machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
        $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
        $env:Path = "$machinePath;$userPath"
        Write-Host "FFmpeg установлен."
    } else {
        throw "FFmpeg не найден. Установите его вручную и добавьте ffmpeg.exe и ffprobe.exe в PATH."
    }
}

$python = Join-Path $venvDirectory "Scripts\python.exe"
$transcriber = Join-Path $venvDirectory "Scripts\transcriber.exe"

Write-Host "Устанавливаем Python-зависимости..."
& $python -m pip install --upgrade pip
& $python -m pip install -e $projectRoot

Write-Host "Проверяем окружение..."
& $transcriber doctor

Write-Host ""
Write-Host "Готово. Запуск: .\.venv\Scripts\transcriber.exe web"
