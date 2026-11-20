"""Offline concept retrieval followed by plot/role reranking. No I/O or models.

A deliberately bounded semantic vocabulary, NOT general language understanding.
Providers can replace retrieval without changing result provenance or the UI.
"""
from __future__ import annotations
from dataclasses import dataclass
from difflib import SequenceMatcher
import re
from typing import Protocol, Sequence

CONCEPTS = {
    "criminal": ("преступ", "бандит", "вор", "воров", "грабит", "мошен", "криминаль", "ограблен"),
    "investigator": ("следоват", "сыщик", "детектив", "полицей", "расслед", "раскрыва", "фбр", "агент"),
    "escape": ("побег", "сбеж", "бежит", "выбрат", "сбега", "покинуть"),
    "prison": ("тюрьм", "заключен", "колони", "решетк"),
    "space": ("космос", "космич", "астронавт", "космонавт", "планет", "орбит", "звездолет"),
    "survival": ("выжив", "спаст", "спасени", "катастроф", "крушени"),
    "family": ("семь", "семейн", "родител", "дочер", "сын", "матер", "мать", "отец"),
    "time": ("времен", "прошл", "будущ", "петл", "повторяет", "повторяющ"),
    "medicine": ("врач", "доктор", "хирург", "больниц", "лечит", "пациент"),
    "memory": ("памят", "амнези", "вспом", "забыл"),
    "identity": ("личност", "чужим", "самозван", "выдает"),
    "revenge": ("месть", "мстит", "отомст", "возмезди"),
    "war": ("войн", "военн", "солдат", "фронт"),
    "love": ("любов", "влюб", "роман", "отношени"),
    "sea": ("мор", "океан", "корабл", "остров", "моряк"),
    "school": ("школ", "учител", "ученик", "подрост"),
    "music": ("музык", "пев", "групп", "концерт", "пианист"),
    "sport": ("спорт", "тренер", "боксер", "команд", "турнир"),
}
ROLE_WORDS = {
    "criminal": {"преступник", "вор", "воровка", "бандит", "мошенник", "грабитель"},
    "investigator": {"следователь", "сыщик", "детектив", "полицейский", "следователи", "сыщики", "полицейские", "агент", "агенты"},
    "medicine": {"врач", "доктор", "хирург"},
}
STOP = set("я хочу найти смотреть история истории про о об где как и в на с по для а но это который которая его ее он она сериал сериалы фильм фильмы кино мне пожалуйста героя герой жизнь".split())


def tokens(text: str) -> list[str]:
    return re.findall(r"[а-яa-z0-9]+", text.casefold().replace("ё", "е"))


def concepts(words: Sequence[str], *, fuzzy: bool = False) -> frozenset[str]:
    result = set()
    for word in words:
        direct = {key for key, roots in CONCEPTS.items() if any(word.startswith(root) for root in roots)}
        result.update(direct)
        if fuzzy and not direct and len(word) >= 7:
            # Bounded fuzzy concept correction, not a query-specific substitution.
            matches = [(SequenceMatcher(None, word, root).ratio(), key)
                       for key, roots in CONCEPTS.items() for root in (*roots, *ROLE_WORDS.get(key, ())) if len(root) >= 6]
            score, key = max(matches, default=(0, ""))
            if score >= .72:
                result.add(key)
    return frozenset(result)


@dataclass(frozen=True)
class StoryDocument:
    key: str
    title: str
    overview: str
    media_type: str
    source: str
    demo: bool = False
    year: int | None = None


@dataclass(frozen=True)
class StoryHit:
    document: StoryDocument
    score: float
    evidence: str


@dataclass(frozen=True)
class StoryResponse:
    hits: tuple[StoryHit, ...]
    notice: str = ""
    backend: str = "Базовый поиск · словарный fallback"


def unsupported_negation(query: str) -> bool:
    words = tokens(query)
    if set(words) & {"без", "кроме", "никаких", "никакого", "никакой", "исключая", "исключить", "нет"}:
        return True
    # Third-person narrative predicates describe what happens in a story.
    # Keep the finite grammar conservative: an unfamiliar negation may still
    # be an unsupported request to exclude films, themes, or genres.
    plot_verbs = {
        "может", "мог", "могут", "помнит", "помнят", "знает", "знают", "умеет",
        "понимает", "получается", "заканчивается", "удается", "успевает",
        "узнает", "узнают", "узнал", "узнала", "узнали",
        "возвращается", "возвращаются", "вернулся", "вернулась", "вернулись",
    }
    return any(w == "не" and (i+1 == len(words) or words[i+1] not in plot_verbs)
               for i, w in enumerate(words))


def media_constraints(query: str):
    words = tokens(query)
    tv = any(w.startswith("сериал") for w in words)
    movie = any(w.startswith("фильм") for w in words)
    kind = "tv" if tv and not movie else "movie" if movie and not tv else None
    match = re.search(r"(?:фильм|сериал)\s+((?:19|20)\d{2})\b|(?:год выпуска|вышел в|выпущен в)\s+((?:19|20)\d{2})\b", query.casefold())
    year = int(next(g for g in match.groups() if g)) if match else None
    return kind, year


class Retriever(Protocol):
    def retrieve(self, query: str, documents: Sequence[StoryDocument], limit: int) -> list[tuple[StoryDocument, float]]: ...


def lexical_score(query: str, text: str) -> float:
    q = set(tokens(query)) - STOP
    d = set(tokens(text))
    return len(q & d) / max(1, len(q))


class ConceptRetriever:
    """Recall stage: union of lexical and concept matches; no role filtering."""
    def retrieve(self, query, documents, limit=80):
        q = concepts(tokens(query), fuzzy=True)
        rows = []
        for doc in documents:
            d = concepts(tokens(doc.overview))
            overlap = len(q & d) / max(1, len(q))
            score = overlap + .25 * lexical_score(query, doc.overview)
            if score > 0:
                rows.append((doc, score))
        return sorted(rows, key=lambda row: (-row[1], row[0].key))[:limit]


def requested_protagonist(query: str) -> str | None:
    """Explicit person noun, not a topic such as 'расследование' or 'ограбление'."""
    for word in tokens(query):
        for role, forms in ROLE_WORDS.items():
            if word in forms or any(len(form) >= 5 and word.startswith(form[:-1]) for form in forms):
                return role
        if word in {"вора", "вору", "вором", "воры", "воров"}:
            return "criminal"
    return None


def protagonist(text: str) -> str | None:
    # Only unambiguous nominative role nouns in the first sentence are used.
    first = re.split(r"[.!?]", text)[0]
    roles = {role for word in tokens(first) for role, forms in ROLE_WORDS.items() if word in forms}
    return next(iter(roles)) if len(roles) == 1 else None


class StorySearch:
    def __init__(self, documents: Sequence[StoryDocument], retriever: Retriever | None = None):
        self.documents = tuple(documents)
        self.retriever = retriever or ConceptRetriever()

    def search(self, query: str, *, excluded: frozenset[str] = frozenset(), limit: int = 5) -> StoryResponse:
        words = tokens(query)
        if len(query) > 600:
            return StoryResponse((), "Сократите описание до 600 символов.")
        if not (set(words) - STOP):
            return StoryResponse((), "Опишите героя или событие: например, побег из тюрьмы.")
        if unsupported_negation(query):
            return StoryResponse((), "Отрицания пока не поддерживаются. Опишите желаемую историю утвердительно.")
        kind, year = media_constraints(query)
        docs = [d for d in self.documents if d.key not in excluded and (kind is None or d.media_type == kind) and (year is None or d.year == year)]
        q = concepts(words, fuzzy=True)
        # "следователь ловит преступника" selects the first role in the query.
        requested_role = next((next(iter(c & ROLE_WORDS.keys())) for w in words
                               if (c := concepts([w], fuzzy=True)) & ROLE_WORDS.keys()), None)
        hits = []
        for doc, recall_score in self.retriever.retrieve(query, docs, max(80, len(docs))):
            d = concepts(tokens(doc.overview))
            coverage = len(q & d) / max(1, len(q))
            if (q and coverage < .5) or (not q and lexical_score(query, doc.overview) < .6):
                continue
            role = protagonist(doc.overview)
            role_score = 0
            if requested_role:
                role_score = .8 if role == requested_role else -.7 if role else -.2
            score = recall_score + coverage + role_score
            if score <= 0:
                continue
            sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", doc.overview) if s.strip()]
            evidence = max(sentences, key=lambda s: len(q & concepts(tokens(s))), default=doc.overview)
            hits.append(StoryHit(doc, round(score, 6), evidence))
        hits.sort(key=lambda hit: (-hit.score, hit.document.key))
        return StoryResponse(tuple(hits[:max(0, min(limit, 10))]), "" if hits else "Совпадений нет. Попробуйте другой сюжет или добавьте локальные описания.")
