import json
import os
from unittest.mock import patch

from parrator.config import Config


def _make_config(tmp_path):
    config_dir = tmp_path / "Parrator"
    config_dir.mkdir()
    config_path = config_dir / "config.json"
    with patch.object(Config, "_get_config_path", return_value=str(config_path)):
        cfg = Config()
    return cfg, config_path


def test_defaults_created_when_no_file(tmp_path):
    cfg, config_path = _make_config(tmp_path)
    assert cfg.get("auto_paste") is True
    assert cfg.get("output_mode") == "paste"
    assert os.path.exists(config_path)


def test_get_returns_default_for_missing_key(tmp_path):
    cfg, _ = _make_config(tmp_path)
    assert cfg.get("nonexistent_key", 42) == 42


def test_set_persists_to_file(tmp_path):
    cfg, config_path = _make_config(tmp_path)
    cfg.set("hotkey", "f8")
    with open(config_path, "r") as f:
        data = json.load(f)
    assert data["hotkey"] == "f8"


def test_set_updates_in_memory(tmp_path):
    cfg, _ = _make_config(tmp_path)
    cfg.set("output_mode", "type")
    assert cfg.get("output_mode") == "type"


def test_update_batch_writes_once(tmp_path):
    cfg, config_path = _make_config(tmp_path)
    cfg.update_batch({"hotkey": "f9", "output_mode": "type", "auto_paste": False})
    with open(config_path, "r") as f:
        data = json.load(f)
    assert data["hotkey"] == "f9"
    assert data["output_mode"] == "type"
    assert data["auto_paste"] is False
    assert cfg.get("hotkey") == "f9"


def test_load_merges_with_defaults(tmp_path):
    cfg, config_path = _make_config(tmp_path)
    cfg.set("hotkey", "f8")
    with patch.object(Config, "_get_config_path", return_value=str(config_path)):
        cfg2 = Config()
    assert cfg2.get("hotkey") == "f8"
    assert cfg2.get("auto_paste") is True
