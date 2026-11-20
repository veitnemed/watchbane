"""Source preview entry point. No installs, downloads, or default real-profile writes."""
import argparse
import os
from pathlib import Path


from candidates.story_seed_snapshot import CATALOG_ENV, configure_catalog, resolve_catalog


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', type=Path, help='Use a chosen local profile; defaults to .preview-profile beside this script')
    parser.add_argument('--model-dir', type=Path, help='Existing verified E5 directory; never downloaded automatically')
    parser.add_argument('--catalog', type=Path, help='Override the configured or publisher-installed local JSONL snapshot')
    parser.add_argument('--check', action='store_true', help='Verify imports/model, then exit without opening a window')
    args = parser.parse_args()
    for name in ('WATCHBANE_DEV_EMPTY_PROFILE', 'WATCHBANE_DEV_CLEAR_CANDIDATES_ON_START'):
        if os.environ.get(name, '').casefold() in {'1', 'true', 'yes', 'on'}:
            parser.error(f'Unset {name} before running the source preview')
    profile = args.profile or Path(__file__).parent / '.preview-profile'
    os.environ['WATCHBANE_DATA_DIR'] = str(profile.expanduser().resolve())
    if args.model_dir:
        os.environ['WATCHBANE_STORY_MODEL_DIR'] = str(args.model_dir.expanduser().resolve())
    catalog = resolve_catalog(__file__, args.catalog, os.environ.get(CATALOG_ENV))
    os.environ.setdefault('WATCHBANE_INTERFACE_LANGUAGE', 'ru')
    os.environ.setdefault('WATCHBANE_DATA_LANGUAGE', 'ru')
    if args.check:
        from desktop.shell.main_window import WatchedMoviesWindow  # noqa: F401
        if catalog is not None:
            from candidates.story_seed_snapshot import StorySeedSnapshotError, load_seed_snapshot
            try:
                print('Validated catalogue:', len(load_seed_snapshot(catalog)))
            except StorySeedSnapshotError as exc:
                parser.error(str(exc))
        model = os.environ.get('WATCHBANE_STORY_MODEL_DIR')
        if model:
            from candidates.story_semantic import LocalE5
            encoder = LocalE5(model)
            assert encoder.encode(['Проверка локальной модели'], prefix='query: ').shape == (1, 384)
            print('Verified local E5:', encoder.variant)
        else:
            print('Source imports OK; fallback mode (no model selected).')
        print('Profile:', os.environ['WATCHBANE_DATA_DIR'])
        return
    configure_catalog(catalog)
    from desktop.shell.bootstrap import main as start
    start()


if __name__ == '__main__':
    main()
