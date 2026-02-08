import subprocess
import sys
import time
from dataclasses import dataclass
from enum import StrEnum


class PrinterStatus(StrEnum):
    OK = "ok"
    BUSY = "busy"
    DISABLED = "disabled"
    UNKNOWN = "unknown"

    # there are many more states but none of these can be get reliable for all printers on all platforms.
    # so we focus on the 4 most important and fallback to UNKNOWN

    # OFFLINE = "offline"
    # PAPER_OUT = "paper_out"
    # COVER_OPEN = "cover_open"
    # JAM = "jam"


@dataclass
class PrinterStateChange:
    printer: str
    old: PrinterStatus | None
    new: PrinterStatus
    raw: str


def classify_linux(output):
    if "idle" in output:
        return PrinterStatus.OK
    if "disabled" in output:
        return PrinterStatus.DISABLED
    if "printing" in output:
        return PrinterStatus.BUSY

    return PrinterStatus.UNKNOWN


def get_printer_status_linux(printer_name: str):
    try:
        # force english because later parsing.
        status_raw = subprocess.check_output(
            ["lpstat", "-p", printer_name],
            text=True,
            stderr=subprocess.STDOUT,
            env={"LANG": "C", "LC_ALL": "C"},
        ).lower()
    except Exception as exc:
        raise RuntimeError(f"Error getting stats for printer '{printer_name}'") from exc

    status = classify_linux(status_raw)

    return status, status_raw


# -------------------------
# Windows (pywin32)
# -------------------------
def classify_windows(status_flags):
    BUSY = 0x00000200
    PRINTER_STATUS_PAUSED = 0x00000001
    OK = 0x00000000

    if status_flags == OK:
        return PrinterStatus.OK
    if status_flags & PRINTER_STATUS_PAUSED:
        return PrinterStatus.DISABLED
    if status_flags & BUSY:
        return PrinterStatus.BUSY

    return PrinterStatus.UNKNOWN


def get_printer_status_windows(printer_name):
    if sys.platform != "win32":
        raise RuntimeError("Windows-only function")

    import win32print

    try:
        handle = win32print.OpenPrinter(printer_name)
    except win32print.error as exc:
        raise RuntimeError(f"Error opening printer '{printer_name}' to get status") from exc

    try:
        info6 = win32print.GetPrinter(handle, 6)
        status_raw = info6["Status"]
    finally:
        win32print.ClosePrinter(handle)

    status = classify_windows(status_raw)

    return status, status_raw


# -------------------------
# Unified API
# -------------------------
def get_printer_status(printer_name):
    if sys.platform == "win32":
        return get_printer_status_windows(printer_name)
    elif sys.platform in ("linux", "darwin"):
        return get_printer_status_linux(printer_name)

    raise OSError(f"System '{sys.platform}' not supported.")


# -------------------------
# State Machine + Polling
# -------------------------
def monitor_printer(printer_name, callback, interval=1.0):
    last_state: PrinterStatus | None = None

    while True:
        new_state, new_state_raw = get_printer_status(printer_name)

        if new_state != last_state:
            event = PrinterStateChange(
                printer=printer_name,
                old=last_state,
                new=new_state,
                raw=new_state_raw,
            )
            callback(event)
            last_state = new_state

        time.sleep(interval)


# -------------------------
# Example usage
# -------------------------
if __name__ == "__main__":
    PRINTER = "Brother_MFC_L2720DW_series"
    PRINTER = "Canon_SELPHY_CP1300"
    PRINTER = "PDF"

    def on_state_change(event: PrinterStateChange):
        print(f"[STATE CHANGE] {event.printer}: {event.old} → {event.new}")
        print("RAW:", event.raw)

    monitor_printer(PRINTER, on_state_change, interval=1.0)
