import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

from parrator import huggingface_runtime as runtime


class _SignalRecorder:
  def __init__(self):
    self.calls = []

  def emit(self, *args):
    self.calls.append(args)


def _register_fake_hf_modules(monkeypatch, cache_dir: Path):
  package = ModuleType("huggingface_hub")
  package.__path__ = []

  utils_module = ModuleType("huggingface_hub.utils")
  tqdm_module = ModuleType("huggingface_hub.utils.tqdm")
  constants_module = ModuleType("huggingface_hub.constants")
  file_download_module = ModuleType("huggingface_hub.file_download")

  class _BaseTqdm:
    def __init__(self, *args, total=None, initial=0, desc="", **kwargs):
      self.total = total
      self.n = initial
      self.desc = desc

    def update(self, n=1):
      self.n += n

  constants_module.HF_HUB_CACHE = str(cache_dir)
  file_download_module._are_symlinks_supported_in_dir = {
    runtime._normalize_cache_dir(str(cache_dir)): True
  }
  file_download_module.are_symlinks_supported = lambda cache_dir=None: True
  tqdm_module.tqdm = _BaseTqdm
  utils_module.tqdm = _BaseTqdm

  monkeypatch.setitem(sys.modules, "huggingface_hub", package)
  monkeypatch.setitem(sys.modules, "huggingface_hub.utils", utils_module)
  monkeypatch.setitem(sys.modules, "huggingface_hub.utils.tqdm", tqdm_module)
  monkeypatch.setitem(sys.modules, "huggingface_hub.constants", constants_module)
  monkeypatch.setitem(
    sys.modules,
    "huggingface_hub.file_download",
    file_download_module,
  )

  return SimpleNamespace(
    utils=utils_module,
    tqdm=tqdm_module,
    constants=constants_module,
    file_download=file_download_module,
  )


def test_disable_hf_symlinks_for_frozen_windows_overrides_cached_state(
  monkeypatch
):
  cache_dir = Path("C:/hf-cache")
  fake_modules = _register_fake_hf_modules(monkeypatch, cache_dir)
  monkeypatch.setattr(runtime.sys, "platform", "win32", raising=False)
  monkeypatch.setattr(runtime.sys, "frozen", True, raising=False)

  assert runtime.disable_hf_symlinks_for_frozen_windows() is True

  normalized_cache = runtime._normalize_cache_dir(str(cache_dir))
  assert fake_modules.file_download._are_symlinks_supported_in_dir == {
    normalized_cache: False
  }
  assert fake_modules.file_download.are_symlinks_supported() is False
  assert (
    fake_modules.file_download.are_symlinks_supported(str(cache_dir / "nested"))
    is False
  )
  assert fake_modules.file_download._are_symlinks_supported_in_dir[
    runtime._normalize_cache_dir(str(cache_dir / "nested"))
  ] is False


def test_fix_existing_hf_symlinks_materializes_links_and_counts_failures(
  monkeypatch
):
  cache_dir = runtime._normalize_cache_dir("C:/hf-cache/hub")
  ok_link = runtime._normalize_cache_dir("C:/hf-cache/hub/ok-link")
  broken_link = runtime._normalize_cache_dir("C:/hf-cache/hub/broken-link")
  model_blob = runtime._normalize_cache_dir("C:/hf-cache/blobs/model.onnx")
  copied_targets = []
  removed_links = []
  replaced_links = []

  monkeypatch.setattr(runtime, "is_frozen_windows", lambda: True)
  monkeypatch.setattr(runtime.os.path, "isdir", lambda path: path == cache_dir)
  monkeypatch.setattr(
    runtime.os,
    "walk",
    lambda _: [(cache_dir, [], ["ok-link", "broken-link", "plain-file"])],
  )
  monkeypatch.setattr(
    runtime.os.path,
    "islink",
    lambda path: path in {ok_link, broken_link},
  )
  monkeypatch.setattr(
    runtime.os,
    "readlink",
    lambda path: "../blobs/model.onnx" if path == ok_link else "../blobs/missing.onnx",
  )
  monkeypatch.setattr(
    runtime.os.path,
    "isfile",
    lambda path: path == model_blob,
  )
  monkeypatch.setattr(
    runtime.shutil,
    "copy2",
    lambda src, dst: copied_targets.append((src, dst)),
  )
  monkeypatch.setattr(
    runtime.os,
    "unlink",
    lambda path: removed_links.append(path),
  )
  monkeypatch.setattr(
    runtime.os,
    "replace",
    lambda src, dst: replaced_links.append((src, dst)),
  )

  converted, failed = runtime.fix_existing_hf_symlinks(cache_dir)

  assert converted == 1
  assert failed == 1
  assert copied_targets == [(model_blob, f"{ok_link}.copying")]
  assert removed_links == [ok_link]
  assert replaced_links == [(f"{ok_link}.copying", ok_link)]


def test_install_download_progress_hook_patches_real_tqdm_module(monkeypatch):
  fake_modules = _register_fake_hf_modules(monkeypatch, Path("C:/hf-cache"))
  signals = SimpleNamespace(
    download_progress=_SignalRecorder(),
    log_msg=_SignalRecorder(),
  )

  assert runtime.install_download_progress_hook(signals) is True
  assert fake_modules.tqdm.tqdm is fake_modules.utils.tqdm

  progress_bar = fake_modules.tqdm.tqdm(total=100, desc="decoder_model.onnx:")
  progress_bar.update(6)
  progress_bar.update(2)
  progress_bar.update(42)

  assert signals.download_progress.calls == [
    (6, "decoder_model.onnx"),
    (50, "decoder_model.onnx"),
  ]
  assert signals.log_msg.calls == [
    ("decoder_model.onnx (6%)",),
    ("decoder_model.onnx (50%)",),
  ]


def test_materialize_snapshot_symlinks_replaces_links(monkeypatch):
  snapshot_dir = runtime._normalize_cache_dir("C:/hf-cache/snapshots/abc/onnx")
  link_file = runtime._normalize_cache_dir(
    "C:/hf-cache/snapshots/abc/onnx/file.onnx_data"
  )
  copied_targets = []
  removed_links = []
  replaced_links = []

  monkeypatch.setattr(runtime.os.path, "isdir", lambda path: path == snapshot_dir)
  monkeypatch.setattr(
    runtime.os,
    "walk",
    lambda _: [(snapshot_dir, [], ["file.onnx_data"])],
  )
  monkeypatch.setattr(runtime.os.path, "islink", lambda path: path == link_file)
  monkeypatch.setattr(
    runtime.os.path,
    "realpath",
    lambda path: runtime._normalize_cache_dir("C:/hf-cache/blobs/blob-file"),
  )
  monkeypatch.setattr(
    runtime.os.path,
    "isfile",
    lambda path: path == runtime._normalize_cache_dir("C:/hf-cache/blobs/blob-file"),
  )
  monkeypatch.setattr(
    runtime.shutil,
    "copy2",
    lambda src, dst: copied_targets.append((src, dst)),
  )
  monkeypatch.setattr(runtime.os, "unlink", lambda path: removed_links.append(path))
  monkeypatch.setattr(
    runtime.os,
    "replace",
    lambda src, dst: replaced_links.append((src, dst)),
  )

  converted, failed = runtime.materialize_snapshot_symlinks(snapshot_dir)

  assert converted == 1
  assert failed == 0
  assert copied_targets == [
    (
      runtime._normalize_cache_dir("C:/hf-cache/blobs/blob-file"),
      f"{link_file}.copying",
    )
  ]
  assert removed_links == [link_file]
  assert replaced_links == [(f"{link_file}.copying", link_file)]


def test_install_onnx_asr_download_logging_wraps_loader_functions(monkeypatch):
  loader_module = ModuleType("onnx_asr.loader")
  messages = []

  def _download_config(repo_id):
    messages.append(("config-call", repo_id))
    return f"{repo_id}/config.json"

  def _download_model(repo_id, files):
    messages.append(("model-call", repo_id, tuple(files)))
    return f"{repo_id}/snapshot"

  loader_module._download_config = _download_config
  loader_module._download_model = _download_model
  monkeypatch.setitem(sys.modules, "onnx_asr.loader", loader_module)

  logged = []
  assert runtime.install_onnx_asr_download_logging(logged.append) is True

  assert loader_module._download_config("repo/test") == "repo/test/config.json"
  assert loader_module._download_model("repo/test", ["a.onnx"]) == "repo/test/snapshot"

  assert logged == [
    "Hugging Face: проверяю config.json для repo/test (кэш/сеть)",
    "Hugging Face: config.json готов для repo/test",
    (
      "Hugging Face: проверяю кэш файлов модели для repo/test "
      "(1 шаблонов), при необходимости докачаю"
    ),
    "Hugging Face: файлы модели готовы для repo/test",
  ]
