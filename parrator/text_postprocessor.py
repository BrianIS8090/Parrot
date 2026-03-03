"""
Постобработка распознанного текста.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Callable, Dict, Optional

from .config import Config

_WORD_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9-]+")
_SPLIT_RE = re.compile(r"([A-Za-zА-Яа-яЁё0-9-]+)")


class TextPostProcessor:
  """Применяет словарь замен к распознанному тексту."""

  def __init__(
    self,
    config: Config,
    logger: Optional[Callable[[str], None]] = None,
    morph_analyzer: Optional[Any] = None
  ):
    self.config = config
    self.logger = logger
    self._lemma_cache: Dict[str, str] = {}
    self._morph = morph_analyzer if morph_analyzer is not None else self._create_morph_analyzer()

  def process(self, text: str) -> str:
    """Применить словарь к тексту."""
    if not text:
      return text

    dictionary = self._load_dictionary()
    if not dictionary:
      return text

    exact_map, lemma_map = self._build_maps(dictionary)
    if not exact_map:
      return text

    return self._replace_words(text, exact_map, lemma_map)

  def _log(self, message: str):
    if self.logger:
      try:
        self.logger(message)
        return
      except Exception:
        pass
    print(message)

  def _create_morph_analyzer(self) -> Optional[Any]:
    try:
      import pymorphy3
      return pymorphy3.MorphAnalyzer()
    except Exception:
      self._log("pymorphy3 недоступен, используется fallback на точные замены словаря")
      return None

  def _load_dictionary(self) -> Dict[str, str]:
    raw_dictionary = self.config.get("dictionary", {})
    dictionary: Dict[str, str] = {}

    if isinstance(raw_dictionary, dict):
      for source, target in raw_dictionary.items():
        if source is None or target is None:
          continue
        source_text = str(source).strip()
        target_text = str(target).strip()
        if source_text and target_text:
          dictionary[source_text] = target_text
    elif raw_dictionary:
      self._log("Поле 'dictionary' в конфиге должно быть объектом вида {\"что\": \"на что\"}")

    dictionary_path = str(self.config.get("dictionary_path", "") or "").strip()
    if not dictionary_path:
      return dictionary

    path = os.path.expanduser(dictionary_path)
    if not os.path.isabs(path):
      config_path = str(getattr(self.config, "config_path", "") or "").strip()
      if config_path:
        config_dir = os.path.dirname(config_path)
        path = os.path.abspath(os.path.join(config_dir, path))
      else:
        path = os.path.abspath(path)
    if not os.path.exists(path):
      self._log(f"Файл словаря не найден: {path}")
      return dictionary

    try:
      with open(path, "r", encoding="utf-8") as dictionary_file:
        file_dictionary = json.load(dictionary_file)
      if isinstance(file_dictionary, dict):
        for source, target in file_dictionary.items():
          if source is None or target is None:
            continue
          source_text = str(source).strip()
          target_text = str(target).strip()
          if source_text and target_text:
            dictionary[source_text] = target_text
      else:
        self._log("Файл словаря должен содержать JSON-объект вида {\"что\": \"на что\"}")
    except Exception as error:
      self._log(f"Не удалось прочитать файл словаря: {error}")

    return dictionary

  def _build_maps(self, dictionary: Dict[str, str]) -> tuple[Dict[str, str], Dict[str, str]]:
    exact_map: Dict[str, str] = {}
    lemma_map: Dict[str, str] = {}

    for source, target in dictionary.items():
      source_key = source.lower()
      exact_map[source_key] = target
      lemma_key = self._lemmatize(source_key)
      lemma_map[lemma_key] = target

    return exact_map, lemma_map

  def _replace_words(
    self,
    text: str,
    exact_map: Dict[str, str],
    lemma_map: Dict[str, str]
  ) -> str:
    parts = _SPLIT_RE.split(text)
    for i, part in enumerate(parts):
      if not part or not _WORD_RE.fullmatch(part):
        continue

      source_word = part.lower()
      replacement = exact_map.get(source_word)
      if replacement is None and self._morph is not None:
        lemma = self._lemmatize(source_word)
        replacement = lemma_map.get(lemma)

      if replacement is not None:
        parts[i] = replacement

    return "".join(parts)

  def _lemmatize(self, word: str) -> str:
    cached = self._lemma_cache.get(word)
    if cached is not None:
      return cached

    lemma = word
    if self._morph is not None:
      try:
        parsed = self._morph.parse(word)
        if parsed:
          normal_form = getattr(parsed[0], "normal_form", None)
          if normal_form:
            lemma = str(normal_form)
      except Exception:
        lemma = word

    self._lemma_cache[word] = lemma
    return lemma
