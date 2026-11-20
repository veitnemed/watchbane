import os
import sys

if __name__ == "__main__":
    if sys.argv[1:2] == ["--check-semantic-runtime"]:
        if len(sys.argv) != 3:
            raise SystemExit(2)
        from candidates.story_runtime_probe import write_runtime_check

        raise SystemExit(write_runtime_check(sys.argv[2]))

    from candidates.story_seed_snapshot import CATALOG_ENV, configure_catalog, resolve_catalog

    configure_catalog(resolve_catalog(__file__, environment_path=os.environ.get(CATALOG_ENV)))
    from desktop.app import main

    main()
