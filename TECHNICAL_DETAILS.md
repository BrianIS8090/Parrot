# Технические детали Parrator

Этот файл содержит термины и техническую информацию, вынесенную из `README.md`.

## Технологии

- Python 3.11+
- Poetry (управление зависимостями)
- ONNX-модели распознавания речи
- Интеграция с системным треем

## Технические возможности

- Глобальная горячая клавиша: `Ctrl+Shift+;`
- Распознавание речи через модели Parakeet и Whisper
- Копирование результата в буфер обмена
- Опциональная автоматическая вставка текста
- Опциональный автозапуск вместе с системой

## Доступные модели распознавания

- `nemo-fastconformer-ru-rnnt` (по умолчанию)
- `onnx-community/whisper-large-v3-turbo`
- `gigaam-v3-rnnt` (ONNX-экспорт GigaAM v3)

Для профиля `gigaam-v3-rnnt` требуется `onnx-asr >= 0.8.0`.

## Конфигурация

Файл настроек использует JSON-формат:

```json
{
  "hotkey": "ctrl+shift+;",
  "model_name": "nemo-fastconformer-ru-rnnt",
  "auto_paste": true,
  "auto_start_with_system": false
}
```

Поля:
- `hotkey`: сочетание клавиш для запуска/остановки записи
- `model_name`: идентификатор модели распознавания
- `auto_paste`: автоматически вставлять текст после копирования
- `auto_start_with_system`: запускать приложение при старте ОС

## Системные требования

- Windows 10/11: поддержка DirectML для ускорения на GPU
- macOS 10.14+: могут потребоваться права доступности для горячих клавиш
- Linux: современный дистрибутив с поддержкой аудио

## Отладка и диагностика

Проверка доступных аудио-устройств:

```bash
python -c "import sounddevice; print(sounddevice.query_devices())"
```

Проблемы с горячей клавишей:
- Windows: при необходимости запуск от имени администратора
- macOS: выдать приложению права в настройках Accessibility
- Linux: установить `python3-dev` и аудио-библиотеки

GPU-ускорение в Windows:
- обновить драйвер видеокарты
- установить Windows Media Feature Pack
- убедиться, что DirectML доступен

## Разработка

Установка и запуск в режиме разработки:

```bash
git clone https://github.com/yourusername/parrator.git
cd parrator
poetry install
poetry run python -m parrator
```

Сборка исполняемого файла:

```bash
poetry run pyinstaller Parrator.spec
```
