"""
Simplified audio recording functionality.
"""

import tempfile
import threading
from typing import List, Optional

import numpy as np
import sounddevice as sd
import soundfile as sf

from .config import Config


class AudioRecorder:
    """Handles audio recording operations."""

    def __init__(self, config: Config):
        self.config = config
        self.sample_rate = 16000
        self.channels = 1
        self.recorded_frames: List[np.ndarray] = []
        self.stream: Optional[sd.InputStream] = None
        self.lock = threading.Lock()

    def start_recording(self) -> bool:
        """Start recording audio."""
        try:
            with self.lock:
                self.recorded_frames.clear()

                self.stream = sd.InputStream(
                    samplerate=self.sample_rate,
                    channels=self.channels,
                    callback=self._audio_callback,
                    dtype='float32'
                )

                self.stream.start()
                return True

        except Exception as e:
            print(f"Failed to start recording: {e}")
            return False

    def stop_recording(self) -> Optional[np.ndarray]:
        """Stop recording and return audio data."""
        try:
            with self.lock:
                if self.stream:
                    self.stream.stop()
                    self.stream.close()
                    self.stream = None

                if self.recorded_frames:
                    audio_data = np.concatenate(self.recorded_frames, axis=0)
                    return audio_data

                return None

        except Exception as e:
            print(f"Error stopping recording: {e}")
            return None

    def _audio_callback(self, indata: np.ndarray, frames, time, status):
        """Callback for audio stream."""
        if status:
            print(f"Audio callback status: {status}")

        with self.lock:
            self.recorded_frames.append(indata.copy())

    def save_temp_audio(self, audio_data: np.ndarray) -> Optional[str]:
        """Save audio data to temporary file."""
        try:
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_path = temp_file.name

            sf.write(temp_path, audio_data, self.sample_rate)
            return temp_path

        except Exception as e:
            print(f"Failed to save temporary audio: {e}")
            return None

    def cleanup(self):
        """Clean up audio resources."""
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except:
                pass
