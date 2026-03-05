from parrator.model_presets import (
  DEFAULT_MODEL_NAME,
  MODEL_LABEL_TO_NAME,
  MODEL_LABELS,
  MODEL_MIN_ONNX_ASR_VERSION,
  MODEL_NAME_TO_LABEL,
  MODEL_ORDER,
  MODEL_PRESETS,
)


def test_model_profiles_include_gigaam_v3():
  assert "gigaam-v3-rnnt" in MODEL_ORDER
  assert MODEL_PRESETS["gigaam-v3-rnnt"]["repo_id"] == "istupakov/gigaam-v3-onnx"


def test_model_label_maps_are_consistent():
  assert len(MODEL_LABELS) == len(MODEL_ORDER)
  assert MODEL_ORDER[0] == DEFAULT_MODEL_NAME
  for model_name in MODEL_ORDER:
    label = MODEL_NAME_TO_LABEL[model_name]
    assert MODEL_LABEL_TO_NAME[label] == model_name


def test_gigaam_requires_modern_onnx_asr():
  assert MODEL_MIN_ONNX_ASR_VERSION["gigaam-v3-rnnt"] == "0.8.0"
