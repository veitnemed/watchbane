

import os

from candidates.story_seed_snapshot import CATALOG_ENV, configure_catalog, resolve_catalog
if __name__ == "__main__":
    configure_catalog(resolve_catalog(__file__, environment_path=os.environ.get(CATALOG_ENV)))
    from desktop.app import main

    main()
