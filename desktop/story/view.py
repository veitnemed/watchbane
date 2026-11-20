"""Search-first Qt home; original library/title search remain separate tabs."""
from importlib.util import find_spec
import os
from pathlib import Path
import sqlite3
import sys
from threading import Event

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QShortcut, QKeySequence
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                            QPushButton, QScrollArea, QFrame, QMessageBox, QFileDialog, QDialog, QMenu, QProgressBar)
from candidates import service
from candidates.title_state_service import STATE_WATCHLIST, get_title_states
from desktop.theme.scaling import layout_px
from desktop.theme.layout import MAIN_TAB_PANE_TOP_LIFT
from desktop.theme.styles.story import build_story_style
from config.app_settings_store import ProfileSetting, get_active_profile_root


_MODEL_SETTING = "story_search.model_dir"
_MODEL_ENV = "WATCHBANE_STORY_MODEL_DIR"
_MODEL_UNSET = object()


def _publisher_model_dir():
    """Find the optional external asset beside a frozen executable, not the source tree."""
    if not getattr(sys, "frozen", False) or not sys.executable:
        return None
    directory = Path(sys.executable).parent / "assets" / "story-model"
    try:
        return str(directory) if directory.is_dir() else None
    except OSError:
        return None


class StoryWorker(QThread):
    completed = pyqtSignal(object, object, int)
    failed = pyqtSignal()
    snapshot_failed = pyqtSignal()
    progress = pyqtSignal(str)

    def __init__(self, query, parent, model_dir=None, seed_path=None):
        super().__init__(parent)
        self.query = query
        self.model_dir = model_dir
        self.seed_path = seed_path
        self._cancelled = Event()

    def cancel(self):
        self._cancelled.set()

    def run(self):
        from candidates.story_seed_snapshot import StorySeedSnapshotError

        try:
            engine, records = service.local_story_catalog(
                self.model_dir, on_progress=self.progress.emit,
                cancelled=self._cancelled.is_set, seed_path=self.seed_path)
            if self._cancelled.is_set():
                return
            self.progress.emit("Ищем совпадения в каталоге…")
            result = engine.search(self.query)
            self.completed.emit(result, records, len(engine.documents))
        except StorySeedSnapshotError:
            self.snapshot_failed.emit()
        except Exception:
            self.failed.emit()


class SnapshotCheckWorker(QThread):
    """Validate a local file without loading E5 or building a search index."""

    def __init__(self, path, parent):
        super().__init__(parent)
        self.path = path
        self.count = 0
        self.failure = None

    def run(self):
        from candidates.story_seed_snapshot import StorySeedSnapshotError, load_seed_snapshot

        if self.isInterruptionRequested():
            return
        try:
            self.count = len(load_seed_snapshot(self.path))
        except StorySeedSnapshotError as exc:
            self.failure = str(exc)
        except Exception:
            self.failure = "Не удалось проверить файл каталога."


def _semantic_install_available():
    # Discover packaging/dependency availability without importing ONNX or E5.
    try:
        return all(find_spec(name) is not None for name in ("numpy", "onnxruntime", "tokenizers"))
    except (ImportError, ValueError):
        return False


_MODEL_INSTALL_HINTS = {
    "redirect_host": "Адрес загрузки у поставщика изменился. Обновите Watchbane или выберите готовую папку.",
    "http_status": "Сервер модели не отдал файлы. Повторите позже или выберите готовую папку.",
    "invalid_response": "Сервер вернул неожиданный файл. Повторите позже или выберите готовую папку.",
    "integrity": "Не совпала контрольная сумма. Файлы не подключены; попробуйте скачать ещё раз.",
    "tls": "Не удалось подтвердить защищённое соединение. Проверьте дату на компьютере и настройки сети.",
    "timeout": "Загрузка заняла слишком много времени. Попробуйте ещё раз при устойчивом соединении.",
    "existing_invalid": "Файлы в кэше не прошли проверку. Они оставлены без изменений. Выберите готовую папку.",
}


class ModelInstallWorker(QThread):
    progress = pyqtSignal(int, int)

    def __init__(self, profile_root, parent):
        super().__init__(parent)
        self.profile_root = profile_root
        self.path = None
        self.failure = None
        self._cancelled = Event()

    def cancel(self):
        self._cancelled.set()

    def run(self):
        try:
            from candidates.story_model_install import (
                StoryModelInstallCancelled, StoryModelInstallError, install_story_model, profile_story_model_destination,
            )
            try:
                self.path = install_story_model(
                    profile_story_model_destination(self.profile_root),
                    on_progress=self.progress.emit,
                    cancelled=self._cancelled.is_set,
                )
            except StoryModelInstallCancelled:
                self.failure = "cancelled"
            except StoryModelInstallError as error:
                self.failure = error.code if error.code in _MODEL_INSTALL_HINTS else "failed"
        except Exception:
            self.failure = "failed"


class StorySearchView:
    def __init__(self, *, on_library_changed=lambda: None, on_open_settings=lambda: None, on_open_filters=lambda: None):
        self.widget = QWidget()
        self.widget.setObjectName("storyHome")
        from desktop.shared.story_posters import CardPosters
        self.posters = CardPosters(self.widget)
        self.widget.setStyleSheet(build_story_style())
        self._worker = None
        self._catalog_worker = None
        self._snapshot_worker = None
        self._snapshot_cancelled = False
        self._auth_dialog = None
        self._model_install_dialog = None
        self._model_install_worker = None
        self._model_install_cancelled = False
        self._model_install_success = False
        self._pending_query = None
        self._closing = False
        self._active_query = ""
        # Bind writes to the profile which owns this particular window. Env/CLI
        # is a process override, not a request to change the saved profile.
        self._model_preference = ProfileSetting(_MODEL_SETTING)
        self._model_install_profile = get_active_profile_root()
        self.model_dir = os.environ.get(_MODEL_ENV) or self._read_model_choice()
        self.seed_path = os.environ.get("WATCHBANE_STORY_SEED_CATALOG")
        self._seed_count = None
        self._snapshot_rows = None
        self._catalog_ready = False
        self._records = {}
        self.on_library_changed = on_library_changed
        root = QVBoxLayout(self.widget)
        root.setContentsMargins(layout_px(24), layout_px(24), layout_px(24), layout_px(24))
        root.setSpacing(layout_px(10))
        self.hero = QWidget()
        hero_layout = QHBoxLayout(self.hero)
        hero_layout.setContentsMargins(0, 0, 0, 0)
        hero_text = QVBoxLayout()
        self.heading = self._label(hero_text, "Какая история вам нужна?", "storyHeading")
        self.subtitle = self._label(hero_text, "Опишите героя, ситуацию или событие.")
        hero_layout.addLayout(hero_text, 1)
        from PyQt6.QtSvgWidgets import QSvgWidget
        self.mascot = QSvgWidget(str(Path(__file__).resolve().parents[1] / "images" / "story_ticket.svg"))
        self.mascot.setFixedSize(layout_px(160), layout_px(120))
        self.mascot.setAccessibleName("Кинобилет с лупой")
        hero_layout.addWidget(self.mascot)
        root.addWidget(self.hero)
        row = QHBoxLayout()
        self.query = QLineEdit()
        self.query.setObjectName("storyQuery")
        self.query.setPlaceholderText("Например: сериал про преступника")
        self.query.setMaxLength(600)
        row.addWidget(self.query, 1)
        self.search_button = QPushButton("Найти историю")
        self.search_button.setObjectName("storySearchButton")
        row.addWidget(self.search_button)
        self.text_search_button = QPushButton("Перейти на поиск по словам")
        self.text_search_button.clicked.connect(self._use_text_search)
        self.text_search_button.setVisible(bool(self.model_dir))
        text_mode_description = "Использовать поиск по словам и забыть папку модели в этом профиле."
        self.text_search_button.setToolTip(text_mode_description)
        self.text_search_button.setAccessibleDescription(text_mode_description)

        root.addLayout(row)
        self.examples = QWidget()
        examples_layout = QHBoxLayout(self.examples)
        examples_layout.setContentsMargins(0, 0, 0, 0)
        for example in ("побег из тюрьмы", "врач в больнице", "выживание в космосе"):
            button = QPushButton(example)
            button.setObjectName("storyExample")
            button.clicked.connect(self._example_callback(example))
            examples_layout.addWidget(button)
        examples_layout.addStretch()
        root.addWidget(self.examples)
        self.options = QWidget(self.widget)
        options_layout = QVBoxLayout(self.options)
        options_layout.setContentsMargins(0, 0, 0, 0)
        self.options.hide()
        source_row = QHBoxLayout()
        self.refresh_button = QPushButton("Обновить описания")
        self.refresh_button.clicked.connect(self._refresh_catalog)
        source_row.addWidget(self.refresh_button)
        options_layout.addLayout(source_row)
        model_row = QHBoxLayout()
        self.backend_label = QLabel("E5 выбрана · загрузится локально при поиске" if self.model_dir else "Базовый поиск: ограниченный словарь. Для поиска по смыслу подключите локальную E5.")
        self.backend_label.setWordWrap(True)
        model_row.addWidget(self.backend_label, 1)
        self.model_button = QPushButton("Подключить локальную E5…")
        self.model_button.clicked.connect(self._open_model_install)
        model_row.addWidget(self.model_button)
        options_layout.addLayout(model_row)
        navigation = QHBoxLayout()
        for title, callback in (("Настройки приложения", on_open_settings), ("Настройки рекомендаций", on_open_filters)):
            button = QPushButton(title)
            button.clicked.connect(callback)
            navigation.addWidget(button)
        options_layout.addLayout(navigation)
        import_row = QHBoxLayout()
        self.catalog_button = QPushButton("Заполнить каталог из TMDb")
        self.catalog_button.setObjectName("storyCatalogButton")
        self.catalog_button.clicked.connect(self._fill_catalog)
        import_row.addWidget(self.catalog_button)
        self.snapshot_button = QPushButton("Файл каталога…")
        self.snapshot_button.setObjectName("storySnapshotButton")
        self.snapshot_button.setAccessibleDescription("Использовать локальный JSONL только для поиска в этом сеансе.")
        self.snapshot_button.clicked.connect(self._choose_snapshot)
        self.snapshot_menu = QMenu(self.snapshot_button)
        self.snapshot_menu.addAction("Выбрать другой файл…", self._choose_snapshot)
        self.snapshot_menu.addAction("Вернуться к каталогу профиля", self._clear_snapshot)
        import_row.addWidget(self.snapshot_button)
        self.install_model_button = QPushButton("Подключить поиск по смыслу…")
        self.install_model_button.setObjectName("storyInstallModelButton")
        self.install_model_button.setAccessibleDescription("Скачайте модель или выберите готовую папку. Скачивание только после подтверждения.")
        self.install_model_button.clicked.connect(self._open_model_install)
        self.install_model_button.setVisible(not bool(self.model_dir))
        import_row.addWidget(self.install_model_button)
        import_row.addWidget(self.text_search_button)
        self.cancel_catalog_button = QPushButton("Отменить загрузку")
        self.cancel_catalog_button.clicked.connect(self._cancel_catalog)
        self.cancel_catalog_button.hide()
        import_row.addWidget(self.cancel_catalog_button)
        self.catalog_status = QLabel("")
        self.catalog_status.setWordWrap(True)
        import_row.addWidget(self.catalog_status, 1)
        root.addLayout(import_row)
        self.scope = self._label(root, self._model_scope(), "storyMuted")
        self.status = self._label(root, "")
        self._update_catalog_count()
        self._show_idle()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.cards = QWidget()
        self.cards_layout = QVBoxLayout(self.cards)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(layout_px(12))
        self.cards_layout.addStretch()
        scroll.setWidget(self.cards)
        root.addWidget(scroll, 1)
        self.search_button.clicked.connect(self.search)
        self.query.returnPressed.connect(self.search)
        self.focus_shortcut = QShortcut(QKeySequence("Ctrl+L"), self.widget)
        self.focus_shortcut.activated.connect(self._focus_query)
        self.escape_shortcut = QShortcut(QKeySequence("Escape"), self.widget)
        self.escape_shortcut.activated.connect(self._close_options)
        self.query.setAccessibleName("Какую историю вы ищете")
        QWidget.setTabOrder(self.query, self.search_button)
        QWidget.setTabOrder(self.search_button, self.catalog_button)
        QWidget.setTabOrder(self.catalog_button, self.snapshot_button)
        QWidget.setTabOrder(self.snapshot_button, self.install_model_button)
        QWidget.setTabOrder(self.install_model_button, self.text_search_button)
        self.query.setFocus()

    def _focus_query(self):
        self.query.setFocus()
        self.query.selectAll()

    def _close_options(self):
        self.query.setFocus()

    def _example_callback(self, example):
        def clicked(_checked=False):
            self.query.setText(example)
            self.search()
        return clicked

    def on_tab_activated(self):
        if self._snapshot_worker:
            return
        if self._catalog_worker is None:
            self._update_catalog_count()
        if self.query.text().strip() and self._worker is None and not self._closing:
            self.search()

    def _show_idle(self):
        self.status.setText(
            "Выберите пример запроса или опишите свой сюжет." if self._catalog_ready else
            "Загрузите описания из TMDb или откройте файл каталога. Можно набрать запрос заранее."
        )

    def _update_catalog_count(self, prefix=""):
        try:
            if self.seed_path:
                # Even if filters excluded every row last time, a replaced
                # snapshot must be retryable. Parsing stays off the UI thread.
                self._catalog_ready = True
                self.catalog_button.hide()
                label = "Только каталог из файла"
                if self._seed_count is not None:
                    label += f" · доступно: {self._seed_count}"
                elif self._snapshot_rows is not None:
                    label += f" · проверено записей: {self._snapshot_rows}"
                self.catalog_status.setText(prefix + label)
            else:
                documents, _ = service.story_catalog_snapshot()
                self._catalog_ready = bool(documents)
                self.catalog_button.setText("Пополнить из TMDb" if documents else "Заполнить каталог из TMDb")
                self.catalog_button.show()
                label = f"В каталоге: {len(documents)}" if documents else "Каталог пока пуст"
                self.catalog_status.setText(prefix + label)
        except Exception:
            self._catalog_ready = False
            self.catalog_status.setText(prefix + "Не удалось прочитать локальный каталог.")
        self.snapshot_button.setMenu(self.snapshot_menu if self.seed_path else None)
        self.examples.setEnabled(self._catalog_ready)
        self.search_button.setEnabled(self._catalog_ready and self._snapshot_worker is None)
        self.query.setPlaceholderText("Например: сериал про преступника" if self._catalog_ready else
                                      "Для поиска нужен каталог")

    def _can_switch_source(self):
        return not (self._closing or self._worker or self._catalog_worker or self._snapshot_worker)

    def _choose_snapshot(self):
        if not self._can_switch_source():
            return
        filename, _ = QFileDialog.getOpenFileName(
            self.widget, "Открыть локальный каталог Watchbane", "",
            "Каталог Watchbane JSONL (*.jsonl)",
        )
        if not filename:
            return
        if Path(filename).suffix.casefold() != ".jsonl":
            self._update_catalog_count("Выберите файл Watchbane в формате JSONL. ")
            return
        worker = SnapshotCheckWorker(filename, self.widget)
        self._snapshot_worker = worker
        self._snapshot_cancelled = False
        self.snapshot_button.setEnabled(False)
        self.catalog_button.setEnabled(False)
        self.search_button.setEnabled(False)
        self.examples.setEnabled(False)
        self.cancel_catalog_button.setEnabled(True)
        self.cancel_catalog_button.setText("Отменить проверку")
        self.cancel_catalog_button.show()
        self.catalog_status.setText("Проверяем локальный файл…")
        worker.finished.connect(self._snapshot_finished, Qt.ConnectionType.QueuedConnection)
        worker.start()

    def _snapshot_finished(self):
        worker, self._snapshot_worker = self._snapshot_worker, None
        if worker is None:
            return
        worker.deleteLater()
        if self._closing:
            return
        self.snapshot_button.setEnabled(True)
        self.catalog_button.setEnabled(True)
        self.cancel_catalog_button.hide()
        self.cancel_catalog_button.setText("Отменить загрузку")
        if self._snapshot_cancelled:
            self._update_catalog_count("Проверка отменена. ")
        elif worker.failure or not worker.count:
            self._update_catalog_count((worker.failure or "Файл каталога пуст.") + " ")
        else:
            self._switch_source(worker.path, worker.count)

    def _clear_snapshot(self):
        if self.seed_path and self._can_switch_source():
            self._switch_source(None, None)

    def _switch_source(self, path, count):
        self.seed_path, self._snapshot_rows = path, count
        self._seed_count = None
        if path and self._auth_dialog:
            self._auth_dialog.hide()
        self._active_query = ""
        self._records = {}
        self._clear()
        for widget in (self.hero, self.heading, self.subtitle, self.examples):
            widget.show()
        self._update_catalog_count()
        self.scope.setText(self._model_scope())
        self.status.setToolTip("")
        self._show_idle()
        self.query.setFocus()

    def _fill_catalog(self):
        if self._closing or self.seed_path or self._snapshot_worker or self._catalog_worker is not None:
            return
        from apis import tmdb_api
        if not tmdb_api.has_tmdb_credentials():
            if self._auth_dialog is None:
                from desktop.settings.tmdb_credentials_panel import TmdbCredentialsPanel
                self._auth_dialog = QDialog(self.widget)
                self._auth_dialog.setWindowTitle("TMDb · подключение каталога")
                layout = QVBoxLayout(self._auth_dialog)
                hint = QLabel("Ключ нужен только для загрузки фильмов и сериалов. После загрузки поиск по описаниям работает без интернета.")
                hint.setWordWrap(True); layout.addWidget(hint)
                panel = TmdbCredentialsPanel(self._auth_dialog)
                panel.credentialsChanged.connect(self._catalog_credentials_ready)
                layout.addWidget(panel)
                close = QPushButton("Вернуться к поиску")
                close.clicked.connect(self._auth_dialog.hide)
                layout.addWidget(close)
            self._auth_dialog.show()
            return
        from desktop.candidates.workers.filter_replenish_worker import FilterReplenishWorker
        worker = FilterReplenishWorker({}, service=service.StoryCatalogImportService, parent=self.widget)
        self._catalog_worker = worker
        self.snapshot_button.setEnabled(False)
        self.catalog_button.setEnabled(False)
        self.cancel_catalog_button.setEnabled(True)
        self.cancel_catalog_button.show()
        self.catalog_status.setText("Загружаем до 15 фильмов и 15 сериалов; сначала русский язык…")
        worker.progress.connect(lambda update: self.catalog_status.setText(update.get("message", "Загрузка…")))
        worker.finished_with_result.connect(self._catalog_result)
        worker.failed.connect(self._catalog_failed)
        worker.finished.connect(self._catalog_finished)
        worker.start()

    def _catalog_credentials_ready(self, ready):
        if ready and not self._closing:
            self._auth_dialog.hide()
            self._fill_catalog()

    def _cancel_catalog(self):
        if self._snapshot_worker:
            self._snapshot_cancelled = True
            self._snapshot_worker.requestInterruption()
            self.cancel_catalog_button.setEnabled(False)
            self.catalog_status.setText("Отменено. Завершаем чтение файла…")
        elif self._catalog_worker:
            self._catalog_worker.cancel()
            self.cancel_catalog_button.setEnabled(False)
            self.catalog_status.setText("Отменяем после текущего запроса. Существующая библиотека сохранится.")

    def _catalog_failed(self, _error):
        if not self._closing:
            self._update_catalog_count("Загрузка не удалась. Проверьте сеть и авторизацию TMDb; повторите попытку. ")

    def _catalog_result(self, result):
        if self._closing:
            return
        if result.get("cancelled"):
            self._update_catalog_count("Загрузка отменена; каталог не изменён. ")
            return
        if not result.get("ok"):
            self._catalog_failed("")
            return
        added = result.get("saved_count", 0)
        prefix = f"Добавлено: {added}. " if added else "Новых описаний в этой подборке нет. "
        self._update_catalog_count(prefix)
        self._show_idle()
        self.on_library_changed()
        if self.query.text().strip():
            self.search()

    def _catalog_finished(self):
        worker, self._catalog_worker = self._catalog_worker, None
        if worker:
            worker.deleteLater()
        self.catalog_button.setEnabled(True)
        self.snapshot_button.setEnabled(self._worker is None)
        self.cancel_catalog_button.hide()

    def _read_model_choice(self):
        try:
            directory = self._model_preference.read(_MODEL_UNSET)
        except (OSError, sqlite3.Error):
            return None
        if directory is _MODEL_UNSET:
            return _publisher_model_dir()
        # JSON null is an intentional choice, not an unset preference.
        return directory if isinstance(directory, str) and directory.strip() else None

    def _remember_model_choice(self):
        try:
            self._model_preference.write(self.model_dir)
        except (OSError, sqlite3.Error):
            self.status.setText("Режим выбран на этот запуск. Не удалось сохранить настройку профиля.")
            return False
        return True

    def _model_scope(self):
        return ("Поиск по смыслу · локальная E5 будет проверена при поиске" if self.model_dir else
                "Поиск по описаниям в вашем каталоге")

    def _update_model_controls(self, *, offer_replacement=False):
        self.install_model_button.setVisible(not self.model_dir or offer_replacement)
        self.text_search_button.setVisible(bool(self.model_dir))
        self.scope.setText("Поиск по смыслу недоступен" if self.model_dir and offer_replacement else self._model_scope())

    def _sync_model_actions(self):
        can_change = not (self._closing or self._worker or self._model_install_worker)
        for button in (self.model_button, self.text_search_button, self.install_model_button):
            button.setEnabled(can_change)
        if self._model_install_dialog is not None:
            self._install_confirm.setEnabled(can_change and self._install_runtime_available
                                             and not self._model_install_success)
            self._install_manual.setEnabled(can_change and self._install_runtime_available)

    def _open_model_install(self):
        if self._closing or self._worker:
            return
        if self._model_install_dialog is None:
            dialog = self._model_install_dialog = QDialog(self.widget)
            dialog.setWindowTitle("Модель поиска по смыслу")
            dialog.setMinimumWidth(layout_px(460))
            layout = QVBoxLayout(dialog)
            self._label(layout, "Один раз скачайте локальную модель E5 (~487 МБ) с Hugging Face, "
                                "из репозитория intfloat/multilingual-e5-small. После установки "
                                "поиск по локальному каталогу работает без интернета.")
            self._label(layout, "E5 ищет по смыслу, но не содержит описаний. Откройте файл каталога "
                                "или загрузите описания из TMDb.")
            self._label(layout, "Watchbane проверит файлы перед подключением. Ваши запросы и "
                                "коллекция не отправляются при установке.")
            self._install_status = self._label(layout, "")
            self._install_status.setObjectName("storyModelInstallStatus")
            self._install_progress = QProgressBar()
            self._install_progress.setAccessibleName("Ход установки модели E5")
            self._install_progress.hide()
            layout.addWidget(self._install_progress)
            self._install_confirm = QPushButton("Скачать и установить (~487 МБ)")
            self._install_confirm.clicked.connect(self._start_model_install)
            self._install_manual = QPushButton("Выбрать готовую папку…")
            self._install_manual.clicked.connect(self._choose_install_folder)
            self._install_cancel = QPushButton("Отменить загрузку")
            self._install_cancel.clicked.connect(self._cancel_model_install)
            self._install_cancel.hide()
            close = QPushButton("Закрыть")
            close.clicked.connect(dialog.reject)
            for button in (self._install_confirm, self._install_cancel, self._install_manual, close):
                button.setAutoDefault(False)  # Opening the dialog is not download consent.
                layout.addWidget(button)
            dialog.rejected.connect(self._cancel_model_install)
            self._install_runtime_available = _semantic_install_available()
            if not self._install_runtime_available:
                self._install_status.setText("Эта сборка поддерживает только поиск по словам. "
                                             "Для установки модели нужна сборка с поиском по смыслу.")
            self._sync_model_actions()
        self._model_install_dialog.show()
        self._model_install_dialog.raise_()
        self._install_manual.setFocus()

    def _choose_install_folder(self):
        if self._choose_model():
            self._model_install_dialog.accept()

    def _start_model_install(self):
        if (self._closing or self._worker or self._model_install_worker or self._model_install_success
                or self._model_install_dialog is None or not self._install_runtime_available):
            return
        worker = self._model_install_worker = ModelInstallWorker(self._model_install_profile, self.widget)
        self._model_install_cancelled = False
        self._install_progress.setRange(0, 0)
        self._install_progress.show()
        self._install_cancel.setEnabled(True)
        self._install_cancel.show()
        self._install_status.setText("Подготавливаем загрузку…")
        self._sync_model_actions()
        worker.progress.connect(self._update_install_progress, Qt.ConnectionType.QueuedConnection)
        worker.finished.connect(self._model_install_finished, Qt.ConnectionType.QueuedConnection)
        worker.start()

    def _update_install_progress(self, downloaded, total):
        if not self._model_install_worker or self._model_install_cancelled or self._closing or total <= 0:
            return
        self._install_progress.setRange(0, 100)
        self._install_progress.setValue(max(0, min(100, downloaded * 100 // total)))
        if downloaded >= total:
            self._install_status.setText("Проверяем файлы модели…")
        else:
            self._install_status.setText(f"Загружено {downloaded / 1_000_000:.0f} МБ.")

    def _cancel_model_install(self):
        if self._model_install_worker:
            self._model_install_cancelled = True
            self._model_install_worker.cancel()
            self._install_cancel.setEnabled(False)
            self._install_status.setText("Отменяем загрузку… Выбранный режим не изменится.")

    def _model_install_finished(self):
        worker, self._model_install_worker = self._model_install_worker, None
        if worker is None:
            return
        worker.deleteLater()
        if self._closing:
            return
        self._install_progress.hide()
        self._install_cancel.hide()
        if self._model_install_cancelled or worker.failure == "cancelled":
            self._install_status.setText("Установка отменена. Выбранный режим не изменился.")
        elif worker.failure or not worker.path:
            hint = _MODEL_INSTALL_HINTS.get(worker.failure, "Проверьте интернет и место на диске "
                                             "или выберите готовую папку.")
            self._install_status.setText(f"Не удалось установить модель. {hint} Выбранный режим не изменился.")
        else:
            self.model_dir = str(worker.path)
            self._model_install_success = True
            self._update_model_controls()
            self.backend_label.setText("Локальная E5 установлена. Она подключится при следующем поиске.")
            saved = self._remember_model_choice()
            self._install_status.setText("Модель проверена и подключится при следующем поиске." if saved else
                                         "Модель проверена. Подключение сохранено только на этот запуск.")
        self._sync_model_actions()

    def _choose_model(self):
        if self._closing or self._worker or self._model_install_worker:
            return False
        directory = QFileDialog.getExistingDirectory(self.widget, "Папка проверенной multilingual-e5-small (скачивание не выполняется)")
        if directory:
            self.model_dir = directory
            self._update_model_controls()
            self.backend_label.setText("E5 выбрана. Файлы будут проверены при следующем поиске; ничего не скачивается.")
            self._remember_model_choice()
            return True
        return False

    def _use_text_search(self):
        if self._model_install_worker:
            return
        self.model_dir = None
        self._model_install_success = False
        self._update_model_controls()
        self._sync_model_actions()
        self.search()
        self._remember_model_choice()

    def _label(self, layout, text, name=""):
        label = QLabel(text)
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setWordWrap(True)
        label.setObjectName(name)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(label)
        return label

    def _clear(self):
        self.posters.clear()
        while self.cards_layout.count() > 1:
            item = self.cards_layout.takeAt(0)
            item.widget().setParent(None)
            item.widget().deleteLater()

    def _refresh_catalog(self):
        service.clear_story_search_cache()
        if self.query.text().strip():
            self.search()
        else:
            self.status.setText("Описания будут обновлены при следующем поиске.")

    def search(self):
        if self._closing or self._snapshot_worker:
            return
        if self._worker is not None:
            self._pending_query = self.query.text()
            self.status.setText("Текущий поиск ещё работает. Следующим выполним новый запрос.")
            return
        self._active_query = self.query.text()
        compact = bool(self._active_query.strip()) and self._catalog_ready
        self.hero.setVisible(not compact)
        self.heading.setVisible(not compact)
        self.subtitle.setVisible(not compact)
        self.examples.setVisible(not compact)
        self._clear()
        if not compact:
            self._show_idle()
            return
        self.status.setText("Ищем совпадения в описаниях…")
        self.search_button.setText("Следующий запрос")
        self.refresh_button.setEnabled(False)
        self.snapshot_button.setEnabled(False)
        self._worker = StoryWorker(self._active_query, self.widget, self.model_dir, self.seed_path)
        self._sync_model_actions()
        self._worker.completed.connect(self._show_results)
        self._worker.progress.connect(self.status.setText)
        self._worker.failed.connect(self._search_failed)
        self._worker.snapshot_failed.connect(self._snapshot_search_failed)
        self._worker.finished.connect(self._finished)
        self._worker.start()

    def _snapshot_search_failed(self):
        self._seed_count = self._snapshot_rows = None
        self._update_catalog_count()
        self.status.setText("Файл каталога недоступен или повреждён. Откройте меню «Файл каталога…», "
                            "чтобы выбрать другой файл или вернуться к каталогу профиля.")

    def _search_failed(self):
        if self._worker is None or self._worker.model_dir == self.model_dir:
            self._update_model_controls(offer_replacement=True)
        self.status.setText("Не удалось открыть описания или модель. Подключите локальную модель или повторите поиск; библиотека не изменена.")

    def _finished(self):
        worker, self._worker = self._worker, None
        if worker:
            worker.deleteLater()
        self.search_button.setText("Найти историю")
        self.search_button.setEnabled(self._catalog_ready and self._snapshot_worker is None)
        self.refresh_button.setEnabled(True)
        self.snapshot_button.setEnabled(self._catalog_worker is None)
        self._sync_model_actions()
        self.query.setEnabled(True)
        if not self._closing and self._pending_query is not None:
            pending, self._pending_query = self._pending_query, None
            self.query.setText(pending)
            self.search()

    def _show_results(self, response, records, count):
        if self._closing or self._pending_query is not None:
            return
        self._records = records
        if self.seed_path:
            self._seed_count = count
            self._update_catalog_count()
        self.backend_label.setText(response.backend)
        if self.seed_path and not count:
            self.status.setText("В этом файле нет доступных описаний. Можно повторить поиск после обновления "
                                "файла, выбрать другой или вернуться к каталогу профиля.")
        else:
            self.status.setText(f"{len(response.hits)} возможных совпадений · {count} описаний" if response.hits else (response.notice or "Совпадений нет. Попробуйте другой запрос."))
        self.status.setToolTip(response.notice or "Сходство по описанию не подтверждает каждое сюжетное условие.")
        self.scope.setText(
            "Поиск по смыслу · результаты могут совпадать только частично" if "E5" in response.backend else
            "Поиск по словам · для поиска по смыслу подключите модель"
        )
        try:
            states = get_title_states({
                hit.document.key: records[hit.document.key]
                for hit in response.hits if hit.document.key in records
            })
        except Exception:
            states = {}
            self.status.setText("Не удалось прочитать статусы коллекции.")
        for hit in response.hits:
            doc = hit.document
            card = QFrame()
            card.setObjectName("storyCard")
            shell = QHBoxLayout(card)
            shell.setContentsMargins(*[layout_px(14)] * 4)
            shell.setSpacing(layout_px(14))
            poster = self._poster(doc)
            shell.addWidget(poster, 0, Qt.AlignmentFlag.AlignTop)
            body = QWidget()
            body.setObjectName("storyCardBody")
            layout = QVBoxLayout(body)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(layout_px(6))
            shell.addWidget(body, 1)
            self._label(layout, doc.title, "storyTitle")
            metadata = ["Сериал" if doc.media_type == "tv" else "Фильм"]
            if doc.year: metadata.append(str(doc.year))
            metadata.append("Локальный каталог")
            if "английский fallback" in doc.source: metadata.append("Английский fallback")
            self._label(layout, " · ".join(metadata), "storyMuted")
            excerpt = self._label(layout, "Из описания: «" + hit.evidence + "»", "storyEvidence")
            details = QWidget()
            details.setObjectName("storyDetails")
            details_layout = QVBoxLayout(details)
            details_layout.setContentsMargins(0, 0, 0, 0)
            self._label(details_layout, doc.overview)
            self._label(details_layout, doc.source, "storyMuted")
            details.hide()
            layout.addWidget(details)
            actions = QHBoxLayout()
            more = QPushButton("Полный сюжет")
            more.setCheckable(True)

            def toggle_details(expanded, *, panel=details, preview=excerpt, button=more, title=doc.title):
                text = "Свернуть сюжет" if expanded else "Полный сюжет"
                panel.setVisible(expanded)
                preview.setVisible(not expanded)
                button.setText(text)
                button.setAccessibleName(f"{text}: {title}")

            toggle_details(False)
            more.toggled.connect(toggle_details)
            save = QPushButton("Сохранить")
            save.setObjectName("storySaveAction")
            save.setAccessibleName("Сохранить: " + doc.title)
            save.clicked.connect(self._action_callback(doc, card, "saved", save, more))
            if states.get(doc.key) == STATE_WATCHLIST:
                self._mark_card_saved(save, doc.title)
            actions.addWidget(save)
            actions.addWidget(more)
            watched = QPushButton("Смотрел")
            watched.clicked.connect(self._action_callback(doc, card, "watched"))
            actions.addWidget(watched)
            hide = QPushButton("Скрыть")
            hide.clicked.connect(self._action_callback(doc, card, "hidden"))
            actions.addWidget(hide)
            actions.addStretch()
            layout.addLayout(actions)
            self.cards_layout.insertWidget(self.cards_layout.count() - 1, card)

    def _poster(self, doc):
        label = QLabel("СЕРИАЛ\n\nБез постера" if doc.media_type == "tv" else "ФИЛЬМ\n\nБез постера")
        label.setObjectName("storyPoster")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setFixedSize(layout_px(68), layout_px(94))
        label.setAccessibleName("Постер недоступен")
        candidate = self._records.get(doc.key)
        if candidate:
            self.posters.bind(label, candidate, doc.title)
        return label

    @staticmethod
    def _mark_card_saved(button, title):
        button.setText("В коллекции")
        button.setAccessibleName("В коллекции: " + title)
        button.setEnabled(False)

    def _action_callback(self, doc, card, action, save_button=None, details_button=None):
        def clicked(_checked=False):
            self._act(doc, card, action, save_button, details_button)
        return clicked

    def _act(self, doc, card, action, save_button=None, details_button=None):
        candidate = self._records[doc.key]
        if action == "watched" and QMessageBox.question(self.widget, "Отметить просмотренным?", doc.title) != QMessageBox.StandardButton.Yes:
            return
        try:
            if action == "watched":
                service.mark_story_watched(candidate)
            elif action == "saved":
                result = service.add_candidate_to_watchlist(candidate)
                if not result.get("ok") or result.get("state") != STATE_WATCHLIST:
                    self.status.setText("Не удалось добавить в сохранённое. Проверьте статус в коллекции.")
                    return
            else:
                service.hide_candidate(candidate)
        except Exception:
            self.status.setText("Не удалось сохранить действие. Карточка остаётся на месте.")
            return
        if action == "saved":
            if save_button.hasFocus():
                details_button.setFocus(Qt.FocusReason.OtherFocusReason)
            self._mark_card_saved(save_button, doc.title)
            self.status.setText("Сохранено в коллекцию. Результаты поиска остались на месте.")
            self.on_library_changed()
            return
        self.on_library_changed()
        self._update_catalog_count()
        self.cards_layout.removeWidget(card)
        card.setParent(None)
        card.deleteLater()
        self.status.setText("Карточка убрана. Для нового поиска нажмите «Найти историю».")

    def prepare_for_shutdown(self):
        self.posters.clear()
        self._closing = True
        self._pending_query = None
        if self._catalog_worker:
            self._catalog_worker.cancel()
        if self._snapshot_worker:
            self._snapshot_worker.requestInterruption()
        if self._auth_dialog:
            self._auth_dialog.hide()
        if self._model_install_worker:
            self._model_install_worker.cancel()
        if self._model_install_dialog:
            self._model_install_dialog.hide()
        if self._worker:
            self._worker.cancel()
            self._worker.requestInterruption()
