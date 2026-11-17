# Установка и команды

## Установка на macOS

```bash
brew install ffmpeg python@3.12
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
```

## Установка на Windows

Требуется 64-битная Windows 10/11 и Python 3.11 или новее. В PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup-windows.ps1
```

Сценарий устанавливает зависимости в `.venv`. Если FFmpeg отсутствует и доступен `winget`,
он также установит FFmpeg и обновит `PATH` текущего процесса.

Ручная установка:

```powershell
winget install --id Gyan.FFmpeg --exact
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

На Windows Faster Whisper автоматически использует NVIDIA CUDA, если CTranslate2 видит
совместимую видеокарту и в системе установлены требуемые CUDA-библиотеки. В остальных случаях,
в том числе если CUDA не удалось загрузить, приложение продолжает работу на CPU с INT8.

## Диагностика

```bash
transcriber doctor
```

Команда проверяет FFmpeg, совместимость платформы и установленный движок. На Mac проверяется
`mlx-whisper` и Metal; на Windows — `faster-whisper`, CTranslate2 и доступность CUDA или CPU.

## Скачивание моделей

```bash
transcriber models download fast
transcriber models download balanced
transcriber models download quality
```

Для обычного использования достаточно `balanced`.

## Запуск веб-интерфейса

```bash
transcriber web
```

В PowerShell без активации виртуального окружения:

```powershell
.\.venv\Scripts\transcriber.exe web
```

Другой порт:

```bash
transcriber web --port 8080
```

Строгий офлайн-режим:

```bash
transcriber web --offline
```

В офлайн-режиме Hugging Face не скачивает отсутствующую модель. Поэтому сначала выполните
`transcriber models download balanced` при доступном интернете.

## Переменные окружения

При программном создании приложения поддерживаются:

| Переменная | Значение по умолчанию | Назначение |
|---|---:|---|
| `TRANSCRIBER_HOST` | `127.0.0.1` | Адрес локального сервера |
| `TRANSCRIBER_PORT` | `8000` | Порт |
| `TRANSCRIBER_OFFLINE` | `false` | Запрет сетевого скачивания моделей |
| `TRANSCRIBER_MODELS_DIR` | `<проект>/models` | Каталог весов моделей |

Параметры команды `transcriber web` задаются непосредственно флагами `--host`, `--port` и
`--offline`.

## Тесты

```bash
pytest
ruff check .
```

