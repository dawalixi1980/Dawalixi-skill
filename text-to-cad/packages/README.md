# Packages

Libraries and distributions. Applications live in `apps/`.

- `cadgen/` — the published distribution: the Python engine plus the built
  JS runtimes it executes. The design laws live in its README.
- `cadgen-js/` — the shared JS source between cadgen's rendering and its
  clients (the viewer, the docs app). Framework-free by law.

Each package's README carries its PURPOSE / MAY DEPEND ON / DEPENDED ON BY
boundary and the laws that live there. New shared code goes in the package
whose boundary admits it — never in an app, never duplicated.

Ships-alone law: `cadgen/` builds and publishes as a package that works in
isolation outside this repo (cadgen-js is bundled in at build time), so its
markdown must not refer to anything outside the package. The same law binds
`apps/viewer/`, which mirrors unchanged to the standalone
`earthtojake/cad-viewer` repo. Enforced by the markdown-isolation check in
`tests/python/global/test_package_boundaries.py`.
