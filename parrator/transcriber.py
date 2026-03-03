"""
Simplified transcription service using ONNX models.
"""

import os
from typing import Callable, Optional, Tuple

import onnxruntime as ort
from onnx_asr import load_model

from .config import Config
from .text_postprocessor import TextPostProcessor


class Transcriber:
    """Handles speech-to-text transcription."""

    def __init__(self, config: Config, logger: Optional[Callable[[str], None]] = None):
        self.config = config
        self.model = None
        self.model_name = None
        self.logger = logger
        self.text_postprocessor = TextPostProcessor(config, logger=self._log)

    def _log(self, message: str):
        if self.logger:
            try:
                self.logger(message)
                return
            except Exception:
                pass
        print(message)

    def load_model(self) -> bool:
        """Load the transcription model."""
        try:
            model_name = self.config.get(
                'model_name', 'nemo-parakeet-tdt-0.6b-v2')
            model_path = str(self.config.get("model_path", "") or "").strip()
            if model_path and not os.path.isdir(model_path):
                self._log(f"Model path does not exist: {model_path}")
                return False

            # Get available ONNX providers
            providers = self._get_providers()

            if model_path:
                self._log(f"Loading model: {model_name} from {model_path}")
                self.model = load_model(model_name, path=model_path, providers=providers)
            else:
                self._log(f"Loading model: {model_name}")
                self.model = load_model(model_name, providers=providers)
            self.model_name = model_name

            self._log(f"Model '{model_name}' loaded successfully")
            return True

        except Exception as e:
            self._log(f"Failed to load model: {e}")
            return False

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
