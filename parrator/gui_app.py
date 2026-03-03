"""Современный GUI-режим Parrator для Windows 11 (PyQt6)."""

from __future__ import annotations

import os
import sys
import time
import ctypes
from contextlib import suppress
from datetime import datetime
from typing import Dict, Optional

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QCheckBox, QLineEdit, QTabWidget,
    QGroupBox, QTreeWidget, QTreeWidgetItem, QTextEdit, QProgressBar, QMessageBox,
    QHeaderView, QAbstractItemView, QSpacerItem, QSizePolicy
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, pyqtSlot, QObject, QTimer, QSize
from PyQt6.QtGui import QIcon, QFont, QColor

from huggingface_hub import snapshot_download

from .audio_recorder import AudioRecorder
from .config import Config
from .hotkey_manager import HotkeyManager
from .transcriber import Transcriber
from .wave_overlay import WaveOverlayController


MODEL_PRESETS: Dict[str, Dict[str, str]] = {
    "nemo-fastconformer-ru-rnnt": {
        "label": "RU FastConformer (быстрый, русский)",
        "repo_id": "istupakov/stt_ru_fastconformer_hybrid_large_pc_onnx",
    },
    "onnx-community/whisper-large-v3-turbo": {
        "label": "Whisper Large V3 Turbo (RU+EN)",
        "repo_id": "onnx-community/whisper-large-v3-turbo",
    },
}

MODEL_ORDER = [
    "nemo-fastconformer-ru-rnnt",
    "onnx-community/whisper-large-v3-turbo",
]
MODEL_LABELS = [MODEL_PRESETS[m]["label"] for m in MODEL_ORDER]
MODEL_LABEL_TO_NAME = {MODEL_PRESETS[m]["label"]: m for m in MODEL_ORDER}
MODEL_NAME_TO_LABEL = {m: MODEL_PRESETS[m]["label"] for m in MODEL_ORDER}


class WorkerSignals(QObject):
    log_msg = pyqtSignal(str)
    model_status_changed = pyqtSignal(str)
    service_status_changed = pyqtSignal(str)
    busy_changed = pyqtSignal(bool, str)
    result_text = pyqtSignal(str)
    controls_update = pyqtSignal()
    model_loaded_result = pyqtSignal(bool)


class BackgroundWorker(QThread):
    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def run(self):
        self.func(*self.args, **self.kwargs)


class ParratorGuiApp(QMainWindow):
    """Modern PyQt6 GUI для локальной диктовки."""

    def __init__(self):
        # Ensure QApplication exists before any QWidget is constructed
        self._app = QApplication.instance()
        if not self._app:
            self._app = QApplication(sys.argv)
            if sys.platform == "win32":
                self._app.setStyle("windowsvista")

        super().__init__()
        # Инициализация зависимостей
        self.config = Config()
        self.transcriber = Transcriber(self.config, logger=self.log_direct)
        self.audio_recorder = AudioRecorder(self.config)
        self.hotkey_manager: Optional[HotkeyManager] = None
        self.wave_overlay = WaveOverlayController()
        self.wave_overlay.start()

        self.model_loaded = False
        self.service_running = False
        self.is_recording = False
        self.is_processing = False
        self.model_loading = False
        self.target_window_handle: Optional[int] = None

        # Сигналы для безопасного обновления UI из других потоков
        self.signals = WorkerSignals()
        self.signals.log_msg.connect(self._append_log)
        self.signals.model_status_changed.connect(self._set_model_status_ui)
        self.signals.service_status_changed.connect(self._set_service_status_ui)
        self.signals.busy_changed.connect(self._set_busy_ui)
        self.signals.result_text.connect(self._set_result_text_ui)
        self.signals.controls_update.connect(self._update_controls_ui)
        self.signals.model_loaded_result.connect(self._on_model_loaded_for_start)

        self._init_window()
        self._build_ui()
        self._apply_styles()
        self._init_data()

        self.log("GUI запущен (PyQt6)")

    def _resource_path(self, relative_path: str) -> str:
        if getattr(sys, "frozen", False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_path, relative_path)

    def _init_window(self):
        self.setWindowTitle("Parrot")
        self.resize(1080, 760)
        self.setMinimumSize(980, 700)

        icon_path = self._resource_path("resources/icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # Windows 11 Mica & Rounded Corners
        if sys.platform == "win32":
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            hwnd = int(self.winId())
            try:
                # Включаем Mica
                DWMWA_SYSTEMBACKDROP_TYPE = 38
                DWMSBT_MICA = 2
                val = ctypes.c_int(DWMSBT_MICA)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, DWMWA_SYSTEMBACKDROP_TYPE, ctypes.byref(val), ctypes.sizeof(val)
                )

                # Закругленные углы
                DWMWA_WINDOW_CORNER_PREFERENCE = 33
                DWMWCP_ROUND = 2
                corner_val = ctypes.c_int(DWMWCP_ROUND)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, DWMWA_WINDOW_CORNER_PREFERENCE, ctypes.byref(corner_val), ctypes.sizeof(corner_val)
                )

                # Тёмная/Светлая тема ОС
                # DWMWA_USE_IMMERSIVE_DARK_MODE = 20
                # is_dark = 1 # 1 for dark, 0 for light
                # ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(ctypes.c_int(is_dark)), ctypes.sizeof(ctypes.c_int))

                # Расширяем рамку
                class MARGINS(ctypes.Structure):
                    _fields_ = [("cxLeftWidth", ctypes.c_int), ("cxRightWidth", ctypes.c_int),
                                ("cyTopHeight", ctypes.c_int), ("cyBottomHeight", ctypes.c_int)]
                margins = MARGINS(-1, -1, -1, -1)
                ctypes.windll.dwmapi.DwmExtendFrameIntoClientArea(hwnd, ctypes.byref(margins))
            except Exception as e:
                print(f"Mica effect not applied: {e}")

    def _build_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(24, 24, 24, 24)
        self.main_layout.setSpacing(16)

        # === Header ===
        header_layout = QHBoxLayout()
        header_left = QVBoxLayout()
        title_layout = QHBoxLayout()
        title = QLabel("Parrot")
        title.setObjectName("HeaderTitle")
        
        # Получаем версию из pyproject.toml если получится, или используем заглушку
        version = "v0.1.0"
        try:
            import tomli
            import os
            pyproject_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "pyproject.toml")
            with open(pyproject_path, "rb") as f:
                pyproject = tomli.load(f)
                version = f"v{pyproject['project']['version']}"
        except Exception:
            pass # Fallback to v0.1.0

        version_label = QLabel(version)
        version_label.setObjectName("VersionLabel")
        version_label.setStyleSheet("color: #0284c7; font-weight: bold; background: rgba(2, 132, 199, 0.1); border-radius: 4px; padding: 2px 6px; font-size: 8pt;")
        
        title_layout.addWidget(title)
        title_layout.addWidget(version_label)
        title_layout.addStretch()
        
        subtitle = QLabel("Локальная диктовка с быстрым выводом в активное приложение")
        subtitle.setObjectName("HeaderSub")
        header_left.addLayout(title_layout)
        header_left.addWidget(subtitle)
        
        header_right = QVBoxLayout()
        header_right.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.lbl_model_status = QLabel("Статус модели: неизвестно")
        self.lbl_model_status.setObjectName("StatusLabel")
        self.lbl_service_status = QLabel("Сервис: остановлен")
        self.lbl_service_status.setObjectName("StatusLabel")
        header_right.addWidget(self.lbl_model_status, alignment=Qt.AlignmentFlag.AlignRight)
        header_right.addWidget(self.lbl_service_status, alignment=Qt.AlignmentFlag.AlignRight)

        header_layout.addLayout(header_left)
        header_layout.addStretch()
        header_layout.addLayout(header_right)
        self.main_layout.addLayout(header_layout)

        # === Tabs ===
        self.tabs = QTabWidget()
        self.main_layout.addWidget(self.tabs, stretch=1)

        self.tab_control = QWidget()
        self.tab_dict = QWidget()
        self.tab_journal = QWidget()

        self.tabs.addTab(self.tab_control, "Управление")
        self.tabs.addTab(self.tab_dict, "Словарь")
        self.tabs.addTab(self.tab_journal, "Журнал")

        self._build_control_tab()
        self._build_dict_tab()
        self._build_journal_tab()

        # === Footer ===
        footer_layout = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0) # Indeterminate
        self.progress_bar.setFixedSize(150, 10)
        self.progress_bar.hide() # Hidden by default
        
        self.lbl_activity = QLabel("Готово")
        self.lbl_activity.setObjectName("ActivityLabel")

        footer_layout.addWidget(self.progress_bar)
        footer_layout.addStretch()
        footer_layout.addWidget(self.lbl_activity)
        self.main_layout.addLayout(footer_layout)

    def _build_control_tab(self):
        layout = QVBoxLayout(self.tab_control)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(20)

        # Управление моделью
        group_model = QGroupBox("Управление моделью")
        gm_layout = QVBoxLayout(group_model)
        
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Профиль модели:"))
        self.combo_model = QComboBox()
        self.combo_model.addItems(MODEL_LABELS)
        self.combo_model.currentTextChanged.connect(self._on_model_selected)
        row1.addWidget(self.combo_model, stretch=1)
        
        self.btn_check_cache = QPushButton("Проверить кэш")
        self.btn_check_cache.setObjectName("SecondaryBtn")
        self.btn_check_cache.clicked.connect(self.check_model_status)
        
        self.btn_save_model = QPushButton("Сохранить")
        self.btn_save_model.setObjectName("SecondaryBtn")
        self.btn_save_model.clicked.connect(self.save_model_settings)
        
        row1.addWidget(self.btn_check_cache)
        row1.addWidget(self.btn_save_model)
        
        hint = QLabel("Рекомендуется загрузить модель заранее, чтобы запись запускалась без задержек.")
        hint.setObjectName("SectionHint")
        
        gm_layout.addLayout(row1)
        gm_layout.addWidget(hint)
        layout.addWidget(group_model)

        # Параметры сервиса
        group_service = QGroupBox("Параметры сервиса")
        gs_layout = QVBoxLayout(group_service)
        
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Горячая клавиша:"))
        self.entry_hotkey = QLineEdit()
        row2.addWidget(self.entry_hotkey, stretch=1)
        
        row2.addSpacing(20)
        row2.addWidget(QLabel("Режим вывода:"))
        self.combo_output = QComboBox()
        self.combo_output.addItems(["paste", "type"])
        row2.addWidget(self.combo_output)
        
        self.check_autopaste = QCheckBox("Автовставка (для режима paste)")
        
        row3 = QHBoxLayout()
        self.btn_start = QPushButton("Включить диктовку")
        self.btn_start.setObjectName("AccentBtn")
        self.btn_start.clicked.connect(self.start_service)
        
        self.btn_stop = QPushButton("Остановить сервис")
        self.btn_stop.setObjectName("SecondaryBtn")
        self.btn_stop.clicked.connect(self.stop_service)
        
        self.btn_save_runtime = QPushButton("Сохранить настройки")
        self.btn_save_runtime.setObjectName("SecondaryBtn")
        self.btn_save_runtime.clicked.connect(self.save_runtime_settings)
        
        self.btn_open_config = QPushButton("Открыть config.json")
        self.btn_open_config.setObjectName("SecondaryBtn")
        self.btn_open_config.clicked.connect(self._open_config_file)
        
        row3.addWidget(self.btn_start)
        row3.addWidget(self.btn_stop)
        row3.addWidget(self.btn_save_runtime)
        row3.addWidget(self.btn_open_config)
        row3.addStretch()

        gs_layout.addLayout(row2)
        gs_layout.addWidget(self.check_autopaste)
        gs_layout.addLayout(row3)
        layout.addWidget(group_service)
        layout.addStretch()

    def _build_dict_tab(self):
        layout = QVBoxLayout(self.tab_dict)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        hint = QLabel("Добавляйте пары «что заменить» -> «на что заменить».")
        hint.setObjectName("SectionHint")
        layout.addWidget(hint)

        row_input = QHBoxLayout()
        self.entry_dict_source = QLineEdit()
        self.entry_dict_source.setPlaceholderText("Что заменить")
        self.entry_dict_target = QLineEdit()
        self.entry_dict_target.setPlaceholderText("На что заменить")
        self.btn_dict_add = QPushButton("Добавить")
        self.btn_dict_add.setObjectName("SecondaryBtn")
        self.btn_dict_add.clicked.connect(self._add_or_update_dictionary_rule)
        
        row_input.addWidget(self.entry_dict_source, stretch=1)
        row_input.addWidget(self.entry_dict_target, stretch=1)
        row_input.addWidget(self.btn_dict_add)
        layout.addLayout(row_input)

        self.tree_dict = QTreeWidget()
        self.tree_dict.setHeaderLabels(["Что заменить", "На что заменить"])
        self.tree_dict.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tree_dict.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tree_dict.header().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tree_dict.itemSelectionChanged.connect(self._on_dictionary_table_select)
        layout.addWidget(self.tree_dict, stretch=1)

        row_actions = QHBoxLayout()
        self.btn_dict_del = QPushButton("Удалить выбранное")
        self.btn_dict_del.setObjectName("SecondaryBtn")
        self.btn_dict_del.clicked.connect(self._delete_selected_dictionary_rule)
        
        self.btn_dict_save = QPushButton("Сохранить словарь")
        self.btn_dict_save.setObjectName("AccentBtn")
        self.btn_dict_save.clicked.connect(lambda: self.save_dictionary_settings(show_message=True))
        
        row_actions.addWidget(self.btn_dict_del)
        row_actions.addStretch()
        row_actions.addWidget(self.btn_dict_save)
        layout.addLayout(row_actions)

    def _build_journal_tab(self):
        layout = QVBoxLayout(self.tab_journal)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        grp_result = QGroupBox("Распознанный текст")
        lay_res = QVBoxLayout(grp_result)
        self.txt_result = QTextEdit()
        self.txt_result.setReadOnly(True)
        self.btn_clear_res = QPushButton("Очистить текст")
        self.btn_clear_res.setObjectName("SecondaryBtn")
        self.btn_clear_res.clicked.connect(lambda: self.txt_result.clear())
        
        lay_res_btn = QHBoxLayout()
        lay_res_btn.addStretch()
        lay_res_btn.addWidget(self.btn_clear_res)
        
        lay_res.addWidget(self.txt_result)
        lay_res.addLayout(lay_res_btn)
        layout.addWidget(grp_result, stretch=1)

        grp_log = QGroupBox("Логи и ошибки")
        lay_log = QVBoxLayout(grp_log)
        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setObjectName("LogConsole")
        self.btn_clear_log = QPushButton("Очистить логи")
        self.btn_clear_log.setObjectName("SecondaryBtn")
        self.btn_clear_log.clicked.connect(lambda: self.txt_log.clear())
        
        lay_log_btn = QHBoxLayout()
        lay_log_btn.addStretch()
        lay_log_btn.addWidget(self.btn_clear_log)
        
        lay_log.addWidget(self.txt_log)
        lay_log.addLayout(lay_log_btn)
        layout.addWidget(grp_log, stretch=1)

    def _apply_styles(self):
        # Modern Fluent-like QSS
        qss = """
        QMainWindow, QWidget#CentralWidget {
            background-color: transparent;
        }
        QWidget {
            font-family: "Segoe UI Variable Text", "Segoe UI", sans-serif;
            font-size: 10pt;
            color: #1f2937;
        }
        QLabel#HeaderTitle {
            font-size: 24pt;
            font-weight: bold;
            color: #0f172a;
        }
        QLabel#HeaderSub, QLabel#SectionHint, QLabel#ActivityLabel {
            font-size: 10pt;
            color: #475569;
        }
        QLabel#StatusLabel {
            font-weight: bold;
            color: #334155;
        }
        QTabWidget::pane {
            border: 1px solid rgba(255, 255, 255, 0.4);
            border-radius: 8px;
            background-color: rgba(255, 255, 255, 0.65);
        }
        QTabBar::tab {
            background-color: transparent;
            padding: 8px 24px;
            font-weight: bold;
            border-bottom: 2px solid transparent;
        }
        QTabBar::tab:selected {
            color: #0284c7;
            border-bottom: 2px solid #0284c7;
        }
        QTabBar::tab:hover {
            background-color: rgba(255, 255, 255, 0.5);
            border-top-left-radius: 6px;
            border-top-right-radius: 6px;
        }
        QGroupBox {
            font-weight: bold;
            border: 1px solid rgba(255, 255, 255, 0.5);
            border-radius: 8px;
            margin-top: 14px;
            background-color: rgba(255, 255, 255, 0.4);
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 5px;
            color: #0f172a;
        }
        QLineEdit, QComboBox, QTextEdit, QTreeWidget {
            border: 1px solid rgba(0, 0, 0, 0.1);
            border-radius: 6px;
            padding: 6px;
            background-color: rgba(255, 255, 255, 0.8);
        }
        QLineEdit:focus, QComboBox:focus, QTextEdit:focus, QTreeWidget:focus {
            border: 1px solid #0284c7;
            background-color: #ffffff;
        }
        QTextEdit#LogConsole {
            font-family: Consolas, monospace;
            font-size: 9pt;
        }
        QPushButton {
            border-radius: 6px;
            padding: 8px 16px;
            font-weight: 600;
        }
        QPushButton#AccentBtn {
            background-color: #0284c7;
            color: white;
            border: none;
        }
        QPushButton#AccentBtn:hover {
            background-color: #0369a1;
        }
        QPushButton#AccentBtn:pressed {
            background-color: #075985;
        }
        QPushButton#AccentBtn:disabled {
            background-color: rgba(2, 132, 199, 0.5);
        }
        QPushButton#SecondaryBtn {
            background-color: rgba(255, 255, 255, 0.7);
            border: 1px solid rgba(0, 0, 0, 0.1);
            color: #334155;
        }
        QPushButton#SecondaryBtn:hover {
            background-color: rgba(255, 255, 255, 1.0);
            border: 1px solid rgba(0, 0, 0, 0.2);
        }
        QPushButton#SecondaryBtn:pressed {
            background-color: rgba(0, 0, 0, 0.05);
        }
        QPushButton#SecondaryBtn:disabled {
            color: rgba(51, 65, 85, 0.4);
        }
        QHeaderView::section {
            background-color: rgba(255, 255, 255, 0.5);
            padding: 4px;
            border: none;
            border-right: 1px solid rgba(0,0,0,0.05);
            font-weight: bold;
        }
        QProgressBar {
            border: 1px solid rgba(0, 0, 0, 0.1);
            border-radius: 4px;
            background-color: rgba(255, 255, 255, 0.5);
            text-align: center;
        }
        QProgressBar::chunk {
            background-color: #0284c7;
            border-radius: 4px;
        }
        """
        self.central_widget.setObjectName("CentralWidget")
        self.setStyleSheet(qss)

    def _init_data(self):
        # Модель
        default_model_name = MODEL_ORDER[0]
        current_model = str(self.config.get("model_name", default_model_name))
        current_label = MODEL_NAME_TO_LABEL.get(current_model)
        if not current_label:
            current_model = default_model_name
            current_label = MODEL_NAME_TO_LABEL[current_model]
            self.config.set("model_name", current_model)
        
        self.combo_model.setCurrentText(current_label)

        # Настройки сервиса
        self.entry_hotkey.setText(str(self.config.get("hotkey", "ctrl+shift+;")))
        out_mode = str(self.config.get("output_mode", "paste"))
        idx = self.combo_output.findText(out_mode)
        if idx >= 0:
            self.combo_output.setCurrentIndex(idx)
        self.check_autopaste.setChecked(bool(self.config.get("auto_paste", True)))

        self._init_dictionary_settings()
        self.check_model_status()
        self._update_controls_ui()

    def _init_dictionary_settings(self):
        dictionary = self._normalize_dictionary(self.config.get("dictionary", {}))
        legacy_path = str(self.config.get("dictionary_path", "")).strip()
        if legacy_path:
            dictionary.update(self._load_dictionary_from_file(legacy_path))
            self.log("Словарь из файла перенесен в визуальные правила")
        
        self.tree_dict.clear()
        for src, tgt in dictionary.items():
            item = QTreeWidgetItem([src, tgt])
            self.tree_dict.addTopLevelItem(item)

    def _normalize_dictionary(self, raw: object) -> Dict[str, str]:
        d = {}
        if isinstance(raw, dict):
            for k, v in raw.items():
                if str(k).strip() and str(v).strip():
                    d[str(k).strip()] = str(v).strip()
        return d

    def _load_dictionary_from_file(self, path: str) -> Dict[str, str]:
        expanded = os.path.expanduser(path)
        if not os.path.exists(expanded):
            return {}
        try:
            with open(expanded, "r", encoding="utf-8") as f:
                return self._normalize_dictionary(json.load(f))
        except Exception as e:
            self.log(f"Не удалось прочитать словарь: {e}")
            return {}

    # === Dictionary UI Slots ===
    def _add_or_update_dictionary_rule(self):
        src = self.entry_dict_source.text().strip()
        tgt = self.entry_dict_target.text().strip()
        if not src or not tgt:
            self.log("Заполните оба поля словаря")
            return

        for i in range(self.tree_dict.topLevelItemCount()):
            item = self.tree_dict.topLevelItem(i)
            if item.text(0) == src:
                item.setText(1, tgt)
                self.log(f"Правило обновлено: {src} -> {tgt}")
                self.entry_dict_source.clear()
                self.entry_dict_target.clear()
                return

        item = QTreeWidgetItem([src, tgt])
        self.tree_dict.addTopLevelItem(item)
        self.log(f"Правило добавлено: {src} -> {tgt}")
        self.entry_dict_source.clear()
        self.entry_dict_target.clear()

    def _on_dictionary_table_select(self):
        items = self.tree_dict.selectedItems()
        if items:
            self.entry_dict_source.setText(items[0].text(0))
            self.entry_dict_target.setText(items[0].text(1))

    def _delete_selected_dictionary_rule(self):
        items = self.tree_dict.selectedItems()
        if not items:
            self.log("Выберите правило для удаления")
            return
        for item in items:
            idx = self.tree_dict.indexOfTopLevelItem(item)
            self.tree_dict.takeTopLevelItem(idx)
        self.entry_dict_source.clear()
        self.entry_dict_target.clear()
        self.log("Выбранное правило удалено")

    def save_dictionary_settings(self, show_message: bool = False) -> bool:
        d = {}
        for i in range(self.tree_dict.topLevelItemCount()):
            item = self.tree_dict.topLevelItem(i)
            d[item.text(0)] = item.text(1)
        self.config.set("dictionary_path", "")
        self.config.set("dictionary", d)
        self.log("Настройки словаря сохранены")
        if show_message:
            QMessageBox.information(self, "Словарь", "Словарь успешно сохранен")
        return True

    # === Core Logic & Threads ===

    def log_direct(self, message: str):
        # Used by Transcriber thread to emit to UI safely
        self.signals.log_msg.emit(message)

    def log(self, message: str):
        self.signals.log_msg.emit(message)

    @pyqtSlot(str)
    def _append_log(self, message: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.txt_log.append(f"[{ts}] {message}")
        status = message if len(message) <= 90 else f"{message[:87]}..."
        self.lbl_activity.setText(status)

    @pyqtSlot(str)
    def _set_model_status_ui(self, text: str):
        self.lbl_model_status.setText(text)
        self._update_controls_ui()

    @pyqtSlot(str)
    def _set_service_status_ui(self, text: str):
        self.lbl_service_status.setText(text)
        self._update_controls_ui()

    @pyqtSlot(bool, str)
    def _set_busy_ui(self, is_busy: bool, status_text: str):
        if is_busy:
            self.progress_bar.show()
        else:
            self.progress_bar.hide()
        if status_text:
            self.lbl_activity.setText(status_text)
        elif not is_busy:
            self.lbl_activity.setText("Готово")
        self._update_controls_ui()

    @pyqtSlot(str)
    def _set_result_text_ui(self, text: str):
        self.txt_result.setPlainText(text)

    @pyqtSlot()
    def _update_controls_ui(self):
        in_bg = self.is_processing or self.model_loading
        self.btn_start.setEnabled(not self.service_running and not in_bg)
        self.btn_stop.setEnabled(self.service_running)
        self.combo_model.setEnabled(not self.service_running and not self.model_loading)

    def _open_config_file(self):
        path = self.config.config_path
        try:
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                import subprocess
                subprocess.run(["open", path], check=False)
            else:
                import subprocess
                subprocess.run(["xdg-open", path], check=False)
            self.log(f"Открыт файл конфигурации: {path}")
        except Exception as e:
            self.log(f"Не удалось открыть конфиг: {e}")

    def _on_model_selected(self, label: str):
        model_name = MODEL_LABEL_TO_NAME.get(label)
        if not model_name:
            return
        self.config.set("model_name", model_name)
        self.model_loaded = False
        self.log(f"Выбрана модель: {model_name}")
        self.check_model_status()

    def save_model_settings(self):
        label = self.combo_model.currentText()
        model_name = MODEL_LABEL_TO_NAME.get(label)
        if model_name:
            self.config.set("model_name", model_name)
            self.config.set("model_path", "")
            self.model_loaded = False
            self.log("Настройки модели сохранены")
            self.check_model_status()

    def save_runtime_settings(self):
        self.config.set("hotkey", self.entry_hotkey.text().strip() or "ctrl+shift+;")
        self.config.set("output_mode", self.combo_output.currentText().strip() or "paste")
        self.config.set("auto_paste", self.check_autopaste.isChecked())
        if not self.save_dictionary_settings(show_message=False):
            self.log("Настройки словаря не сохранены")
            return False
        self.log("Настройки сервиса сохранены")
        return True

    def check_model_status(self):
        label = self.combo_model.currentText()
        model_name = MODEL_LABEL_TO_NAME.get(label)
        if not model_name:
            return
            
        self.signals.model_status_changed.emit("Статус модели: проверка...")
        
        def worker():
            preset = MODEL_PRESETS.get(model_name)
            if not preset:
                self.signals.model_status_changed.emit("Статус модели: не найдена")
                return
            repo_id = preset["repo_id"]
            try:
                snapshot_download(repo_id=repo_id, local_files_only=True)
                self.signals.model_status_changed.emit("Статус модели: скачана")
            except Exception:
                self.signals.model_status_changed.emit("Статус модели: не скачана")

        try:
            if hasattr(self, '_check_thread') and self._check_thread is not None:
                if self._check_thread.isRunning():
                    self._check_thread.quit()
                    self._check_thread.wait()
        except RuntimeError:
            pass # The thread C++ object has been deleted
            
        self._check_thread = BackgroundWorker(worker)
        self._check_thread.finished.connect(self._check_thread.deleteLater)
        self._check_thread.start()

    def load_model_async(self, auto_start=False):
        if self.model_loading:
            self.log("Загрузка модели уже выполняется")
            return

        self.save_model_settings()
        self.model_loading = True
        self.signals.busy_changed.emit(True, "Загрузка модели...")
        self.signals.model_status_changed.emit("Статус модели: загрузка...")
        self.log("Запущена загрузка/инициализация модели")

        def worker():
            ok = self.transcriber.load_model()
            if ok:
                self.signals.model_status_changed.emit("Статус модели: загружена и готова")
                self.signals.log_msg.emit("Модель готова к работе")
            else:
                self.signals.model_status_changed.emit("Статус модели: ошибка загрузки")
                self.signals.log_msg.emit("Ошибка загрузки модели")
            if auto_start:
                self.signals.model_loaded_result.emit(ok)
                
            self.signals.busy_changed.emit(False, "Готово")
            
        # Store ref to prevent GC
        self._load_thread = BackgroundWorker(worker)
        self._load_thread.finished.connect(self._on_model_load_thread_finished)
        self._load_thread.start()

    def _on_model_load_thread_finished(self):
        self.model_loading = False
        self.model_loaded = True
        self.signals.controls_update.emit()

    def start_service(self):
        if self.service_running:
            self.log("Сервис уже запущен")
            return
        if not self.save_runtime_settings():
            self.signals.service_status_changed.emit("Сервис: ошибка настроек")
            return
        if self.model_loading:
            self.signals.service_status_changed.emit("Сервис: идет загрузка модели...")
            self.log("Подождите завершения загрузки модели")
            return
        if not self.model_loaded:
            self.signals.service_status_changed.emit("Сервис: подготовка модели...")
            self.log("Модель не загружена, запускаю загрузку и автозапуск сервиса")
            self.load_model_async(auto_start=True)
            return

        self._start_service_with_hotkey()

    @pyqtSlot(bool)
    def _on_model_loaded_for_start(self, ok: bool):
        if not ok:
            self.signals.service_status_changed.emit("Сервис: ошибка загрузки модели")
            return
        self._start_service_with_hotkey()

    def _start_service_with_hotkey(self):
        if self.service_running:
            return

        hotkey = str(self.config.get("hotkey", "ctrl+shift+;"))
        self.hotkey_manager = HotkeyManager(
            hotkey, self._on_hotkey_press, self._on_hotkey_release
        )
        if not self.hotkey_manager.start():
            self.log("Не удалось зарегистрировать горячую клавишу")
            return

        self.service_running = True
        if self.hotkey_manager.is_hold_mode:
            self.signals.service_status_changed.emit(f"Сервис: запущен (удерживайте {hotkey})")
        else:
            self.signals.service_status_changed.emit(f"Сервис: запущен (toggle: {hotkey})")
        self.log("Сервис диктовки запущен")
        self.signals.controls_update.emit()

    def stop_service(self):
        if self.hotkey_manager:
            self.hotkey_manager.stop()
            self.hotkey_manager = None
        self.service_running = False
        self.is_recording = False
        self.signals.service_status_changed.emit("Сервис: остановлен")
        self.log("Сервис диктовки остановлен")
        self.signals.controls_update.emit()

    def _on_hotkey_press(self):
        if not self.service_running or self.is_processing:
            return
        if self.hotkey_manager and self.hotkey_manager.is_hold_mode:
            if not self.is_recording:
                # Dispatch safely to main thread
                QTimer.singleShot(0, self._start_recording)
            return

        if self.is_recording:
            QTimer.singleShot(0, self._stop_recording)
        else:
            QTimer.singleShot(0, self._start_recording)

    def _on_hotkey_release(self):
        if self.hotkey_manager and self.hotkey_manager.is_hold_mode and self.is_recording:
            QTimer.singleShot(0, self._stop_recording)

    def _start_recording(self):
        self.is_recording = True
        self.target_window_handle = self._get_foreground_window_handle()
        self.signals.service_status_changed.emit("Сервис: запись...")
        self.signals.busy_changed.emit(True, "Запись голоса...")
        self.log("Запись началась")
        
        self.wave_overlay.show()

        if not self.audio_recorder.start_recording():
            self.is_recording = False
            self.signals.service_status_changed.emit("Сервис: ошибка записи")
            self.signals.busy_changed.emit(False, "Готово")
            self.log("Не удалось начать запись")
            self.wave_overlay.hide()

    def _stop_recording(self):
        if not self.is_recording:
            return
        self.is_recording = False
        self.is_processing = True
        self.signals.service_status_changed.emit("Сервис: распознавание...")
        self.signals.busy_changed.emit(True, "Распознавание аудио...")
        self.log("Запись остановлена, распознавание...")
        
        self.wave_overlay.hide()

        audio_data = self.audio_recorder.stop_recording()
        if audio_data is None:
            self.is_processing = False
            self.signals.service_status_changed.emit("Сервис: нет аудио")
            self.signals.busy_changed.emit(False, "Нет аудио")
            self.log("Нет аудио для распознавания")
            return

        self._proc_thread = BackgroundWorker(self._process_audio, audio_data)
        self._proc_thread.finished.connect(self._proc_thread.deleteLater)
        self._proc_thread.start()

    def _process_audio(self, audio_data):
        temp_path = None
        try:
            temp_path = self.audio_recorder.save_temp_audio(audio_data)
            if not temp_path:
                self.signals.log_msg.emit("Не удалось сохранить временный файл")
                return

            ok, text = self.transcriber.transcribe_file(temp_path)
            if not ok or not text:
                self.signals.log_msg.emit("Распознавание не дало результата")
                return

            self.signals.log_msg.emit(f"Распознано: {text}")
            self.signals.result_text.emit(text)
            self._output_text(text)
        finally:
            self.is_processing = False
            if self.service_running:
                self.signals.service_status_changed.emit("Сервис: запущен")
            else:
                self.signals.service_status_changed.emit("Сервис: остановлен")
            self.signals.busy_changed.emit(False, "Готово")
            
            if temp_path and os.path.exists(temp_path):
                with suppress(Exception):
                    os.remove(temp_path)

    def _output_text(self, text: str):
        mode = str(self.config.get("output_mode", "paste")).lower().strip()
        if mode == "type":
            if self._type_direct(text):
                self.signals.log_msg.emit("Текст напечатан напрямую")
                return
            self.signals.log_msg.emit("Прямой ввод не сработал, fallback в буфер")

        try:
            import pyperclip
            pyperclip.copy(text)
            self.signals.log_msg.emit("Текст скопирован в буфер")
            if bool(self.config.get("auto_paste", True)):
                self._auto_paste()
        except Exception as e:
            self.signals.log_msg.emit(f"Ошибка буфера обмена: {e}")

    def _type_direct(self, text: str) -> bool:
        self._focus_target_window()
        try:
            from pynput.keyboard import Controller
            controller = Controller()
            time.sleep(0.12)
            controller.type(text)
            return True
        except Exception as e:
            self.signals.log_msg.emit(f"Ошибка прямого ввода: {e}")
            return False

    def _auto_paste(self):
        self._focus_target_window()
        try:
            from pynput.keyboard import Controller, Key
            controller = Controller()
            time.sleep(0.12)
            controller.press(Key.ctrl)
            controller.press("v")
            controller.release("v")
            controller.release(Key.ctrl)
            self.signals.log_msg.emit("Текст вставлен")
            return
        except Exception as e:
            self.signals.log_msg.emit(f"Вставка через pynput не сработала: {e}")

        try:
            import pyautogui
            time.sleep(0.12)
            pyautogui.hotkey("ctrl", "v")
            self.signals.log_msg.emit("Текст вставлен")
        except Exception as e:
            self.signals.log_msg.emit(f"Ошибка вставки: {e}")

    def _get_foreground_window_handle(self) -> Optional[int]:
        if os.name != "nt":
            return None
        try:
            return ctypes.windll.user32.GetForegroundWindow()
        except Exception:
            return None

    def _focus_target_window(self):
        if os.name != "nt" or not self.target_window_handle:
            return
        try:
            user32 = ctypes.windll.user32
            if user32.IsIconic(self.target_window_handle):
                user32.ShowWindow(self.target_window_handle, 9)
            user32.SetForegroundWindow(self.target_window_handle)
            time.sleep(0.08)
        except Exception as e:
            self.signals.log_msg.emit(f"Не удалось вернуть фокус: {e}")

    def closeEvent(self, event):
        self.wave_overlay.stop()
        self.stop_service()
        self.audio_recorder.cleanup()
        event.accept()

    def run(self):
        # Entry point for the main script
        app = QApplication.instance()
        if not app:
            app = QApplication(sys.argv)
            
        # Apply Windows Vista theme if available to look native
        if sys.platform == "win32":
            app.setStyle("windowsvista")
            
        self.show()
        
        # If run was called directly, we might need to exec if not already running
        # Assuming the caller will call exec() or we call it here.
        # In __main__.py: app.run() is called.
        sys.exit(app.exec())
