# PsychoParadigm Architecture

## Runtime layout

- `paradigm.app` is the CLI entry and now lazily loads task runners so headless imports do not pull in PsychoPy visual modules.
- `paradigm.runtime.base_experiment` owns the shared task lifecycle, flip helpers, response helpers, logging calls, and safe-exit flow.
- `paradigm.runtime.session` builds the runtime service bundle: window, keyboard, clocks, paths, loggers, marker manager, and eye tracker manager.

## Contracts and data

- `paradigm.contracts` contains the stable runtime contracts:
  - `event_codes.py` for semantic event registry and hardware marker codebook
  - `schemas.py` for metadata, run summary, and `task_specific_data` schemas
  - `validation.py` for event/trial consistency helpers
- `paradigm.data` contains data-layer helpers:
  - `logging.py` for CSV/JSON writers
  - `bids.py` for BIDS-ready behavior/event export
  - `rdm_export.py` for RDM analysis tables
  - `normalize.py` for post-run artifact normalization

## Hardware

- `paradigm.hardware.markers.manager` owns `MarkerManager`, `LSLMarkerBackend`, and runtime marker status snapshots.
- `paradigm.hardware.markers.backends` owns the pluggable LPT backends:
  - `InpOutLPTBackend`
  - `PsychoPyParallelLPTBackend`
  - `NullLPTBackend`
- Backend selection is controlled by `MarkerConfig.lpt_backend`:
  - `auto`: try `inpout`, then `psychopy`
  - `inpout`: use Windows `inpoutx64`
  - `psychopy`: force PsychoPy parallel backend

## Tasks

- Each task now has two layers:
  - runner package: `paradigm.tasks.doors`, `paradigm.tasks.prl`, `paradigm.tasks.rdm`
  - pure logic module: `paradigm.tasks.doors.doors_logic`, `paradigm.tasks.prl.prl_logic`, `paradigm.tasks.rdm.rdm_logic`
- The pure logic modules are safe to import in headless environments and are the preferred target for unit tests.

## Tools

- Package-native tools now live under `paradigm.tools`.
- Post-run normalization lives in `paradigm.data.normalize`, while the command-line entrypoint is `paradigm.tools.normalize_logs`.
- BIDS and RDM export entrypoints are `paradigm.tools.export.export_bids` and `paradigm.tools.export.export_rdm`.
