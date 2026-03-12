"""
Simplified transcription service using ONNX models.
"""

import os
import re
from contextlib import suppress
from importlib import metadata
from typing import Any, Callable, Optional, Tuple

import numpy as np
import onnxruntime as ort
import soundfile as sf
from onnx_asr import load_model, load_vad

from .config import Config
from .model_presets import (
  DEFAULT_MODEL_NAME,
  MODEL_MIN_ONNX_ASR_VERSION,
)
from .text_postprocessor import TextPostProcessor


class Transcriber:
  """Handles speech-to-text transcription."""

  WHISPER_DIRECT_MAX_SECONDS = 30.0
  WHISPER_WINDOW_SECONDS = 25.0
  WHISPER_WINDOW_OVERLAP_SECONDS = 1.0

  def __init__(self, config: Config, logger: Optional[Callable[[str], None]] = None):
    self.config = config
    self.model = None
    self.vad = None
    self.model_name = None
    self.last_error = ""
    self.logger = logger
    self.text_postprocessor = TextPostProcessor(config, logger=self._log)

  def _log(self, message: str):
    if self.logger:
      try:
        self.logger(message)
        return
      except Exception:
        pass
    with suppress(Exception):
      print(message)

  def load_model(self) -> bool:
    """Load the transcription model."""
    try:
      self.last_error = ""
      self.vad = None
      model_name = self.config.get(
        "model_name", DEFAULT_MODEL_NAME
      )
      model_path = str(self.config.get("model_path", "") or "").strip()
      if model_path and not os.path.isdir(model_path):
        self.last_error = f"Model path does not exist: {model_path}"
        self._log(self.last_error)
        return False

      required_version = MODEL_MIN_ONNX_ASR_VERSION.get(str(model_name))
      if (
        required_version
        and not self._is_onnx_asr_version_supported(required_version)
      ):
        self.last_error = (
          f"Модель '{model_name}' требует onnx-asr>={required_version}. "
          "Обновите зависимость и перезапустите приложение."
        )
        self._log(self.last_error)
        return False

      providers = self._get_providers()
      model_path = self._resolve_model_path(str(model_name), model_path)

      if model_path:
        self._log(f"Loading model: {model_name} from {model_path}")
        self.model = load_model(
          model_name, path=model_path, providers=providers
        )
      else:
        self._log(f"Loading model: {model_name}")
        self.model = load_model(model_name, providers=providers)
      self.model_name = model_name
      self.vad = self._load_vad_if_needed(str(model_name), providers)
      self.last_error = ""

      self._log(f"Model '{model_name}' loaded successfully")
      return True

    except Exception as e:
      self.last_error = f"Failed to load model: {e}"
      self._log(self.last_error)
      return False

  def _load_vad_if_needed(self, model_name: str, providers: list[str]):
    if not self._is_whisper_model_name(model_name):
      return None

    try:
      self._log("Loading VAD: silero")
      vad = load_vad("silero", providers=providers)
      self._log("VAD 'silero' loaded successfully")
      return vad
    except Exception as e:
      self._log(f"Не удалось загрузить VAD для Whisper: {e}")
      return None

  def _resolve_model_path(self, model_name: str, model_path: str) -> str:
    if model_path:
      return model_path

    # Если явный путь не задан, onnx-asr сам скачает только нужные файлы модели.
    return ""

  def _is_onnx_asr_version_supported(self, required_version: str) -> bool:
    try:
      current_version = metadata.version("onnx-asr")
    except metadata.PackageNotFoundError:
      return False
    current = self._version_to_tuple(current_version)
    required = self._version_to_tuple(required_version)
    return current >= required

  @staticmethod
  def _version_to_tuple(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", value))

  def transcribe_file(self, audio_path: str) -> Tuple[bool, Optional[str]]:
    """Transcribe an audio file."""
    if not self.model:
      return False, None

    if not os.path.exists(audio_path):
      return False, None

    try:
      if self._should_use_whisper_long_audio_mode(audio_path):
        self._log("Whisper long audio detected, using segmented transcription")
        text = self._transcribe_whisper_long_audio(audio_path)
      else:
        self._log("Using direct transcription mode")
        text = self._recognize_text(audio_path)

      processed_text = self.text_postprocessor.process(text)
      return True, processed_text if processed_text else None

    except Exception as e:
      self._log(f"Transcription failed: {e}")
      return False, None

  def _should_use_whisper_long_audio_mode(self, audio_path: str) -> bool:
    if not self._is_whisper_model_name(str(self.model_name or "")):
      return False

    duration = self._get_audio_duration(audio_path)
    return duration > self.WHISPER_DIRECT_MAX_SECONDS

  def _get_audio_duration(self, audio_path: str) -> float:
    try:
      return float(sf.info(audio_path).duration)
    except Exception as e:
      self._log(f"Не удалось определить длительность аудио: {e}")
      return 0.0

  def _transcribe_whisper_long_audio(self, audio_path: str) -> str:
    texts = self._transcribe_whisper_with_vad(audio_path)
    if texts:
      self._log(f"Whisper VAD mode: {len(texts)} segments")
      return self._join_texts(texts)

    texts = self._transcribe_whisper_with_windows(audio_path)
    self._log(f"Whisper window fallback: {len(texts)} windows")
    return self._join_texts(texts)

  def _transcribe_whisper_with_vad(self, audio_path: str) -> list[str]:
    if not self.vad:
      self._log("Whisper VAD is not available, switching to window fallback")
      return []

    try:
      segments = list(self.model.with_vad(self.vad, batch_size=1).recognize(audio_path))
    except Exception as e:
      self._log(f"Whisper VAD transcription failed: {e}")
      return []

    if not segments:
      self._log("Whisper VAD returned no segments")
      return []

    if self._has_oversized_vad_segments(segments):
      self._log("Whisper VAD returned oversized segments, switching to window fallback")
      return []

    texts = [self._extract_segment_text(segment) for segment in segments]
    return [text for text in texts if text]

  def _has_oversized_vad_segments(self, segments: list[Any]) -> bool:
    max_duration = 0.0
    for segment in segments:
      start = getattr(segment, "start", None)
      end = getattr(segment, "end", None)
      if isinstance(start, (int, float)) and isinstance(end, (int, float)):
        max_duration = max(max_duration, float(end) - float(start))
    return max_duration > self.WHISPER_DIRECT_MAX_SECONDS

  def _extract_segment_text(self, segment: Any) -> str:
    if isinstance(segment, dict):
      return str(segment.get("text", "")).strip()
    return str(getattr(segment, "text", segment)).strip()

  def _transcribe_whisper_with_windows(self, audio_path: str) -> list[str]:
    audio_data, sample_rate = sf.read(audio_path, dtype="float32", always_2d=False)
    audio_data = self._prepare_audio_array(audio_data)
    if audio_data.size == 0:
      return []

    window_size = max(int(sample_rate * self.WHISPER_WINDOW_SECONDS), 1)
    overlap_size = min(
      int(sample_rate * self.WHISPER_WINDOW_OVERLAP_SECONDS),
      max(window_size - 1, 0)
    )
    step_size = max(window_size - overlap_size, 1)

    texts: list[str] = []
    start = 0
    while start < len(audio_data):
      end = min(start + window_size, len(audio_data))
      chunk = np.ascontiguousarray(audio_data[start:end], dtype=np.float32)
      text = self._recognize_text(chunk, sample_rate=sample_rate)
      if text:
        texts.append(text)
      if end >= len(audio_data):
        break
      start += step_size

    return texts

  def _prepare_audio_array(self, audio_data: np.ndarray) -> np.ndarray:
    array = np.asarray(audio_data, dtype=np.float32)
    if array.ndim == 1:
      return array
    return np.mean(array, axis=1, dtype=np.float32)

  def _recognize_text(
    self,
    audio_input: str | np.ndarray,
    sample_rate: int = 16000
  ) -> str:
    if isinstance(audio_input, str):
      result = self.model.recognize(audio_input)
    else:
      result = self.model.recognize(audio_input, sample_rate=sample_rate)
    return self._normalize_recognition_result(result)

  def _normalize_recognition_result(self, result: Any) -> str:
    if isinstance(result, str):
      return result.strip()
    if isinstance(result, list) and result:
      if isinstance(result[0], dict) and "text" in result[0]:
        return " ".join(str(s.get("text", "")).strip() for s in result).strip()
      return " ".join(str(s).strip() for s in result).strip()
    if result is None:
      return ""
    return str(result).strip()

  def _join_texts(self, texts: list[str]) -> str:
    joined: list[str] = []
    for text in texts:
      normalized = text.strip()
      if not normalized:
        continue
      if joined and joined[-1] == normalized:
        continue
      joined.append(normalized)
    return " ".join(joined).strip()

  @staticmethod
  def _is_whisper_model_name(model_name: str) -> bool:
    return "whisper" in model_name.lower()

  def _get_providers(self):
    """Get ONNX runtime providers in preferred order."""
    available = ort.get_available_providers()
    preferred = [
      "DmlExecutionProvider",   # DirectML (Windows/WSL)
      "ROCMExecutionProvider",  # AMD GPU
      "CUDAExecutionProvider",  # NVIDIA GPU
      "CPUExecutionProvider"    # CPU fallback
    ]

    providers = [p for p in preferred if p in available]
    return providers or ["CPUExecutionProvider"]
