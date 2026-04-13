import numpy as np

from parrator.audio_recorder import AudioRecorder


class DummyConfig:
  def __init__(self):
    self.values = {}

  def get(self, key, default=None):
    return self.values.get(key, default)


def test_audio_callback_emits_level_and_stores_frame(monkeypatch):
  recorder = AudioRecorder(DummyConfig())
  emitted = []
  recorder.set_level_callback(emitted.append)

  monkeypatch.setattr("parrator.audio_recorder.time.monotonic", lambda: 10.0)

  frame = np.full((160, 1), 0.1, dtype=np.float32)
  recorder._audio_callback(frame, None, None, None)

  assert len(recorder.recorded_frames) == 1
  assert emitted
  assert 0 < emitted[0] <= 1


def test_audio_callback_throttles_level_updates(monkeypatch):
  recorder = AudioRecorder(DummyConfig())
  emitted = []
  recorder.set_level_callback(emitted.append)

  moments = iter([1.0, 1.01, 1.2])
  monkeypatch.setattr("parrator.audio_recorder.time.monotonic", lambda: next(moments))

  frame = np.full((160, 1), 0.12, dtype=np.float32)
  recorder._audio_callback(frame, None, None, None)
  recorder._audio_callback(frame, None, None, None)
  recorder._audio_callback(frame, None, None, None)

  assert len(emitted) == 2


def test_stop_recording_emits_zero_level(monkeypatch):
  recorder = AudioRecorder(DummyConfig())
  emitted = []
  recorder.set_level_callback(emitted.append)

  monkeypatch.setattr("parrator.audio_recorder.time.monotonic", lambda: 5.0)

  recorder.recorded_frames = [np.zeros((32, 1), dtype=np.float32)]
  audio_data = recorder.stop_recording()

  assert audio_data is not None
  assert emitted[-1] == 0.0
