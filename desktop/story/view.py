"""Search-first Qt home; original library/title search remain separate tabs."""
import os
from threading import Event

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QShortcut, QKeySequence
from pathlib import Path
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                            QPushButton, QScrollArea, QFrame, QMessageBox, QFileDialog, QDialog)
from candidates import service
from candidates.title_state_service import STATE_WATCHLIST, get_title_states
from desktop.theme.scaling import layout_px
from desktop.theme.layout import MAIN_TAB_PANE_TOP_LIFT
from desktop.theme.styles.story import build_story_style


class StoryWorker(QThread):
    completed = pyqtSignal(object, object, int)
    failed = pyqtSignal()
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
        try:
            engine, records = service.local_story_catalog(
                self.model_dir, on_progress=self.progress.emit,
                cancelled=self._cancelled.is_set, seed_path=self.seed_path)
            if self._cancelled.is_set():
                return
            self.progress.emit("Ищем совпадения в каталоге…")
            result = engine.search(self.query)
            self.completed.emit(result, records, len(engine.documents))
        except Exception:
            self.failed.emit()


class StorySearchView:
    def __init__(self, *, on_library_changed=lambda: None, on_open_settings=lambda: None, on_open_filters=lambda: None):
        self.widget = QWidget()
        self.widget.setObjectName("storyHome")
        from desktop.shared.story_posters import CardPosters
        self.posters = CardPosters(self.widget)
        self.widget.setStyleSheet(build_story_style())
        self._worker = None
        self._catalog_worker = None
        self._auth_dialog = None
        self._pending_query = None
        self._closing = False
        self._active_query = ""
        self.model_dir = os.environ.get("WATCHBANE_STORY_MODEL_DIR")
        self.seed_path = os.environ.get("WATCHBANE_STORY_SEED_CATALOG")
        self._seed_count = None
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
        self.options_button = QPushButton("Подключить поиск по смыслу…")
        self.options_button.setVisible(not bool(self.model_dir))
        self.options_button.setAccessibleName("Подключить локальную модель поиска")
        self.text_search_button = QPushButton("Искать по словам")
        self.text_search_button.clicked.connect(self._use_text_search)
        self.text_search_button.hide()

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
        self.options_button.clicked.connect(self._choose_model)
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
        self.model_button.clicked.connect(self._choose_model)
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
        import_row.addWidget(self.options_button)
        import_row.addWidget(self.text_search_button)
        self.cancel_catalog_button = QPushButton("Отменить загрузку")
        self.cancel_catalog_button.clicked.connect(self._cancel_catalog)
        self.cancel_catalog_button.hide()
        import_row.addWidget(self.cancel_catalog_button)
        self.catalog_status = QLabel("")
        self.catalog_status.setWordWrap(True)
        import_row.addWidget(self.catalog_status, 1)
        root.addLayout(import_row)
        self.scope = self._label(root, "Поиск по описаниям в вашем каталоге", "storyMuted")
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
        QWidget.setTabOrder(self.catalog_button, self.options_button)
        self.query.setFocus()

    def _focus_query(self):
        self.query.setFocus()
        self.query.selectAll()

    def _close_options(self):
        self.options_button.setChecked(False)
        self.query.setFocus()

    def _example_callback(self, example):
        def clicked(_checked=False):
            self.query.setText(example)
            self.search()
        return clicked

    def on_tab_activated(self):
        if self._catalog_worker is None:
            self._update_catalog_count()
        if self.query.text().strip() and self._worker is None and not self._closing:
            self.search()

    def _show_idle(self):
        self.status.setText(
            "Выберите пример запроса или опишите свой сюжет." if self._catalog_ready else
            "Загрузите первые фильмы и сериалы из TMDb, чтобы начать поиск."
        )

    def _update_catalog_count(self, prefix=""):
        try:
            if self.seed_path:
                # Parsing thousands of rows stays in the search thread.
                self._catalog_ready = self._seed_count is None or self._seed_count > 0
                self.catalog_button.hide()
                label = "Каталог из файла подключён" if self._seed_count is None else f"В каталоге: {self._seed_count}"
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
        self.examples.setEnabled(self._catalog_ready)

    def _fill_catalog(self):
        if self._closing or self._catalog_worker is not None:
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
        if self._catalog_worker:
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
        self.cancel_catalog_button.hide()

    def _choose_model(self):
        directory = QFileDialog.getExistingDirectory(self.widget, "Папка проверенной multilingual-e5-small (скачивание не выполняется)")
        if directory:
            self.model_dir = directory
            self.options_button.hide()
            self.text_search_button.hide()
            self.backend_label.setText("E5 выбрана. Файлы будут проверены при следующем поиске; ничего не скачивается.")

    def _use_text_search(self):
        self.model_dir = None
        self.text_search_button.hide()
        self.options_button.show()
        self.search()

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
        if self._closing:
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
        self.options_button.setChecked(False)
        self._clear()
        if not compact:
            self._show_idle()
            if self._active_query.strip() and self.catalog_button.isVisible():
                self.catalog_button.setFocus()
            return
        self.status.setText("Ищем совпадения в описаниях…")
        self.search_button.setText("Следующий запрос")
        self.refresh_button.setEnabled(False)
        self.model_button.setEnabled(False)
        self._worker = StoryWorker(self._active_query, self.widget, self.model_dir, self.seed_path)
        self._worker.completed.connect(self._show_results)
        self._worker.progress.connect(self.status.setText)
        self._worker.failed.connect(self._search_failed)
        self._worker.finished.connect(self._finished)
        self._worker.start()

    def _search_failed(self):
        self.options_button.show()
        self.text_search_button.setVisible(bool(self.model_dir))
        self.status.setText("Не удалось открыть описания или модель. Подключите локальную модель или повторите поиск; библиотека не изменена.")

    def _finished(self):
        worker, self._worker = self._worker, None
        if worker:
            worker.deleteLater()
        self.search_button.setText("Найти историю")
        self.search_button.setEnabled(True)
        self.refresh_button.setEnabled(True)
        self.model_button.setEnabled(True)
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
        if self._auth_dialog:
            self._auth_dialog.hide()
        if self._worker:
            self._worker.cancel()
            self._worker.requestInterruption()
