$ErrorActionPreference = "Stop"
$projectRoot = (Get-Item -LiteralPath (Join-Path $PSScriptRoot "..")).FullName
$venvDirectory = Join-Path $projectRoot ".venv"
$pythonRuntimeDirectory = Join-Path $env:LocalAppData "LocalTranscriber\Python311-x64"
$python311 = Join-Path $pythonRuntimeDirectory "python.exe"
$pythonInstallerUrl = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
$pythonInstallerSha256 = "5EE42C4EEE1E6B4464BB23722F90B45303F79442DF63083F05322F1785F5FDDE"

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

function Test-Python311X64 {
    param([string]$Executable)
    if (-not (Test-Path $Executable)) {
        return $false
    }
    & $Executable -c "import platform, sys; raise SystemExit(sys.version_info[:2] != (3, 11) or platform.machine().lower() not in ('amd64', 'x86_64'))" 2>$null
    return $LASTEXITCODE -eq 0
}

function Install-PrivatePython311X64 {
    $installer = Join-Path $env:TEMP "local-transcriber-python-3.11.9-amd64.exe"
    Write-Host "Скачиваем официальный Python 3.11 x64..."
    try {
        Invoke-WebRequest -UseBasicParsing -Uri $pythonInstallerUrl -OutFile $installer
        $actualHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $installer).Hash
        if ($actualHash -ne $pythonInstallerSha256) {
            throw "Контрольная сумма установщика Python не совпала. Файл не будет запущен."
        }
        $signature = Get-AuthenticodeSignature -LiteralPath $installer
        if ($signature.Status -ne "Valid") {
            throw "Не удалось подтвердить цифровую подпись установщика Python: $($signature.Status)."
        }
        Write-Host "Устанавливаем локальный Python 3.11 x64..."
        $arguments = @(
            "/quiet",
            "InstallAllUsers=0",
            "TargetDir=`"$pythonRuntimeDirectory`"",
            "Include_launcher=0",
            "Include_test=0",
            "PrependPath=0",
            "Shortcuts=0"
        )
        $process = Start-Process -FilePath $installer -ArgumentList $arguments -Wait -PassThru
        if ($process.ExitCode -ne 0) {
            throw "Установка Python 3.11 x64 завершилась с кодом $($process.ExitCode)."
        }
    } finally {
        Remove-Item -LiteralPath $installer -Force -ErrorAction SilentlyContinue
    }
}

if ($projectRoot.StartsWith("\\")) {
    throw "Проект открыт из сетевой или общей папки ($projectRoot). Скопируйте папку проекта на локальный диск Windows, например в C:\LocalTranscriber, и снова запустите start-windows.bat."
}

Write-Host "Проверяем Python 3.11 x64..."
if (-not (Test-Python311X64 $python311)) {
    Install-PrivatePython311X64
}
if (-not (Test-Python311X64 $python311)) {
    throw "Python 3.11 x64 установлен, но не прошёл проверку архитектуры."
}

if (Test-Path $venvDirectory) {
    $existingPython = Join-Path $venvDirectory "Scripts\python.exe"
    if (-not (Test-Python311X64 $existingPython)) {
        Write-Host "Найдено несовместимое окружение .venv. Пересоздаём его на Python x64..."
        Remove-Item -LiteralPath $venvDirectory -Recurse -Force
    }
}

if (-not (Test-Path (Join-Path $venvDirectory "Scripts\python.exe"))) {
    Write-Host "Создаём виртуальное окружение..."
    & $python311 -m venv $venvDirectory
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
