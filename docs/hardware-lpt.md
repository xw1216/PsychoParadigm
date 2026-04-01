# LPT Backend Notes

## Backend policy

- `enable_lpt=false`: LPT is disabled and marker sending is skipped safely.
- `lpt_backend=auto`: try `InpOutLPTBackend` first, then fall back to `PsychoPyParallelLPTBackend`.
- `lpt_backend=inpout`: use the Windows `inpoutx64` driver path only.
- `lpt_backend=psychopy`: force PsychoPy parallel support.

## InpOut backend

- The packaged Windows driver assets live in `paradigm/hardware/markers/vendor/windows/`.
- Config knobs:
  - `markers.lpt_driver_dir`
  - `markers.lpt_dll_name`
  - `markers.lpt_address`
  - `markers.lpt_pulse_width_ms`
  - `markers.lpt_reset_on_close`
- The backend uses `ctypes`, checks `IsInpOutDriverOpen`, writes markers through `Out32`, and clears the line back to zero after the configured pulse width.

## Status and metadata

- `run_metadata.json` now records:
  - `lpt_requested_backend`
  - `lpt_resolved_backend`
  - `lpt_driver`
  - `lpt_driver_path`
  - `lpt_failure_reason`
- This makes it easier to distinguish “disabled”, “not available on this machine”, and “driver selected successfully”.

## Cross-platform behavior

- macOS/Linux development machines should still be able to import and test the project without a display server or parallel-port driver.
- Windows lab machines can use the `inpout` backend as the preferred production path.
