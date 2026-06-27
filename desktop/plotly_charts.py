"""Plotly chart builders for read-only desktop analytics."""

from __future__ import annotations

from html import escape

from desktop.theme import (
    COLOR_ACCENT,
    COLOR_ACCENT_PLOT_FILL,
    COLOR_ACCENT_PLOT_HOVER,
    COLOR_BORDER,
    COLOR_CARD,
    COLOR_CARD_ALT,
    COLOR_SURFACE,
    COLOR_TEXT,
    COLOR_TEXT_SECONDARY,
    FONT_FAMILY,
    FONT_FAMILY_FALLBACK,
)

CHART_BG = COLOR_CARD
PLOT_BG = COLOR_SURFACE
TEXT_COLOR = COLOR_TEXT
MUTED_TEXT = COLOR_TEXT_SECONDARY
GRID_COLOR = COLOR_BORDER
BAR_COLOR = COLOR_ACCENT
BAR_HOVER_COLOR = COLOR_ACCENT_PLOT_HOVER
PLOT_FONT_FAMILY = f"{FONT_FAMILY}, {FONT_FAMILY_FALLBACK}"

CHART_BASE_HEIGHT = 280
SCORE_CHART_HEIGHT = CHART_BASE_HEIGHT
SCORE_DISTRIBUTION_CHART_HEIGHT = CHART_BASE_HEIGHT
GENRE_COUNT_CHART_HEIGHT = CHART_BASE_HEIGHT
YEAR_AVERAGE_CHART_HEIGHT = CHART_BASE_HEIGHT
IMDB_DELTA_CHART_HEIGHT = CHART_BASE_HEIGHT

CHART_BAR_ROW_HEIGHT = 24
CHART_BAR_MIN_HEIGHT = 120
CHART_MARGIN_DEFAULT = {"l": 48, "r": 12, "t": 4, "b": 48}
CHART_MARGIN_HBAR = {"l": 132, "r": 12, "t": 4, "b": 40}
CHART_FONT_SIZE = 12
CHART_AXIS_TITLE_SIZE = 11

IMDB_DELTA_NEGATIVE_COLOR = "#9f6b6b"
IMDB_DELTA_CHART_TITLE_LIMIT = 28


def bar_chart_height(row_count: int, *, base: int = CHART_BASE_HEIGHT) -> int:
    """Compute Plotly height for horizontal bar charts from row count."""
    if row_count <= 0:
        return base
    return max(base, CHART_BAR_MIN_HEIGHT + row_count * CHART_BAR_ROW_HEIGHT)


def _hoverlabel_style() -> dict:
    return {
        "bgcolor": COLOR_CARD_ALT,
        "bordercolor": GRID_COLOR,
        "font": {"color": TEXT_COLOR, "size": CHART_FONT_SIZE},
    }


def _apply_chart_layout(
    fig,
    *,
    height: int,
    margin: dict | None = None,
    bargap: float | None = None,
) -> None:
    fig.update_layout(
        paper_bgcolor=CHART_BG,
        plot_bgcolor=PLOT_BG,
        font={"color": TEXT_COLOR, "family": PLOT_FONT_FAMILY, "size": CHART_FONT_SIZE},
        height=height,
        margin=margin or CHART_MARGIN_DEFAULT,
        hoverlabel=_hoverlabel_style(),
    )
    if bargap is not None:
        fig.update_layout(bargap=bargap)


def _plotly_html_page(chart: str, height: int) -> str:
    return f"""
<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        html, body {{
            margin: 0;
            padding: 0;
            background: {PLOT_BG};
            overflow: hidden;
            min-height: {height}px;
        }}
        .plotly-graph-div {{
            width: 100% !important;
        }}
    </style>
</head>
<body>
{chart}
</body>
</html>
"""


def _format_hover(row: dict) -> str:
    title_line = escape(str(row["label"]))
    count_line = f"{int(row['count'])} тайтлов · {float(row['percent']):.1f}%"
    examples = [escape(str(title)) for title in row.get("example_titles", []) if title]

    lines = [title_line, count_line]
    if examples:
        lines.append(f"Примеры: {', '.join(examples)}")
    else:
        lines.append("Примеры: нет")

    extra_count = int(row.get("extra_count") or 0)
    if extra_count > 0:
        lines.append(f"ещё {extra_count}")

    return "<br>".join(lines)


def build_score_distribution_figure(rows: list[dict]):
    """Build a Plotly bar figure for user_score distribution."""
    import plotly.graph_objects as go

    labels = [row["label"] for row in rows]
    counts = [row["count"] for row in rows]
    hover_texts = [_format_hover(row) for row in rows]

    fig = go.Figure(
        data=[
            go.Bar(
                x=labels,
                y=counts,
                marker={
                    "color": BAR_COLOR,
                    "line": {"color": BAR_HOVER_COLOR, "width": 1},
                },
                hovertext=hover_texts,
                hovertemplate="%{hovertext}<extra></extra>",
            )
        ]
    )
    _apply_chart_layout(
        fig,
        height=SCORE_DISTRIBUTION_CHART_HEIGHT,
        margin=CHART_MARGIN_DEFAULT,
        bargap=0.28,
    )
    fig.update_layout(
        xaxis={
            "title": {"text": "", "font": {"color": MUTED_TEXT, "size": CHART_AXIS_TITLE_SIZE}},
            "gridcolor": GRID_COLOR,
            "linecolor": GRID_COLOR,
            "tickfont": {"color": MUTED_TEXT, "size": CHART_AXIS_TITLE_SIZE},
            "showgrid": False,
        },
        yaxis={
            "title": {"text": "Тайтлов", "font": {"color": MUTED_TEXT, "size": CHART_AXIS_TITLE_SIZE}},
            "gridcolor": GRID_COLOR,
            "linecolor": GRID_COLOR,
            "tickfont": {"color": MUTED_TEXT, "size": CHART_AXIS_TITLE_SIZE},
            "rangemode": "tozero",
            "dtick": 1,
        },
    )
    return fig


def build_score_distribution_html(rows: list[dict]) -> str:
    """Build standalone HTML for QWebEngineView."""
    import plotly.io as pio

    fig = build_score_distribution_figure(rows)
    chart = pio.to_html(
        fig,
        include_plotlyjs=True,
        full_html=False,
        config={"displayModeBar": False, "responsive": True},
    )
    return _plotly_html_page(chart, SCORE_DISTRIBUTION_CHART_HEIGHT)


def _format_genre_count_hover(row: dict) -> str:
    label = escape(str(row["label"]))
    count = int(row["count"])
    examples = [escape(str(title)) for title in row.get("example_titles", []) if title]
    lines = [label, f"{count} тайтлов"]
    if examples:
        lines.append(f"Примеры: {', '.join(examples)}")
    extra_count = int(row.get("extra_count") or 0)
    if extra_count > 0:
        lines.append(f"ещё {extra_count}")
    return "<br>".join(lines)


def build_genre_count_figure(rows: list[dict]):
    """Build a horizontal bar chart for genre title counts."""
    import plotly.graph_objects as go

    labels = [str(row["label"]) for row in rows]
    counts = [int(row["count"]) for row in rows]
    hover_texts = [_format_genre_count_hover(row) for row in rows]
    height = bar_chart_height(len(rows))

    fig = go.Figure(
        data=[
            go.Bar(
                x=counts,
                y=labels,
                orientation="h",
                marker={
                    "color": BAR_COLOR,
                    "line": {"color": BAR_HOVER_COLOR, "width": 1},
                },
                hovertext=hover_texts,
                hovertemplate="%{hovertext}<extra></extra>",
            )
        ]
    )
    _apply_chart_layout(fig, height=height, margin=CHART_MARGIN_HBAR, bargap=0.24)
    fig.update_layout(
        xaxis={
            "title": {"text": "Тайтлов", "font": {"color": MUTED_TEXT, "size": CHART_AXIS_TITLE_SIZE}},
            "gridcolor": GRID_COLOR,
            "linecolor": GRID_COLOR,
            "tickfont": {"color": MUTED_TEXT, "size": CHART_AXIS_TITLE_SIZE},
            "rangemode": "tozero",
            "dtick": 1,
        },
        yaxis={
            "title": {"text": ""},
            "gridcolor": GRID_COLOR,
            "linecolor": GRID_COLOR,
            "tickfont": {"color": MUTED_TEXT, "size": CHART_AXIS_TITLE_SIZE},
            "autorange": "reversed",
            "showgrid": False,
        },
    )
    return fig


def build_genre_count_html(rows: list[dict]) -> str:
    """Build standalone HTML for genre count chart."""
    import plotly.io as pio

    fig = build_genre_count_figure(rows)
    chart = pio.to_html(
        fig,
        include_plotlyjs=True,
        full_html=False,
        config={"displayModeBar": False, "responsive": True},
    )
    return _plotly_html_page(chart, int(fig.layout.height))


def _format_year_average_hover(point: dict) -> str:
    year = int(point["year"])
    average = float(point["average"])
    count = int(point["count"])
    return f"Год: {year}<br>Средняя оценка: {average:.1f}<br>{count} тайтлов"


def build_year_average_figure(points: list[dict]):
    """Build a line chart for average user_score by release year."""
    import plotly.graph_objects as go

    years = [int(point["year"]) for point in points]
    averages = [float(point["average"]) for point in points]
    hover_texts = [_format_year_average_hover(point) for point in points]

    fig = go.Figure(
        data=[
            go.Scatter(
                x=years,
                y=averages,
                mode="lines+markers",
                line={"color": BAR_COLOR, "width": 2.5, "shape": "spline"},
                marker={
                    "size": 8,
                    "color": BAR_COLOR,
                    "line": {"color": BAR_HOVER_COLOR, "width": 1.5},
                },
                fill="tozeroy",
                fillcolor=COLOR_ACCENT_PLOT_FILL,
                hovertext=hover_texts,
                hovertemplate="%{hovertext}<extra></extra>",
            )
        ]
    )
    _apply_chart_layout(fig, height=YEAR_AVERAGE_CHART_HEIGHT, margin=CHART_MARGIN_DEFAULT)
    fig.update_layout(
        xaxis={
            "title": {"text": "Год выхода", "font": {"color": MUTED_TEXT, "size": CHART_AXIS_TITLE_SIZE}},
            "gridcolor": GRID_COLOR,
            "linecolor": GRID_COLOR,
            "tickfont": {"color": MUTED_TEXT, "size": CHART_AXIS_TITLE_SIZE},
            "showgrid": False,
        },
        yaxis={
            "title": {"text": "Средняя оценка", "font": {"color": MUTED_TEXT, "size": CHART_AXIS_TITLE_SIZE}},
            "gridcolor": GRID_COLOR,
            "linecolor": GRID_COLOR,
            "tickfont": {"color": MUTED_TEXT, "size": CHART_AXIS_TITLE_SIZE},
            "range": _year_average_axis_range(averages),
            "dtick": 0.5,
        },
    )
    return fig


def _year_average_axis_range(averages: list[float]) -> list[float]:
    if not averages:
        return [0, 10]
    minimum = min(averages)
    maximum = max(averages)
    if minimum == maximum:
        return [max(0, minimum - 0.5), min(10, maximum + 0.5)]
    padding = 0.3
    return [max(0, minimum - padding), min(10, maximum + padding)]


def build_year_average_html(points: list[dict]) -> str:
    """Build standalone HTML for average score by year chart."""
    import plotly.io as pio

    fig = build_year_average_figure(points)
    chart = pio.to_html(
        fig,
        include_plotlyjs=True,
        full_html=False,
        config={"displayModeBar": False, "responsive": True},
    )
    return _plotly_html_page(chart, YEAR_AVERAGE_CHART_HEIGHT)


def _chart_title_label(title: str, limit: int = IMDB_DELTA_CHART_TITLE_LIMIT) -> str:
    text = str(title)
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1]}…"


def _format_imdb_delta_hover(row: dict) -> str:
    title = escape(str(row["title"]))
    year = row.get("year")
    year_text = f" ({year})" if year not in (None, "") else ""
    user_score = float(row["user_score"])
    imdb_score = float(row["imdb_score"])
    delta = float(row["delta"])
    sign = "+" if delta > 0 else ""
    return (
        f"{title}{year_text}<br>"
        f"Моя: {user_score:.1f}<br>"
        f"IMDb: {imdb_score:.1f}<br>"
        f"Отличие: {sign}{delta:.1f}"
    )


def build_imdb_delta_figure(rows: list[dict]):
    """Build a horizontal diverging bar chart for user_score minus IMDb."""
    import plotly.graph_objects as go

    labels = [_chart_title_label(str(row["title"])) for row in rows]
    deltas = [float(row["delta"]) for row in rows]
    hover_texts = [_format_imdb_delta_hover(row) for row in rows]
    colors = [BAR_COLOR if delta >= 0 else IMDB_DELTA_NEGATIVE_COLOR for delta in deltas]
    height = bar_chart_height(len(rows))

    fig = go.Figure(
        data=[
            go.Bar(
                x=deltas,
                y=labels,
                orientation="h",
                marker={
                    "color": colors,
                    "line": {"color": GRID_COLOR, "width": 1},
                },
                hovertext=hover_texts,
                hovertemplate="%{hovertext}<extra></extra>",
            )
        ]
    )
    fig.add_vline(x=0, line_color=GRID_COLOR, line_width=1)
    _apply_chart_layout(fig, height=height, margin=CHART_MARGIN_HBAR, bargap=0.24)
    fig.update_layout(
        xaxis={
            "title": {"text": "Отличие (моя − IMDb)", "font": {"color": MUTED_TEXT, "size": CHART_AXIS_TITLE_SIZE}},
            "gridcolor": GRID_COLOR,
            "linecolor": GRID_COLOR,
            "tickfont": {"color": MUTED_TEXT, "size": CHART_AXIS_TITLE_SIZE},
            "zeroline": False,
            "dtick": 0.5,
        },
        yaxis={
            "title": {"text": ""},
            "gridcolor": GRID_COLOR,
            "linecolor": GRID_COLOR,
            "tickfont": {"color": MUTED_TEXT, "size": CHART_AXIS_TITLE_SIZE},
            "autorange": "reversed",
            "showgrid": False,
        },
    )
    return fig


def build_imdb_delta_html(rows: list[dict]) -> str:
    """Build standalone HTML for IMDb delta chart."""
    import plotly.io as pio

    fig = build_imdb_delta_figure(rows)
    chart = pio.to_html(
        fig,
        include_plotlyjs=True,
        full_html=False,
        config={"displayModeBar": False, "responsive": True},
    )
    return _plotly_html_page(chart, int(fig.layout.height))


def _format_score_count_hover(point: dict) -> str:
    score = float(point["score"])
    count = int(point["count"])
    examples = [escape(str(title)) for title in point.get("example_titles", []) if title]

    lines = [
        f"Оценка: {score:.1f}",
        f"{count} тайтлов",
    ]
    if examples:
        lines.append(f"Примеры: {', '.join(examples)}")

    extra_count = int(point.get("extra_count") or 0)
    if extra_count > 0:
        lines.append(f"ещё {extra_count}")

    return "<br>".join(lines)


def build_score_count_figure(points: list[dict]):
    """Build a Plotly dot/line chart: X=user_score, Y=title count."""
    import plotly.graph_objects as go

    scores = [point["score"] for point in points]
    counts = [point["count"] for point in points]
    hover_texts = [_format_score_count_hover(point) for point in points]

    fig = go.Figure(
        data=[
            go.Scatter(
                x=scores,
                y=counts,
                mode="lines+markers",
                line={"color": BAR_COLOR, "width": 2.5, "shape": "spline"},
                marker={
                    "size": 8,
                    "color": BAR_COLOR,
                    "line": {"color": BAR_HOVER_COLOR, "width": 1.5},
                },
                fill="tozeroy",
                fillcolor=COLOR_ACCENT_PLOT_FILL,
                hovertext=hover_texts,
                hovertemplate="%{hovertext}<extra></extra>",
            )
        ]
    )
    _apply_chart_layout(fig, height=SCORE_CHART_HEIGHT, margin=CHART_MARGIN_DEFAULT)
    fig.update_layout(
        xaxis={
            "title": {"text": "Моя оценка", "font": {"color": MUTED_TEXT, "size": CHART_AXIS_TITLE_SIZE}},
            "gridcolor": GRID_COLOR,
            "linecolor": GRID_COLOR,
            "tickfont": {"color": MUTED_TEXT, "size": CHART_AXIS_TITLE_SIZE},
            "range": _score_axis_range(scores),
            "dtick": 0.5,
            "showgrid": False,
        },
        yaxis={
            "title": {"text": "Тайтлов", "font": {"color": MUTED_TEXT, "size": CHART_AXIS_TITLE_SIZE}},
            "gridcolor": GRID_COLOR,
            "linecolor": GRID_COLOR,
            "tickfont": {"color": MUTED_TEXT, "size": CHART_AXIS_TITLE_SIZE},
            "rangemode": "tozero",
            "dtick": 1,
        },
    )
    return fig


def _score_axis_range(scores: list[float]) -> list[float]:
    if not scores:
        return [0, 10]

    minimum = min(scores)
    maximum = max(scores)
    if minimum == maximum:
        return [max(0, minimum - 0.5), min(10, maximum + 0.5)]
    return [minimum, maximum]


def build_score_count_html(points: list[dict]) -> str:
    """Build standalone HTML for exact-score count chart."""
    import plotly.io as pio

    fig = build_score_count_figure(points)
    chart = pio.to_html(
        fig,
        include_plotlyjs=True,
        full_html=False,
        config={"displayModeBar": False, "responsive": True},
    )
    return _plotly_html_page(chart, SCORE_CHART_HEIGHT)
