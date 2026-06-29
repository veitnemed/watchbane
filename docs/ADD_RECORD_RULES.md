# ������� ���������� � ��������� ������� dataset

���� ���� ��������� ������� �������� ���������� � ��������� �������. �� ������ �������� �������� ��������� ����, � �� �������� ����������� "�� �������".

## ������� �������

����� ������ ������ ����������� ����� ������������ ���������� ����:

```python
storage_movie.add_movie(...)
    -> add_dataset_record(...)
```

������ ��������� dataset �������� �� UI-���������.

## ���� ���������������

### UI-����

�����:

- [ui/console/interface_funcs.py](../ui/console/interface_funcs.py)
- [ui/console/request.py](../ui/console/request.py)
- [desktop/app.py](../desktop/app.py)
- [desktop/watched_view.py](../desktop/watched_view.py)

�������� ��:

- ����� ��������;
- ����� �������� � ��������������;
- ���� defaults;
- �������� ����� �������������;
- ������ ���� `user_score`, `raw_scores`, `tags_vibe`, `genre`;
- ������ ���������� ��������� ������������.

UI �� ������ ����� ��������� ������ � dataset.

Desktop GUI ���������� ��� �� �������: ��������� `user_score` ��� ����� `dataset.dataset_records.update_dataset_record()` � helper `save_watched_user_score()`, � �� ����� ������ ������ JSON �� PyQt.

### Storage / service-����

�����:

- [dataset/storage_movie.py](../dataset/storage_movie.py)
- [dataset/dataset_records.py](../dataset/dataset_records.py)

�������� ��:

- ��������� payload;
- �������� ������;
- ������������ �����;
- ��������/���������� meta;
- �������� `computed_scores`;
- ���������� dataset;
- ������� candidate pool ����� ��������� ����������;
- ������� ������������������ ����������.

Storage ���������� `AddRecordResult`, � �� ��������� UX �������.

## ������� �������� `add_movie()`

```python
add_movie(
    movie: dict,
    *,
    meta_payload=None,
    pool_candidate=None,
    print_message: bool = True,
)
```

### ��� ������ `add_movie()`

- �������� `add_dataset_record(...)`;
- ����������� `meta_payload`;
- ����������� `pool_candidate`;
- �� ��������� ����� ���������� `result.message`;
- ���������� `AddRecordResult`.

### ��� ����� ������

- ��� UI-���������, ��� ��������� ��� ���������� �������, ����� �������� `print_message=False`;
- ��� ������� ������� ����� `����� ������ ���������!`.

## ������� �������� `add_dataset_record()`

```python
add_dataset_record(
    record_payload: dict,
    meta_payload=None,
    source_name: str = "",
    pool_candidate=None,
) -> AddRecordResult
```

### ������������ ������ `record_payload`

- `main_info.title`
- `main_info.user_score`
- `main_info.year`
- `raw_scores`
- `tags_vibe`
- `genre`

### ��� ��������� service

- ���������� `title`;
- ����� �� title ��� ����� ��������;
- ���������� `user_score`;
- ���������� `year`;
- ���������� `raw_scores`;
- ���������� `tags_vibe`;
- ���������� `genre`;
- ������� ��������� ������ ���������.

### ��� ������ ��� ������

1. ����������� `main_info`, `raw_scores`, `tags_vibe`, `genre`;
2. �������� `computed_scores`;
3. ��������� ������ � dataset;
4. ��� ������������� ��������������/������ meta;
5. ������� candidate pool:
   - ���� ������� `pool_candidate`, ������� ������ ���;
   - ����� ������ best-effort cleanup ������������� ����������;
6. �������������� poster-cache (`sync_poster_cache_from_meta_and_sources`) � **��������� ��������� ���� �������** (`download_poster_for_title`) � best-effort, ������ �� ���������� ���������� ������;
7. ���������� `AddRecordResult(ok=True, ..., reason="saved")`.

���������� ������� ��� � service-����, �� �� UI. Batch �������� ����������� �������� � ������� (`Extra` > `download_poster_images_local`) ������� ��� backfill ������ �������.

## ��������� ���������� ����� ������

### 1. ������ ����������

����:

```text
interface_funcs.request_object()
-> request.request_api_defaults(confirm_genres=True)
-> request.request_all_scores(defaults)
-> storage_movie.add_movie(movie_request, print_message=False)
```

�����������:

- defaults ���������� ����� SQL/API flow;
- ����� ����������� ������ ����������� �����;
- �������� ��������� �������� UI.

### 2. ������� ��������� �� ����

����:

```text
interface_funcs.mark_candidate_as_watched()
-> title_resolve.build_candidate_transfer_payload(candidate)
-> request.request_all_scores(defaults)
-> storage_movie.add_movie(
       movie_request,
       meta_payload=meta_payload,
       pool_candidate=candidate,
       print_message=False,
   )
```

�����������:

- ������ �� ����������� ������������� ��� �����;
- ����� ������ UI �������� read-only preview ������ (`build_candidate_genre_transfer_preview`);
- ����� ������ �������� ��������� �� ������ ����;
- ��� incomplete-��������� UI ���������� ��������������, �� �� ��������� �������.

## ��� TMDb-�������� ������������ � defaults

������ ���� �:

- [dataset/title_resolve.py](../dataset/title_resolve.py)

`build_candidate_transfer_payload(candidate)` �������:

- `defaults` ��� �����;
- `meta_payload` ��� ���������� meta.

### ��� TMDb-��������� ������������ common-����

- `title`
- `year`
- `kp_score`
- `kp_votes`
- `imdb_score`
- `imdb_votes`
- `genres`
- `description`
- `tmdb_id`
- `imdb_id`
- `kp_id`
- `source`

### ���������� `raw_scores`

� ����� ������ ��������:

- `kp_score <- candidate["kp_score"]`
- `kp_votes <- candidate["kp_votes"]`
- `imdb_score <- candidate["imdb_score"]`
- `imdb_votes <- candidate["imdb_votes"]`

���� ���� ���, ��� ������ �������� ������/`None`, � �� ������������ � `0`.

## �����

�������� �������� � dataset � ��� ������������� ����� �������� `has_*` �� [config/genre_tags.json](../config/genre_tags.json). ����� `has_*` ��� ������������ ������ �� �����������.

����� mapper ���� � [candidates/to_dataset.py](../candidates/to_dataset.py):

- `candidate_genre_keys_to_dataset_genres(genre_keys)` � canonical pool keys > `has_*`;
- `raw_genres_to_dataset_genres(raw_genres)` � EN/RU raw labels > pool keys > `has_*`.

������ �������: pool key `mystery` � raw labels `Mystery` / `��������` > `has_detective`, � �� `has_mystery`.

### ������ ����������

`build_genre_defaults()` � [dataset/title_resolve.py](../dataset/title_resolve.py) ���������� `raw_genres_to_dataset_genres()`.

`split_known_genres()` ��� confirm UI � [ui/console/request.py](../ui/console/request.py) ���������� ��� �� mapper: � known �������� ������ raw-�����, ������� ������� �������� � ������� `has_*`.

### ������� candidate > dataset

`build_candidate_transfer_genre_defaults()` �������� �������� ���:

1. ���� ���� �������� `candidate["genre_keys"]` � mapper status �� `missing` > `candidate_genre_keys_to_dataset_genres()`;
2. ����� fallback ����� `extract_candidate_fallback_genres()` (`imdb_genres`, `genres_tmdb`, `genres`) � `build_genre_defaults()`.

����� ������ `mark_candidate_as_watched()` �������� read-only preview:

- pool `genre_keys` > �������� `has_*`;
- fallback / partial / empty warning � ��� ���������� ��������.

������������ �� ����� ������������ ��� ������ ����� � ����� `request_all_scores()`.

## Meta ��� ����������

`meta_payload` ����� ��������� �������������� ���� ������ `main_info` / `raw_scores`.

������ � meta ��� TMDb-�������� �� ����������� ����������:

- `tmdb_id`
- `imdb_id`
- `kp_id`
- `description`
- `source`

`add_dataset_record()` ��������� ��� �������������� ���� ��� extra meta.

## Duplicate policy

����� ������ �����������, ���� � dataset ��� ���� title � ��� �� ������� ��� ����� ��������.

��������� ��� �����:

```python
AddRecordResult(
    ok=False,
    message="������ ����������! ����� ������ ��� ��������",
    reason="duplicate_title",
)
```

��� ����� ��� callers � ������: current contract ���������� ������ ����������, � �� `False`.

## ���������� ������������ ������

��� patch ������������ ������ ������������:

```python
update_dataset_record(title, patch_payload, source_name="") -> UpdateRecordResult
```

### ��������� ������

- `main_info.user_score`
- `main_info.year`
- `raw_scores`
- `tags_vibe`
- `genre`

### ��������� ������ ����� update

- key ������;
- `main_info.title` ��� ������ ��������������.

�������������� ������ ���� ��������� ���� ����� `rename_movie_title()`.

## ���������� ������ � �������

`user_score` ����� ������ ����������� UI-����������, �� ��� ��� ������ ���� ����� ����� update-service:

- ������ ��������� ����� ������ �� `�������� ��� ������`;
- ��������� ������ � desktop GUI ����� ��� -> dialog;
- �������� ��������� ������� ������ (`rating_comparison`);
- ���������� draft ��������� ������������� ������.

### Rating comparison

����:

```text
global_menu.open_data_menu()
-> rating_comparison.start_rating_comparison()
-> rating_comparison.apply_rating_comparison_scores()
-> update_dataset_record(title, {"main_info": {"user_score": new_score}}, source_name="rating_comparison")
```

����� ����������� ����������� preview snapshot:

```text
config/rating_comparison_last_snapshot.json
```

���� ������������ �������� ����������, snapshot ������� ��� preview, � dataset �� ��������.

### Draft ��������� �������������

�������� draft:

```text
interface_funcs.show_all_movies()
-> interface_funcs.open_scores_actions_menu()
-> interface_funcs.create_linear_distribution_draft(rows)
```

Draft ����������� �:

```text
data/rating_order_drafts/rating_order_draft_YYYY-MM-DD_HH-MM-SS.json
```

�������� draft �� ������ dataset.

���������� draft:

```text
interface_funcs.apply_rating_order_draft_flow()
-> validate_rating_order_draft(draft, data)
-> build_rating_order_draft_preview(...)
-> storage_files.create_backup()
-> update_dataset_record(title, {"main_info": {"user_score": proposed_score}}, source_name="rating_order_draft")
```

��������� draft ������ ���������� ����������, ����:

- `method` �� ����� `linear_distribution`;
- ����������� `items`;
- ������ �� draft ����������� � ������� dataset;
- ������� `user_score` ���������� �� `old_score` � draft;
- `proposed_score` �� �������� `valid.is_correct_score`.

LOO-preview ��� draft ������� `current_loo_mae` � `draft_loo_mae` �� ����� dataset. ���� preview �� ������ ��������� ���� � �� ������ ������ `config/model_metrics.json`.

����� ���������� draft ������������ ��������� LOO �������� ��������, ���� ����� �������� ���� � ���������� `LOO MAE`.

## Excel-�������

Excel-����� ������ ������ ��� patch ������������ �������, � �� ��� �������� �����.

��� ������:

- Excel �� ������ ��������� ����� ������;
- Excel �� ������ ������� ������;
- Excel �� ������ ��������������� ������;
- ���� ����� title �� ��������� � dataset, ������ ������ ���������������;
- `raw_scores` patch ������ ������������������ � meta ����� update-service.

## Candidate pool cleanup

������� �������:

- �������� ���������� ����� ������� ��������� ������ ������� ��������� �� ������ ����;
- ��� ����� caller ������� `pool_candidate` � `storage_movie.add_movie()`;
- cleanup ����������� � `add_dataset_record()`, � �� ������� ��������� UI-����� ����� ����������.

## �������� watched

����:

```text
delete_watched_record(dataset_key)
```

����: [dataset/delete_record.py](../dataset/delete_record.py).

Service ������� ������ �� dataset, meta � poster-cache **����� backup**. ����� �������� cache ���������� `remove_local_poster_file()` � ��������� JPG � `data/cache/posters/images/` ���������, ���� ���.

��������� �������� �������� `deleted_dataset`, `deleted_meta`, `deleted_poster_cache`, `deleted_poster_file`. ������ �������� ����� ������� **���������** �������� ������ (dataset/meta �� ��������).

Console � desktop GUI �������� ���� � ��� �� service; UI �� ������� JSON ��������.

## ������ ���������

������� ���������� ���������������:

- service ���������� `AddRecordResult` / `UpdateRecordResult`;
- UI ������, ��� �������� ������������;
- ��� ��������� � ������ ������� ����� ������������ `print_message=False`.

��� ��������� ������-������ ��� ���������, �� ������� ������� success-output.
