from parrator.wave_overlay import (
  WaveOverlayController,
  build_overlay_mask,
  get_overlay_screen,
)


class DummyStdin:
  def __init__(self):
    self.commands = []

  def write(self, value):
    self.commands.append(value)

  def flush(self):
    return None


class DummyProcess:
  def __init__(self):
    self.stdin = DummyStdin()


class DummyWidget:
  def __init__(self, screen):
    self._screen = screen

  def screen(self):
    return self._screen


def test_controller_sends_small_level_change_after_interval(monkeypatch):
  controller = WaveOverlayController()
  controller.process = DummyProcess()

  moments = iter([1.0, 1.01, 1.04])
  monkeypatch.setattr("parrator.wave_overlay.time.monotonic", lambda: next(moments))

  controller.set_level(0.2)
  controller.set_level(0.205)
  controller.set_level(0.205)

  assert controller.process.stdin.commands == [
    "level 0.2000\n",
    "level 0.2050\n",
  ]


def test_controller_always_sends_zero_level(monkeypatch):
  controller = WaveOverlayController()
  controller.process = DummyProcess()

  moments = iter([2.0, 2.005])
  monkeypatch.setattr("parrator.wave_overlay.time.monotonic", lambda: next(moments))

  controller.set_level(0.3)
  controller.set_level(0.0)

  assert controller.process.stdin.commands == [
    "level 0.3000\n",
    "level 0.0000\n",
  ]


def test_get_overlay_screen_prefers_cursor_screen(monkeypatch):
  cursor_screen = object()
  widget_screen = object()

  monkeypatch.setattr(
    "parrator.wave_overlay.QApplication.screenAt",
    lambda _pos: cursor_screen,
  )
  monkeypatch.setattr(
    "parrator.wave_overlay.QApplication.primaryScreen",
    lambda: None,
  )

  screen = get_overlay_screen(DummyWidget(widget_screen))

  assert screen is cursor_screen


def test_get_overlay_screen_falls_back_to_widget_and_primary(monkeypatch):
  primary_screen = object()

  monkeypatch.setattr(
    "parrator.wave_overlay.QApplication.screenAt",
    lambda _pos: None,
  )
  monkeypatch.setattr(
    "parrator.wave_overlay.QApplication.primaryScreen",
    lambda: primary_screen,
  )

  widget_screen = object()
  assert get_overlay_screen(DummyWidget(widget_screen)) is widget_screen
  assert get_overlay_screen(DummyWidget(None)) is primary_screen


def test_build_overlay_mask_matches_window_bounds():
  region = build_overlay_mask(216, 80)

  assert not region.isEmpty()
  bounds = region.boundingRect()
  assert bounds.width() <= 216
  assert bounds.height() <= 80
  assert bounds.width() >= 210
  assert bounds.height() >= 74
