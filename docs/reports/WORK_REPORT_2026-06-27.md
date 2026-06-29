# ����� � ����������� ������ �� 2026-06-27

�������� �� ��������������� ���������� ����� `2c3eabe` (poster auto-download, Model tab LOO training).

## �������

��� �����������: **���������� ���� ������ ������** � **desktop wizard ��������� �����** � ������������ UX (����� > ������������� �� ��������). Save ��� ����� ������������ service path (`add_movie` / `add_dataset_record`), ��� ������ ������ JSON �� PyQt.

---

## 1. �������: ������ �������

### ������� ����

��������� ��������:

| # | ����� |
|---|--------|
| 4 | **�����** (�����) |
| 5 | ������������� |
| 6 | ���� ���������� |
| 7 | ��������� ����� |

### ������� �������

- **1 >> �������� ��� �����** � ������� `has_*` �� `config/genre_tags.json` � �������� ��������� (`label`).

### �����

| ���� | ��������� |
|------|-----------|
| `ui/console/ui.py` | `show_genres_menu()`, ������� `show_global_menu` |
| `ui/console/global_menu.py` | `open_genres_menu()` |
| `ui/console/console_app.py` | ������������� ������ 4 |
| `ui/console/genre_menu.py` | **�����** � ����� `genre_stats.show_model_genres()` |
| `dataset/genre_stats.py` | `build_model_genre_catalog()`, `show_model_genres()` |
| `config/genre_tags.json` | `has_romance` > label ���������� |
| `docs/README.md`, `docs/PROJECT_MAP.md` | ��������� ���� |

### �����

- `tests_pytest/test_genre_stats.py`

---

## 2. Desktop: wizard ��������� �����

�������� �������� `QMessageBox` �� ����������� �������� ���������� watched-������.

### UX (��� ������, `QStackedWidget`)

**����� A � �����**

- ��������, ������ (�� ��������� **��� �����**), ������
- Progress bar �� 7 ����� resolve (IMDb SQL > KP > TMDb > ������)
- ��������� ����: ��������� ����� � �����

**����� B � �������������**

- ����� ��������� resolve ����� ������ **�����**
- ����� � title/year, ������ ����������
- ���������� `WatchedDetailCard` (������ ?0.5, ������� ����� IMDb/��, ��� ���� ������ �� ��������)
- Scroll ������ ��� ��������; ���, ������ � ������ **��� scroll**
- ������� ������ > ������� �� ����� A
- ��������� ����� > `save_add_title_record()` > refresh ������ watched

### Service-����

| ���� | ���� |
|------|------|
| `dataset/add_title_service.py` | resolve bundle, preview card, `save_add_title_record()` |
| `dataset/title_resolve.py` | `on_progress` callback ��� GUI |
| `desktop/add_title_worker.py` | `QThread` > resolve |
| `desktop/add_title_dialog.py` | wizard UI |
| `desktop/app.py` | `_open_add_title_dialog()` |
| `candidates/tmdb_country_options.py` | ��� ����� + `add_title_country_combo_options()` |

### �������� preview

- `DetailCardLayoutProfile` + `ADD_TITLE_PREVIEW_CARD_PROFILE`
- `include_bottom_stretch=False` ��� preview (������ ������ ������ scroll)
- QSS: `#addTitlePreviewCard QLabel#detailTitle` > 18px

### �����

- `tests_pytest/test_add_title_service.py`
- `tests_pytest/test_desktop.py` � wizard wiring, `QStackedWidget`

### Roadmap

- `docs/DESKTOP_GUI_ROADMAP.md`: B1/B2 wizard � **done**

---

## 3. ��� �� ������ / �� ����������

- `config/model_metrics.json` � ��������� �������� ����� LOO, �� ���������� � ������.

---

## 4. ��������

```powershell
python -m pytest tests_pytest/test_genre_stats.py tests_pytest/test_add_title_service.py tests_pytest/test_desktop.py::test_add_title_button_opens_wizard_dialog -q
```

---

## 5. ��������� ���� (�����������)

- �������������� vibe-����� � ������ �� ������ preview
- �������� ������� � preview �� URL �� save
- LLM-�������� vibe-����� (��. ���������� �����)
