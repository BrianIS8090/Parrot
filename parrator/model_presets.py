"""Каталог доступных профилей моделей."""

MODEL_PRESETS: dict[str, dict[str, str]] = {
  "nemo-fastconformer-ru-rnnt": {
    "label": "RU FastConformer (быстрый, русский)",
    "repo_id": "istupakov/stt_ru_fastconformer_hybrid_large_pc_onnx",
  },
  "onnx-community/whisper-large-v3-turbo": {
    "label": "Whisper Large V3 Turbo (RU+EN)",
    "repo_id": "onnx-community/whisper-large-v3-turbo",
  },
  "gigaam-v3-rnnt": {
    "label": "GigaAM v3 RNNT (русский)",
    "repo_id": "istupakov/gigaam-v3-onnx",
  },
}

MODEL_ORDER: list[str] = [
  "nemo-fastconformer-ru-rnnt",
  "onnx-community/whisper-large-v3-turbo",
  "gigaam-v3-rnnt",
]

DEFAULT_MODEL_NAME = MODEL_ORDER[0]
MODEL_LABELS = [MODEL_PRESETS[m]["label"] for m in MODEL_ORDER]
MODEL_LABEL_TO_NAME = {
  MODEL_PRESETS[m]["label"]: m for m in MODEL_ORDER
}
MODEL_NAME_TO_LABEL = {
  m: MODEL_PRESETS[m]["label"] for m in MODEL_ORDER
}

MODEL_MIN_ONNX_ASR_VERSION: dict[str, str] = {
  "gigaam-v3-rnnt": "0.8.0",
}
