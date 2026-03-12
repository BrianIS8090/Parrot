from pathlib import Path

import numpy as np
import soundfile as sf

from parrator.transcriber import Transcriber


class DummyConfig:
  def __init__(self, values):
    self.values = values

  def get(self, key, default=None):
    return self.values.get(key, default)


class DummySegment:
  def __init__(self, start, end, text):
    self.start = start
    self.end = end
    self.text = text


class DummyVadAdapter:
  def __init__(self, model, segments):
    self.model = model
    self.segments = segments

  def recognize(self, audio_path):
    self.model.vad_recognize_calls.append(audio_path)
    return iter(self.segments)


class DummyWhisperModel:
  def __init__(self, direct_result="", chunk_results=None, vad_segments=None):
    self.direct_result = direct_result
    self.chunk_results = list(chunk_results or [])
    self.vad_segments = list(vad_segments or [])
    self.direct_calls = []
    self.chunk_calls = []
    self.with_vad_calls = []
    self.vad_recognize_calls = []

  def recognize(self, audio_input, sample_rate=16000):
    if isinstance(audio_input, str):
      self.direct_calls.append(audio_input)
      return self.direct_result

    self.chunk_calls.append((len(audio_input), sample_rate))
    if self.chunk_results:
      return self.chunk_results.pop(0)
    return self.direct_result

  def with_vad(self, vad, batch_size=1):
    self.with_vad_calls.append((vad, batch_size))
    return DummyVadAdapter(self, self.vad_segments)


def _build_config(model_name):
  return DummyConfig({
    "model_name": model_name,
    "model_path": "",
    "dictionary": {},
  })


def _create_audio_file(tmp_path: Path, duration_seconds: int, sample_rate: int = 16000):
  samples = np.zeros(sample_rate * duration_seconds, dtype=np.float32)
  audio_path = tmp_path / f"audio_{duration_seconds}s.wav"
  sf.write(audio_path, samples, sample_rate)
  return audio_path


def test_resolve_model_path_returns_given_path():
  config = _build_config("gigaam-v3-rnnt")
  transcriber = Transcriber(config)

  resolved = transcriber._resolve_model_path("gigaam-v3-rnnt", "C:/models/gigaam")
  assert resolved == "C:/models/gigaam"


def test_resolve_model_path_returns_empty_when_path_not_set():
  config = _build_config("onnx-community/whisper-large-v3-turbo")
  transcriber = Transcriber(config)

  resolved = transcriber._resolve_model_path(
    "onnx-community/whisper-large-v3-turbo", ""
  )

  assert resolved == ""


def test_whisper_short_audio_uses_direct_recognize(tmp_path, monkeypatch):
  config = _build_config("onnx-community/whisper-large-v3-turbo")
  transcriber = Transcriber(config)
  transcriber.model = DummyWhisperModel(direct_result="короткий текст")
  transcriber.model_name = config.get("model_name")
  monkeypatch.setattr(
    transcriber.text_postprocessor,
    "process",
    lambda text: text
  )

  audio_path = _create_audio_file(tmp_path, 10)
  success, text = transcriber.transcribe_file(str(audio_path))

  assert success is True
  assert text == "короткий текст"
  assert transcriber.model.direct_calls == [str(audio_path)]
  assert transcriber.model.with_vad_calls == []


def test_whisper_long_audio_uses_vad_segments(tmp_path, monkeypatch):
  config = _build_config("onnx-community/whisper-large-v3-turbo")
  transcriber = Transcriber(config)
  transcriber.model = DummyWhisperModel(
    vad_segments=[
      DummySegment(0.0, 12.0, "первая часть"),
      DummySegment(13.0, 28.0, "вторая часть"),
      DummySegment(29.0, 41.0, "третья часть"),
    ]
  )
  transcriber.model_name = config.get("model_name")
  transcriber.vad = object()
  monkeypatch.setattr(
    transcriber.text_postprocessor,
    "process",
    lambda text: text
  )

  audio_path = _create_audio_file(tmp_path, 41)
  success, text = transcriber.transcribe_file(str(audio_path))

  assert success is True
  assert text == "первая часть вторая часть третья часть"
  assert transcriber.model.direct_calls == []
  assert transcriber.model.with_vad_calls == [(transcriber.vad, 1)]
  assert transcriber.model.vad_recognize_calls == [str(audio_path)]


def test_whisper_long_audio_falls_back_to_windows(tmp_path, monkeypatch):
  config = _build_config("onnx-community/whisper-large-v3-turbo")
  transcriber = Transcriber(config)
  transcriber.model = DummyWhisperModel(
    chunk_results=["первое окно", "второе окно", "третье окно"],
    vad_segments=[DummySegment(0.0, 60.0, "слишком длинный сегмент")]
  )
  transcriber.model_name = config.get("model_name")
  transcriber.vad = object()
  monkeypatch.setattr(
    transcriber.text_postprocessor,
    "process",
    lambda text: text
  )

  audio_path = _create_audio_file(tmp_path, 60)
  success, text = transcriber.transcribe_file(str(audio_path))

  assert success is True
  assert text == "первое окно второе окно третье окно"
  assert transcriber.model.direct_calls == []
  assert len(transcriber.model.chunk_calls) == 3
  assert all(sample_rate == 16000 for _, sample_rate in transcriber.model.chunk_calls)


def test_non_whisper_long_audio_keeps_direct_mode(tmp_path, monkeypatch):
  config = _build_config("nemo-fastconformer-ru-rnnt")
  transcriber = Transcriber(config)
  transcriber.model = DummyWhisperModel(direct_result="прямой режим")
  transcriber.model_name = config.get("model_name")
  monkeypatch.setattr(
    transcriber.text_postprocessor,
    "process",
    lambda text: text
  )

  audio_path = _create_audio_file(tmp_path, 60)
  success, text = transcriber.transcribe_file(str(audio_path))

  assert success is True
  assert text == "прямой режим"
  assert transcriber.model.direct_calls == [str(audio_path)]
  assert transcriber.model.with_vad_calls == []
  assert transcriber.model.chunk_calls == []


def test_load_model_keeps_working_when_whisper_vad_fails(monkeypatch):
  config = _build_config("onnx-community/whisper-large-v3-turbo")
  transcriber = Transcriber(config)

  model = object()
  monkeypatch.setattr("parrator.transcriber.load_model", lambda *args, **kwargs: model)

  def fail_load_vad(*args, **kwargs):
    raise RuntimeError("vad unavailable")

  monkeypatch.setattr("parrator.transcriber.load_vad", fail_load_vad)

  assert transcriber.load_model() is True
  assert transcriber.model is model
  assert transcriber.vad is None
