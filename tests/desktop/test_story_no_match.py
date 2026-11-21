from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QPushButton
import pytest

from candidates import service, story_service
from candidates.story_search import OUT_OF_SCOPE_NOTICE, StoryDocument, StoryHit, StoryResponse
from desktop.story import view as story_view
from desktop.story.view import StorySearchView


@pytest.fixture
def plot_view(qtbot, monkeypatch):
    rows = [{"title": "Локальная история", "year": 2025, "media_type": "movie",
             "tmdb_id": 99117, "overview": "Преступник планирует ограбление.", "source": "synthetic"}]
    monkeypatch.setattr(story_service, "get_pool_view", lambda: rows)
    view = StorySearchView()
    qtbot.addWidget(view.widget)
    view.widget.resize(1100, 850)
    view.widget.show()
    yield view, rows
    view.prepare_for_shutdown()


def _submit(qtbot, view, query):
    view.query.setText(query)
    qtbot.keyClick(view.query, Qt.Key.Key_Return)
    qtbot.waitUntil(lambda: view._worker is None, timeout=10000)


def test_no_match_prompts_for_one_plot_clue_without_erasing_draft(qtbot, plot_view):
    view, _ = plot_view
    draft = "космонавт"
    _submit(qtbot, view, draft)
    assert view.status.text().endswith("Какое необычное событие вы помните?")
    assert view.query.text() == draft
    assert not view.cards.findChildren(QLabel, "storyTitle")
    _submit(qtbot, view, draft + " планирует ограбление")
    assert [card.text() for card in view.cards.findChildren(QLabel, "storyTitle")] == ["Локальная история"]


@pytest.mark.parametrize(("query", "notice"), [
    ("сериал 1999 про ограбление", "Попробуйте убрать год или тип."),
    ("Как мне обновить драйвер на ноутбуке", OUT_OF_SCOPE_NOTICE),
    ("без убийств", "Отрицания пока не поддерживаются."),
])
def test_specific_notices_do_not_ask_for_plot_clue(qtbot, plot_view, query, notice):
    view, _ = plot_view
    _submit(qtbot, view, query)
    assert notice in view.status.text()
    assert "Какое необычное событие" not in view.status.text()
    assert view.query.text() == query


@pytest.mark.parametrize(("source", "notice"), [
    (None, "Для поиска в профиле нет доступных описаний"),
    ("local.jsonl", "В этом файле нет доступных описаний"),
])
def test_empty_result_catalog_takes_priority_over_clue(plot_view, source, notice):
    view, rows = plot_view
    rows.clear()
    view.seed_path = source
    view.query.setText("хочу продолжить")
    view._show_results(StoryResponse((), reason="no_match"), {}, 0)
    assert notice in view.status.text()
    assert "Какое необычное событие" not in view.status.text()
    assert view.query.text() == "хочу продолжить"



def test_no_result_profile_reread_error_preserves_recovery(plot_view, monkeypatch):
    view, _ = plot_view
    def unavailable(*_args, **_kwargs):
        raise OSError("disposable fixture read fails")
    monkeypatch.setattr(service, "story_catalog_snapshot", unavailable)
    view._show_results(StoryResponse(()), {}, 0)
    assert view.retry_catalog_button.isVisible()
    assert "Повторите чтение каталога профиля" in view.status.text()


@pytest.mark.parametrize("semantic", [True, False])
def test_cards_frame_e5_as_options_and_preserve_card_order_and_actions(
    qtbot, plot_view, monkeypatch, semantic
):

    view, _ = plot_view
    monkeypatch.setattr(story_view, "get_title_states", lambda records: {})
    documents = (
        StoryDocument("movie:2", "Первый вариант", "Описание первого.", "movie", "synthetic"),
        StoryDocument("tv:1", "Второй вариант", "Описание второго.", "tv", "synthetic"),
    )
    response = StoryResponse(tuple(StoryHit(doc, score, doc.overview)
                                   for doc, score in zip(documents, (0.8, 0.7))))
    if semantic:
        from dataclasses import replace

        response = replace(response, backend="Локальная E5")
    view._show_results(response, {doc.key: {} for doc in documents}, 23)

    if semantic:
        assert view.status.text() == "Варианты из каталога: 2 · описаний: 23"
        assert view.scope.isVisible()
        assert view.scope.text() == "Поиск по смыслу · подходящего фильма или сериала среди вариантов может не быть"
    else:
        assert view.status.text() == "2 возможных совпадений · 23 описаний"
        assert view.scope.text() == "Поиск по словам · для поиска по смыслу подключите модель"
    assert view.backend_label.text() == response.backend
    assert [card.text() for card in view.cards.findChildren(QLabel, "storyTitle")] == [
        "Первый вариант", "Второй вариант",
    ]
    saves = view.cards.findChildren(QPushButton, "storySaveAction")
    assert [button.accessibleName() for button in saves] == [
        "Сохранить: Первый вариант", "Сохранить: Второй вариант",
    ]
    assert all(button.isEnabled() for button in saves)
    details = next(button for button in view.cards.findChildren(QPushButton)
                   if button.accessibleName() == "Полный сюжет: Первый вариант")
    qtbot.mouseClick(details, Qt.MouseButton.LeftButton)
    assert details.accessibleName() == "Свернуть сюжет: Первый вариант"


def test_e5_without_cards_keeps_no_match_prompt(plot_view):
    view, _ = plot_view
    view._show_results(StoryResponse((), backend="Локальная E5", reason="no_match"), {}, 1)
    assert view.status.text() == (
        "В доступных описаниях совпадений не найдено. Какое необычное событие вы помните?"
    )
    assert view.scope.text() == "Поиск по смыслу · результаты могут совпадать только частично"
