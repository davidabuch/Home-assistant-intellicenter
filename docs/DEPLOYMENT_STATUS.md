# Deployment status — NOT READY

This repository is an in-progress implementation, **not** an installable replacement.

- Config flow and command transport are implemented.
- Live authoritative observation mapping is not implemented; climate entities intentionally report unavailable.
- The integration startup intentionally fails rather than create misleading or unsafe entities.
- No HA registry migration has occurred. Old entity IDs still belong to PoolOS.
- No physical commands have been sent by this integration.
- Do not add this repository to HACS or remove PoolOS until the complete commissioning gate passes.

Next engineering gates: pyintellicenter model observation mapping, connection lifecycle, entity registration, read-only observation validation, tests with mocked transport, compatibility mapping, CI, HA installation, physical commissioning.
