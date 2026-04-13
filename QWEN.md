# Parrator — QWEN Context

## Project Overview

**Parrator** — это десктопное Python-приложение для распознавания речи (speech-to-text) с локальными ONNX-моделями. Приложение работает в фоновом режиме, записывает аудио по горячей клавише и вставляет распознанный текст в активное окно или буфер обмена.

### Ключевые возможности
- Глобальная горячая клавиша (PTT — push-to-talk или toggle-режим)
- Локальное распознавание речи через ONNX-модели (Parakeet, Whisper, GigaAM)
- GPU-ускорение через DirectML (Windows)
- Автоматическая вставка текста (paste/type режимы)
- Настраиваемый словарь автозамен
- PyQt6 GUI с эффектом Mica (Windows 11)
- Системный трей (PyQt6 tray mode)
- Плавающая анимация волны во время записи

### Технологии
- **Python 3.11–3.13**
- **Poetry** — управление зависимостями
- **PyQt6** — GUI-фреймворк
- **ONNX Runtime + onnx-asr** — распознавание речи
- **sounddevice + soundfile** — работа с аудио
- **pystray + keyboard** — трей и горячие клавиши
- **PyInstaller** — сборка в `.exe`

---

## Project Structure

```
parrator/             # Основной код приложения
├── __main__.py       # Entry point (tray или GUI режим)
├── gui_app.py        # PyQt6 GUI-приложение (~1459 строк)
├── tray_app.py       # Системный трей (фоновый режим)
├── transcriber.py    # Распознавание речи через ONNX
├── audio_recorder.py # Запись аудио с микрофона
├── hotkey_manager.py # Управление горячими клавишами
├── config.py         # Менеджер конфигурации (JSON)
├── text_output.py    # Вставка текста (paste/type)
├── text_postprocessor.py  # Постобработка текста
├── model_presets.py  # Пресеты моделей распознавания
├── wave_overlay.py   # Визуальная анимация волны
├── huggingface_runtime.py  # HuggingFace cache/runtime
├── notifications.py  # Системные уведомления
├── startup.py        # Автозапуск с системой
├── win_utils.py      # Windows-специфичные утилиты
├── resources/        # Иконки и runtime-ресурсы
tests/                # Unit-тесты (pytest)
assets/               # Статические ресурсы интерфейса
pyproject.toml        # Зависимости и настройки Ruff/pytest
Parrator.spec         # Конфигурация PyInstaller
```

---

## Building and Running

### Установка зависимостей
```bash
poetry install
```

### Запуск приложения
```bash
# Tray-режим (фоновый)
python -m parrator

# GUI-режим (графический интерфейс)
python -m parrator --gui
```

### Тестирование
```bash
# Быстрый прогон тестов
python -m pytest -q

# С подробным выводом
python -m pytest -v
```

### Линтинг и проверка стиля
```bash
python -m ruff check parrator tests
```

### Сборка .exe
```bash
pyinstaller Parrator.spec
```

---

## Development Conventions

### Coding Style
- **Отступы:** 4 пробела
- **Кавычки:** двойные (`"`)
- **Длина строки:** 88 символов (Ruff)
- **Именование:** `snake_case` для функций/переменных, `PascalCase` для классов
- **Комментарии:** на русском языке

### Imports
- В `gui_app.py` допускается нарушение порядка импортов (I001) из-за конфликта DLL с ONNX Runtime
- ONNX Runtime должен загружаться **до** PyQt6

### Testing
- Фреймворк: `pytest`
- Файлы: `tests/test_*.py`
- Добавлять тесты для новых веток логики
- Минимум перед коммитом: `python -m pytest -q`

### Конфигурация
- Путь: `%APPDATA%\Parrator\config.json`
- Формат: JSON
- **Не коммитьте** локальные конфиги в репозиторий

---

## Available Models

| Профиль | Описание |
|---------|----------|
| `nemo-fastconformer-ru-rnnt` | Модель по умолчанию (быстрая, русская) |
| `onnx-community/whisper-large-v3-turbo` | Whisper (поддерживает VAD, длинное аудио) |
| `gigaam-v3-rnnt` | ONNX-экспорт GigaAM v3 |

---

## Key Architecture Notes

### Transcriber
- Поддерживает два режима: прямой (FastConformer) и сегментированный (Whisper с VAD)
- Whisper автоматически разбивает аудио >30 сек на окна с перекрытием
- Использует `onnx-asr` для загрузки и распознавания моделей

### GUI (PyQt6)
- Windows 11: Mica-эффект + закруглённые углы через DwmApi
- Навигация через `QStackedWidget` (3 страницы: управление, словарь, журнал)
- Фоновые задачи через `QThread` для неблокирующего UI

### Config
- Хранится в `%APPDATA%\Parrator\config.json`
- Ключи: `hotkey`, `model_name`, `auto_paste`, `output_mode`, `dictionary`, `audio_device`

---

## Common Commands Reference

| Действие | Команда |
|----------|---------|
| Установка зависимостей | `poetry install` |
| Запуск GUI | `python -m parrator --gui` |
| Запуск tray | `python -m parrator` |
| Тесты | `python -m pytest -q` |
| Линтинг | `python -m ruff check parrator tests` |
| Сборка .exe | `pyinstaller Parrator.spec` |
| Проверка аудио-устройств | `python -c "import sounddevice; print(sounddevice.query_devices())"` |
