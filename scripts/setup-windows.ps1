$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$venvDirectory = Join-Path $projectRoot ".venv"

function Assert-NativeCommandSucceeded {
    param([string]$Action)
    if ($LASTEXITCODE -ne 0) {
        throw "$Action завершилось с кодом $LASTEXITCODE."
    }
}

function Refresh-ProcessPath {
    $machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$machinePath;$userPath"
}

function Test-PyLauncher311 {
    if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
        return $false
    }
    & py -3.11 -c "import sys; raise SystemExit(sys.version_info[:2] != (3, 11))" 2>$null
    return $LASTEXITCODE -eq 0
}

function Find-Python311Executable {
    $candidates = @(
        (Join-Path $env:LocalAppData "Programs\Python\Python311\python.exe"),
        (Join-Path $env:ProgramFiles "Python311\python.exe")
    )
    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCommand -and $pythonCommand.Source -notlike "*\WindowsApps\*") {
        $version = & $pythonCommand.Source -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
        if ($LASTEXITCODE -eq 0 -and $version.Trim() -eq "3.11") {
            return $pythonCommand.Source
        }
    }
    return $null
}

Write-Host "Проверяем Python 3.11..."
$python311 = Find-Python311Executable
if (-not (Test-PyLauncher311) -and -not $python311) {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw "Python 3.11 не найден. Установите Python 3.11 (64-bit) с python.org и повторите запуск."
    }
    Write-Host "Python 3.11 не найден. Устанавливаем через winget..."
    & winget install --id Python.Python.3.11 --exact --scope user --accept-package-agreements --accept-source-agreements
    Assert-NativeCommandSucceeded "Установка Python 3.11"
    Refresh-ProcessPath
    $python311 = Find-Python311Executable
}

if (Test-Path $venvDirectory) {
    $existingPython = Join-Path $venvDirectory "Scripts\python.exe"
    if (Test-Path $existingPython) {
        $venvVersion = & $existingPython -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
        if ($LASTEXITCODE -ne 0 -or $venvVersion.Trim() -ne "3.11") {
            throw "Папка .venv создана другой версией Python. Удалите .venv и запустите start-windows.bat снова."
        }
    }
}

if (-not (Test-Path (Join-Path $venvDirectory "Scripts\python.exe"))) {
    Write-Host "Создаём виртуальное окружение..."
    if (Test-PyLauncher311) {
        & py -3.11 -m venv $venvDirectory
    } else {
        $python311 = Find-Python311Executable
        if (-not $python311) {
            throw "Python 3.11 установлен, но не найден. Перезапустите Windows и повторите запуск."
        }
        & $python311 -m venv $venvDirectory
    }
    Assert-NativeCommandSucceeded "Создание виртуального окружения"
}

if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue) -or
    -not (Get-Command ffprobe -ErrorAction SilentlyContinue)) {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw "FFmpeg не найден. Установите FFmpeg вручную и добавьте ffmpeg.exe и ffprobe.exe в PATH."
    }
    Write-Host "FFmpeg не найден. Устанавливаем через winget..."
    & winget install --id Gyan.FFmpeg --exact --accept-package-agreements --accept-source-agreements
    Assert-NativeCommandSucceeded "Установка FFmpeg"
    Refresh-ProcessPath
}

if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue) -or
    -not (Get-Command ffprobe -ErrorAction SilentlyContinue)) {
    throw "FFmpeg установлен, но ещё не появился в PATH. Перезапустите Windows и снова откройте start-windows.bat."
}

$python = Join-Path $venvDirectory "Scripts\python.exe"
$transcriber = Join-Path $venvDirectory "Scripts\transcriber.exe"

Write-Host "Устанавливаем компоненты программы. Это может занять несколько минут..."
& $python -m pip install --upgrade pip
Assert-NativeCommandSucceeded "Обновление pip"
& $python -m pip install -e $projectRoot
Assert-NativeCommandSucceeded "Установка программы"

Write-Host "Проверяем окружение..."
& $transcriber doctor
Assert-NativeCommandSucceeded "Проверка окружения"

Write-Host ""
Write-Host "Установка завершена. В дальнейшем запускайте start-windows.bat."
