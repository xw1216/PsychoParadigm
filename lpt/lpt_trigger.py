import ctypes
import platform
import signal
import time
from pathlib import Path

BASE_ADDRESS = 0xDF08
DLL_NAME = "inpoutx64.dll"


def load_inpout_dll(dll_name: str):
    if platform.system() != "Windows":
        raise RuntimeError("This script requires Windows because it uses inpout32/inpoutx64.")

    dll_path = Path(__file__).resolve().parent / dll_name
    if dll_path.exists():
        return ctypes.WinDLL(str(dll_path))

    dll_path = Path(dll_name)
    if dll_path.exists():
        return ctypes.WinDLL(str(dll_path.resolve()))

    try:
        return ctypes.WinDLL(dll_name)
    except OSError as exc:
        raise RuntimeError(
            f"Unable to load {dll_name}. Place the DLL next to this script or add it to PATH."
        ) from exc


def write_lpt_byte(out32, base_address: int, value: int) -> None:
    out32(base_address, value & 0xFF)


def hold_marker_until_stopped(base_address: int, marker: int, reset_value: int, out32) -> None:
    if not (0 <= base_address <= 0xFFFF):
        raise ValueError("base_address must be in 0x0000..0xFFFF")
    if not (0 <= marker <= 0xFF):
        raise ValueError("marker must be in 0..255")
    if not (0 <= reset_value <= 0xFF):
        raise ValueError("reset_value must be in 0..255")

    stop_requested = False

    def request_stop(*_args) -> None:
        nonlocal stop_requested
        stop_requested = True

    signal.signal(signal.SIGINT, request_stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, request_stop)

    write_lpt_byte(out32, base_address, marker)

    try:
        while not stop_requested:
            time.sleep(1.0)
    finally:
        write_lpt_byte(out32, base_address, reset_value)


MARKER = 1
RESET_VALUE = 0

def main() -> None:
    dll = load_inpout_dll(DLL_NAME)

    is_driver_open = dll.IsInpOutDriverOpen
    is_driver_open.restype = ctypes.c_bool
    if not is_driver_open():
        raise RuntimeError("InpOut driver did not open successfully.")

    out32 = dll.Out32
    out32.argtypes = [ctypes.c_short, ctypes.c_short]
    out32.restype = None
    hold_marker_until_stopped(BASE_ADDRESS, MARKER, RESET_VALUE, out32)


if __name__ == "__main__":
    main()