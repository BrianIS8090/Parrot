from parrator.transcriber import Transcriber


class DummyConfig:
  def __init__(self, values):
    self.values = values

  def get(self, key, default=None):
    return self.values.get(key, default)


def test_resolve_model_path_returns_given_path():
  config = DummyConfig({
    "model_name": "gigaam-v3-rnnt",
    "model_path": "C:/models/gigaam",
    "dictionary": {},
  })
  transcriber = Transcriber(config)

  resolved = transcriber._resolve_model_path("gigaam-v3-rnnt", "C:/models/gigaam")
  assert resolved == "C:/models/gigaam"


def test_resolve_model_path_returns_empty_when_path_not_set():
  config = DummyConfig({
    "model_name": "onnx-community/whisper-large-v3-turbo",
    "model_path": "",
    "dictionary": {},
  })
  transcriber = Transcriber(config)

  resolved = transcriber._resolve_model_path(
    "onnx-community/whisper-large-v3-turbo", ""
  )

  assert resolved == ""
