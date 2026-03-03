from parrator.text_postprocessor import TextPostProcessor


class DummyConfig:
  def __init__(self, values):
    self.values = values

  def get(self, key, default=None):
    return self.values.get(key, default)


class DummyParseResult:
  def __init__(self, normal_form):
    self.normal_form = normal_form


class DummyMorph:
  def __init__(self, normal_forms):
    self.normal_forms = normal_forms

  def parse(self, word):
    normal_form = self.normal_forms.get(word, word)
    return [DummyParseResult(normal_form)]


def test_exact_replacement_without_morph():
  config = DummyConfig({
    "dictionary": {
      "привет": "здравствуйте"
    }
  })
  processor = TextPostProcessor(config, morph_analyzer=None)

  result = processor.process("привет, мир!")

  assert result == "здравствуйте, мир!"


def test_lemma_replacement_with_morph():
  config = DummyConfig({
    "dictionary": {
      "собака": "пёс"
    }
  })
  morph = DummyMorph({
    "собаки": "собака",
    "собаку": "собака"
  })
  processor = TextPostProcessor(config, morph_analyzer=morph)

  result = processor.process("собаки и собаку")

  assert result == "пёс и пёс"


def test_exact_fallback_for_non_lemmatized_word():
  config = DummyConfig({
    "dictionary": {
      "собаки": "псы"
    }
  })
  processor = TextPostProcessor(config, morph_analyzer=None)

  result = processor.process("собаки и коты")

  assert result == "псы и коты"


def test_invalid_dictionary_value_ignored():
  config = DummyConfig({
    "dictionary": ["невалидный формат"]
  })
  processor = TextPostProcessor(config, morph_analyzer=None)

  result = processor.process("текст без изменений")

  assert result == "текст без изменений"
