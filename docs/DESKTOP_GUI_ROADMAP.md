# ����: ������� ����������� � PyQt desktop GUI

����: 2026-06-25  
������: �������� ����  
��������� ���������: [DESKTOP_STYLE_CONTRACT.md](DESKTOP_STYLE_CONTRACT.md), [ADD_RECORD_RULES.md](ADD_RECORD_RULES.md), [PROJECT_MAP.md](PROJECT_MAP.md), [ARCHITECTURE_TARGET.md](ARCHITECTURE_TARGET.md), [add_functions.md](add_functions.md)

������ �� polish: [DESKTOP_GUI_REPORT_2026-06-25.md](reports/DESKTOP_GUI_REPORT_2026-06-25.md), [DESKTOP_GUI_REPORT_2026-06-25_layout-polish.md](reports/DESKTOP_GUI_REPORT_2026-06-25_layout-polish.md)

����������: ���������� � layout-�������� desktop GUI ������ � [DESKTOP_STYLE_CONTRACT.md](DESKTOP_STYLE_CONTRACT.md). ���� �������� ��������� **��� � � ����� �������** ���������� � GUI, �� �������� ������� ����������.

## ����

PyQt desktop � **�������� ��������** ��� ������������ ������ � watched-�����, ���������� � (�����) ��������������.

������� � **������� � fallback**: ������� �������, ��������, pool build, �������� ��������, �������.

## ������������� ������

```
PyQt widget (desktop/*)
  > desktop helper / dialog
    > dataset/* | candidates/service | model reports
      > storage / JSON / cache
```

Ƹ����� �������: GUI **�� ����� JSON ��������**. Write ������ ����� documented services:

- `dataset/dataset_records.py` � add/update ������;
- `dataset/delete_record.py` � �������� watched;
- `candidates/service.py` � candidate pool � top prediction.

���������: [add_functions.md](add_functions.md), [PROJECT_MAP.md](PROJECT_MAP.md).

## ������� ���������

| ������� | ����� | ������ |
| --- | --- | --- |
| Watched list + �������� | [desktop/watched_view.py](../desktop/watched_view.py), [desktop/app.py](../desktop/app.py) | done |
| Watched sidebar (�������, thumbnails, delete) | `app.py`, `watched_delete.py`, `delete_dialog.py` | done |
| �������������� `user_score` | `app.py` > `update_dataset_record` | done |
| �������� watched | `app.py` > `delete_record.delete_watched_record` | done |
| Analytics KPI / dense / insights | [desktop/analytics_view.py](../desktop/analytics_view.py) | done |
| Analytics �������� dataset� | `score_analytics.py` + `analytics_view.py` | done |
| Analytics MVP (�����, ����, gaps, suspicious) | `score_analytics.py` + `plotly_charts.py` + `analytics_view.py` | done |
| Bar �������������� ������ | `analytics_view.py` + [desktop/plotly_charts.py](../desktop/plotly_charts.py) + [dataset/score_analytics.py](../dataset/score_analytics.py) (`chart_distribution`) | done |
| Layout-�������� | [DESKTOP_STYLE_CONTRACT.md](DESKTOP_STYLE_CONTRACT.md) | done |

---

## ���� 1. Polish �������� GUI

**����:** ���������� ������� ���, ��� ����� ������-������.  
**�����:** `desktop/watched_view.py`, `desktop/analytics_view.py`, `desktop/plotly_charts.py`, `desktop/app.py`

### ������

- [x] **1.1** Visual QA watched card � done (������� � [DESKTOP_STYLE_CONTRACT.md](DESKTOP_STYLE_CONTRACT.md); helper-����� sparse card � `test_desktop.py`).
- [x] **1.2** Polish ����� ������ ������ � done (sidebar: thumbnails, collapsible filters, sort row, counter, forest-green add button).
- [x] **1.3** Plotly charts: ������ ������/�������, `#analyticsPlotlyChart`, ��� `COLOR_SURFACE` � done (`plotly_charts.py` helpers, `analytics_view.py`).
- [x] **1.4** Analytics polish (KPI, ��������, spacing) � done (`ANALYTICS_*` ���������, completeness block layout).

### �������� ����������

��� ������� ����� �� [DESKTOP_STYLE_CONTRACT.md](DESKTOP_STYLE_CONTRACT.md) �������� �������; layout �� �������� ��� resize.

### �� ������ �� ���� �����

����� write, ����� �������, pool, training.

---

## ���� 2. Read-only ����������

### 2.1 Watched (������ �����������)

- [x] **2.1.1** ������ �� ��������� `user_score` � done (`desktop.watched_view.filter_entries_by_user_score`, UI min/max � watched left panel).
- [x] **2.1.2** ������ �� ���� � done (`desktop.watched_view.filter_entries_by_year`, UI `year_from/year_to` � watched left panel).
- [x] **2.1.3** ������ �� ����� � done (`desktop.watched_view.get_available_genres`, `filter_entries_by_genre`, UI genre combo � watched left panel).
- [x] **2.1.4** ������� �������� N� � done (`format_watched_list_counter` ��� ������� + status bar).
- [x] **2.1.5** ������� ����� �������� � done (`�������� �������`, score/year/genre > defaults; ����� �� ������������).

������: `load_watched_entries()` + filter/sort, ��� ������.

### 2.2 Analytics (������� �� ������)

Pipeline ��� **�������** ������ �������:

1. ������ � [dataset/score_analytics.py](../dataset/score_analytics.py);
2. HTML � [desktop/plotly_charts.py](../desktop/plotly_charts.py);
3. ������ � [desktop/analytics_view.py](../desktop/analytics_view.py) + Qt-fallback;
4. smoke � [tests/test_desktop.py](../tests/test_desktop.py).

������� ����������:

- [x] **2.2.0** Read-only �������� dataset� � done (`build_dataset_completeness*`, ��� ������ � ��������).
- [x] **2.2.1** ������������� �� �������� � done (`score_count_points` + Plotly).
- [x] **2.2.2** ���������� ������� �� ������ � done (`genre_count_rows`, horizontal bar).
- [x] **2.2.3** ������� ��� ������ �� ����� � done (`year_average_points`, line chart; **���** count-by-year).
- [x] **2.2.4** � ������ ���� IMDb � done (text list, ? ? 1.5, ������ IMDb).
- [x] **2.2.5** � ������ ���� IMDb � done (text list, ? ? ?1.5, ������ IMDb).
- [x] **2.2.6** �������������� ������ � done (text list + reason).
- [x] **2.2.7** ������� ���� ������ �� IMDb � done (text top-10 + ��������� ����, ���������� �� |?|, �� 20).

**Analytics MVP freeze (2026-06-26):** ����� ����� ��������������� ������ **�� ���������** ����� analytics-������ ��� ���������� �������. ����������: **2.2.7** �������� �� �������. ��� scope: ������, pie charts, scatter, ������ ���������� ������ �� �����, �������, drill-down � watched.

�������� / ���������� �� ������� �����:

- ~~2.2.x ���� ������ �� ����� (count)�~~ � �� ������ � MVP;
- ~~scatter/bar ���� vs IMDb/�ϻ~~ � �������� text lists 2.2.4�2.2.5.

### �������� ����������

������ ������ �������� � Plotly/WebEngine � � Qt-fallback; analytics read-only � �� ������� weights, `model_metrics`, pool, dataset (����� ������).

---

## ���� 3. ���������� write � watched

### ������

- [x] **3.0** UI-stub �������� ���������� watched-������ � done (`+ �������� �����` > wizard: search, progress, card confirm, save ����� service).
- [x] **3.1** �������� ������ � done (��� > �������� �������, preview dialog, ������������� `DELETE`, `delete_watched_record()` ����� `desktop/watched_delete.py`).
- [x] **3.2** Read-only ��������� ������ (�����������): �������� ��������� ������, ��������� ���� poster-cache� � done (`WatchedDetailCard`, `open_path_in_shell`).

### �����

[tests/test_delete_watched_record.py](../tests/test_delete_watched_record.py) � service layer; wiring GUI � `tests/test_desktop.py` (`test_watched_delete_*`, context menu).

### �� ������ �� ���� �����

������ �������� ������ (title, genres, raw_scores).

### �������� ����������

Delete �������� ��� �� service path, ��� � �������; cancel �� ������� ������.

---

## ���� 4. ������� ��������

**Read-only KPI + ����� LOO-��������** ����� service; ��� ��������� �������� �� GUI.

| ���� | �������� |
| --- | --- |
| LOO MAE summary | `config/model_metrics.json`, train reports |
| IMDb / KP baseline | report helpers �� `model/` |
| Feature ablation | [ui/console/train_menu.py](../ui/console/train_menu.py) / model diagnostics |
| Top errors | read-only report |

### ������

- [x] **4.1** ������� �������� � read-only summary �� `model_metrics` � done (`ModelView`, KPI: LOO MAE, IMDb/�� baseline, dataset size, fresh/stale).
- [x] **4.2** LOO-��������: ������, progress bar, `QThread` > `execute_explicit_loo_training()` � done (`model_loo_worker.py`); stale-banner + ���������� (����).
- [ ] **4.3** Read-only ���������� ����� / ablation / top errors (��� save).

### �� ������

�������� �������� �� GUI, auto-update metrics ��� ������ LOO.

---

## ���� 5. ������������� (read-only top prediction)

- [ ] **5.1** ������� > ����� `criteria_name`.
- [ ] **5.2** [candidates/service.py](../candidates/service.py) `get_global_top_prediction_view()` � ������������ �������� ranking (��� � console ~1638 `interface_funcs.py`).
- [ ] **5.3** ������� (runtime, ready/incomplete) ����� service.
- [ ] **5.4** �������� ���������� read-only.

### �� ������

�������� pool, import TMDb, retry KP, ������ `candidate_criteria.json`. Ranking �� ����������� � `desktop/`.

---

## ���� 6. Candidate pool � GUI

### Read-only (�������)

- [ ] **6.1** ������ criteria.
- [ ] **6.2** Stats (raw/watched/active/ready/incomplete).
- [ ] **6.3** �������� ����������, ������ incomplete.

### Write (�����, � confirmation dialogs)

- mark watched;
- retry KP;
- delete criteria;
- import saved TMDb result.

### �������� � �������

TMDb build, �������� ��������, ������� import.

---

## ���� 7. ������� � metadata

### Backend (done)

- [x] **7.0** ��� ���������� ������ � sync poster-cache + `download_poster_for_title()`; ��� �������� � `remove_local_poster_file()` (`add_dataset_record`, `delete_watched_record`).

### Read-only (�������)

- [ ] **7.1** �����������: ������� �������� local / missing / ��� description.

### �����

- update metadata;
- batch download missing posters (������� Extra ��� ���� ��� backfill).

��������� ����-����: ����, TMDb, SSL.

---

## ���� 8. ���� �������

������� **�� �������**. �������� ������� ���:

- Excel import/export;
- LOO training / weights;
- rating comparison / drafts;
- TMDb pool build;
- backup/restore;
- �������.

---

## ��������� 8 �����

| # | ��� | ���� | ������ |
| --- | --- | --- | --- |
| 1 | A1 Analytics Plotly/KPI polish | 1 | done |
| 2 | A2 Read-only poster actions � �������� | 1 | done |
| 3 | A3 Status bar LOO MAE | 1 | next |
| 4 | B1 Wizard ��������� ����� (search + preview) | 3 | done |
| 5 | B2 Wizard save ����� service | 3 | done |
| 6 | C4 ������� ������������� read-only | 5 | planned |
| 7 | C1 ������� �������� KPI + LOO �������� | 4 | done |
| 8 | C1.2 Baseline comparison + �������� | 4 | next |
| 9 | E1 Mark watched �� pool | 6 | planned |

---

## ������� ����� GUI-PR

- [x] ��� ������ ������ JSON �� PyQt (delete > `delete_watched_record`, score > `update_dataset_record`).
- [x] Write ��� ����� documented service + `source_name` (score edit).
- [x] Layout/size policy �� [DESKTOP_STYLE_CONTRACT.md](DESKTOP_STYLE_CONTRACT.md) (watched card + sidebar).
- [x] Spacing/fonts ����� ����������� ��������� � `analytics_view.py`.
- [x] Helper-����� edge cases watched card � `test_desktop.py`; ������ ������� � style contract.
- [x] `tests/test_desktop.py` (+ smoke ��� plotly ��� ��������).
- [x] �� �������: training, pool build, weights ��� ���������� �����.

## ��� �� ������� ��� ���������� �������

- ������ dataset / meta;
- ������������ ����� ������ ������;
- TMDb/KP pipeline, poster cache logic;
- `candidate_pool` write �� GUI �� ������ ������;
- web GUI;
- console flows (����� reuse helpers).
