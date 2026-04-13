import contextlib
import importlib
import os
import shutil
import sys
from typing import Any


def is_frozen_windows() -> bool:
  """Возвращает True только для Windows-сборки PyInstaller."""
  return bool(getattr(sys, "frozen", False) and sys.platform == "win32")


def _normalize_cache_dir(cache_dir: str | None) -> str:
  base_dir = cache_dir or os.path.join("~", ".cache", "huggingface", "hub")
  expanded = os.path.expanduser(str(base_dir))
  return os.path.normcase(os.path.abspath(expanded))


def disable_hf_symlinks_for_frozen_windows() -> bool:
  """Отключает симлинки в huggingface-hub и сбрасывает их кэш."""
  if not is_frozen_windows():
    return False

  os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

  hf_constants = importlib.import_module("huggingface_hub.constants")
  file_download = importlib.import_module("huggingface_hub.file_download")
  cache_dir = _normalize_cache_dir(getattr(hf_constants, "HF_HUB_CACHE", None))

  cache_state = getattr(file_download, "_are_symlinks_supported_in_dir", None)
  if isinstance(cache_state, dict):
    cache_state.clear()
    cache_state[cache_dir] = False

  def _always_disable_symlinks(requested_cache_dir: str | None = None) -> bool:
    requested_dir = _normalize_cache_dir(requested_cache_dir or cache_dir)
    if isinstance(cache_state, dict):
      cache_state[requested_dir] = False
    return False

  file_download.are_symlinks_supported = _always_disable_symlinks
  return True


def fix_existing_hf_symlinks(cache_dir: str | None = None) -> tuple[int, int]:
  """Заменяет существующие симлинки в кеше huggingface на обычные файлы."""
  if not is_frozen_windows():
    return (0, 0)

  hub_cache_dir = _normalize_cache_dir(cache_dir)
  if not os.path.isdir(hub_cache_dir):
    return (0, 0)

  converted = 0
  failed = 0

  for root, _dirs, files in os.walk(hub_cache_dir):
    for name in files:
      full_path = os.path.join(root, name)
      tmp_path = f"{full_path}.copying"
      try:
        if not os.path.islink(full_path):
          continue

        link_target = os.readlink(full_path)
        target_path = link_target
        if not os.path.isabs(target_path):
          target_path = os.path.join(root, target_path)
        target_path = os.path.normpath(target_path)

        if not os.path.isfile(target_path):
          failed += 1
          continue

        shutil.copy2(target_path, tmp_path)
        os.unlink(full_path)
        os.replace(tmp_path, full_path)
        converted += 1
      except Exception:
        failed += 1
        with contextlib.suppress(Exception):
          os.remove(tmp_path)

  return (converted, failed)


def materialize_snapshot_symlinks(snapshot_dir: str) -> tuple[int, int]:
  """Заменяет симлинки внутри snapshot на обычные файлы."""
  normalized_snapshot_dir = _normalize_cache_dir(snapshot_dir)
  if not os.path.isdir(normalized_snapshot_dir):
    return (0, 0)

  converted = 0
  failed = 0

  for root, _dirs, files in os.walk(normalized_snapshot_dir):
    for name in files:
      full_path = os.path.join(root, name)
      tmp_path = f"{full_path}.copying"
      try:
        if not os.path.islink(full_path):
          continue

        target_path = os.path.realpath(full_path)
        if not os.path.isfile(target_path):
          failed += 1
          continue

        shutil.copy2(target_path, tmp_path)
        os.unlink(full_path)
        os.replace(tmp_path, full_path)
        converted += 1
      except Exception:
        failed += 1
        with contextlib.suppress(Exception):
          os.remove(tmp_path)

  return (converted, failed)


def prepare_hf_hub_runtime() -> tuple[int, int]:
  """Подготавливает huggingface-hub для работы из frozen Windows exe."""
  if not disable_hf_symlinks_for_frozen_windows():
    return (0, 0)

  hf_constants = importlib.import_module("huggingface_hub.constants")
  return fix_existing_hf_symlinks(getattr(hf_constants, "HF_HUB_CACHE", None))


def install_download_progress_hook(signals: Any) -> bool:
  """Подменяет tqdm huggingface-hub на версию с отчётом в GUI."""
  hf_tqdm_mod = importlib.import_module("huggingface_hub.utils.tqdm")
  hf_utils_mod = importlib.import_module("huggingface_hub.utils")

  current_tqdm = hf_tqdm_mod.tqdm
  if getattr(current_tqdm, "_parrator_gui_hook", False):
    current_tqdm._parrator_signals = signals
    hf_utils_mod.tqdm = current_tqdm
    return False

  class _GuiTqdm(current_tqdm):
    _parrator_gui_hook = True
    _parrator_signals = signals

    def __init__(self, *args, **kwargs):
      super().__init__(*args, **kwargs)
      self._last_logged_pct = -1

    def update(self, n=1):
      super().update(n)
      if not self.total or self.total <= 0:
        return

      pct = min(100, int(100 * self.n / self.total))
      if pct < self._last_logged_pct + 5:
        return

      self._last_logged_pct = pct
      desc = str(getattr(self, "desc", "") or "").strip().rstrip(":")
      if not desc:
        desc = "Скачивание"

      total_mb = self.total / 1_048_576
      if total_mb >= 1:
        done_mb = self.n / 1_048_576
        log_message = f"{desc}: {done_mb:.0f}/{total_mb:.0f} МБ ({pct}%)"
      else:
        log_message = f"{desc} ({pct}%)"

      hook_signals = type(self)._parrator_signals
      hook_signals.download_progress.emit(pct, desc)
      hook_signals.log_msg.emit(log_message)

  hf_tqdm_mod.tqdm = _GuiTqdm
  hf_utils_mod.tqdm = _GuiTqdm
  return True


def install_onnx_asr_download_logging(logger: Any) -> bool:
  """Добавляет подробные логи вокруг onnx_asr-загрузки из Hugging Face."""
  onnx_loader = importlib.import_module("onnx_asr.loader")

  if getattr(onnx_loader, "_parrator_download_logging_hook", False):
    onnx_loader._parrator_download_logger = logger
    return False

  original_download_config = onnx_loader._download_config
  original_download_model = onnx_loader._download_model

  def _log(message: str) -> None:
    current_logger = getattr(onnx_loader, "_parrator_download_logger", None)
    if current_logger:
      current_logger(message)

  def _download_config_with_logging(repo_id: str) -> str:
    _log(f"Hugging Face: проверяю config.json для {repo_id} (кэш/сеть)")
    try:
      result = original_download_config(repo_id)
    except Exception as exc:
      _log(f"Hugging Face: ошибка загрузки config.json для {repo_id}: {exc}")
      raise
    _log(f"Hugging Face: config.json готов для {repo_id}")
    return result

  def _download_model_with_logging(repo_id: str, files: list[str]) -> str:
    _log(
      "Hugging Face: проверяю кэш файлов модели "
      f"для {repo_id} ({len(files)} шаблонов), при необходимости докачаю"
    )
    try:
      result = original_download_model(repo_id, files)
    except Exception as exc:
      _log(f"Hugging Face: ошибка snapshot_download для {repo_id}: {exc}")
      raise
    converted, failed = materialize_snapshot_symlinks(result)
    if converted:
      _log(f"Hugging Face: материализовано симлинков в snapshot: {converted}")
    if failed:
      _log(f"Hugging Face: не удалось материализовать симлинков: {failed}")
    _log(f"Hugging Face: файлы модели готовы для {repo_id}")
    return result

  onnx_loader._download_config = _download_config_with_logging
  onnx_loader._download_model = _download_model_with_logging
  onnx_loader._parrator_download_logger = logger
  onnx_loader._parrator_download_logging_hook = True
  return True
