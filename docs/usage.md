# Установка и команды

## Установка

```bash
brew install ffmpeg python@3.12
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
```

## Диагностика

```bash
transcriber doctor
```

Команда проверяет наличие FFmpeg, macOS и пакета `mlx-whisper`.

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

