# Стек технологий

## Python 3.11+

Основной язык приложения. Бизнес-логика транскрибации не зависит от веб-слоя и может
переиспользоваться в CLI или другом интерфейсе.

## Whisper-движки

`mlx-whisper` запускает многоязычные модели Whisper локально и использует GPU Apple Silicon
через MLX. На 64-битной Windows `faster-whisper` запускает модели через CTranslate2: на NVIDIA
GPU используется CUDA, а на остальных компьютерах доступен CPU-режим с INT8.

Доступны три профиля:

| Профиль | macOS / MLX | Windows / CTranslate2 |
|---|---|---|
| Быстро | `mlx-community/whisper-small-mlx` | `Systran/faster-whisper-small` |
| Сбалансированно | `mlx-community/whisper-large-v3-turbo` | `mobiuslabsgmbh/faster-whisper-large-v3-turbo` |
| Максимальное качество | `mlx-community/whisper-large-v3-mlx` | `Systran/faster-whisper-large-v3` |

Модель скачивается с Hugging Face один раз и затем читается из локального кэша.

## FFmpeg

FFprobe и FFmpeg проверяют и декодируют поддерживаемые медиаформаты. Перед распознаванием
первая аудиодорожка преобразуется в mono PCM WAV с частотой 16 кГц.

## FastAPI и Uvicorn

FastAPI принимает multipart-загрузки потоково, предоставляет API состояния задания и отдаёт
файлы результата. Uvicorn запускает приложение только на loopback-интерфейсе.

## Jinja2 и нативный JavaScript

Интерфейс рендерится Jinja2. Загрузка с прогрессом и опрос состояния реализованы небольшим
локальным JavaScript-файлом. React, Node.js и CDN не требуются.

## Тестирование

Pytest проверяет экспорт форматов, выбор платформенного движка и выполнение задания через очередь
без загрузки настоящей модели. Ruff используется для статической проверки. GitHub Actions
повторяет эти проверки на `windows-latest`.

