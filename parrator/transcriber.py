"""
Simplified transcription service using ONNX models.
"""

import os
import re
from importlib import metadata
from typing import Callable, Optional, Tuple

import onnxruntime as ort
from onnx_asr import load_model

from .config import Config
from .model_presets import (
    DEFAULT_MODEL_NAME,
    MODEL_MIN_ONNX_ASR_VERSION,
)
from .text_postprocessor import TextPostProcessor


class Transcriber:
    """Handles speech-to-text transcription."""

    def __init__(self, config: Config, logger: Optional[Callable[[str], None]] = None):
        self.config = config
        self.model = None
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
        try:
            print(message)
        except Exception:
            pass

    def load_model(self) -> bool:
        """Load the transcription model."""
        try:
            self.last_error = ""
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

            # Get available ONNX providers
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
            self.last_error = ""

            self._log(f"Model '{model_name}' loaded successfully")
            return True

        except Exception as e:
            self.last_error = f"Failed to load model: {e}"
            self._log(self.last_error)
            return False

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
            result = self.model.recognize(audio_path)

            # Handle different result formats
            if isinstance(result, str):
                text = result.strip()
            elif isinstance(result, list) and result:
                if isinstance(result[0], dict) and 'text' in result[0]:
                    text = ' '.join(s.get('text', '') for s in result).strip()
                else:
                    text = ' '.join(str(s) for s in result).strip()
            else:
                text = str(result).strip()

            processed_text = self.text_postprocessor.process(text)
            return True, processed_text if processed_text else None

        except Exception as e:
            self._log(f"Transcription failed: {e}")
            return False, None

    def _get_providers(self):
        """Get ONNX runtime providers in preferred order."""
        available = ort.get_available_providers()
        preferred = [
            'DmlExecutionProvider',    # DirectML (Windows/WSL)
            'ROCMExecutionProvider',   # AMD GPU
            'CUDAExecutionProvider',   # NVIDIA GPU
            'CPUExecutionProvider'     # CPU fallback
        ]

        providers = [p for p in preferred if p in available]
        return providers or ['CPUExecutionProvider']
