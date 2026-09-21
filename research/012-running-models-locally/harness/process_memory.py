from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProcessMemory:
    vm_peak_kb: int | None
    vm_size_kb: int | None
    vm_hwm_kb: int | None
    vm_rss_kb: int | None
    rss_anon_kb: int | None
    rss_file_kb: int | None
    vm_data_kb: int | None
    vm_swap_kb: int | None


_FIELD_NAMES = {
    "VmPeak": "vm_peak_kb",
    "VmSize": "vm_size_kb",
    "VmHWM": "vm_hwm_kb",
    "VmRSS": "vm_rss_kb",
    "RssAnon": "rss_anon_kb",
    "RssFile": "rss_file_kb",
    "VmData": "vm_data_kb",
    "VmSwap": "vm_swap_kb",
}


def read_process_memory(pid: int) -> ProcessMemory:
    status_path = Path(f"/proc/{pid}/status")

    values: dict[str, int | None] = {
        field_name: None for field_name in _FIELD_NAMES.values()
    }

    for line in status_path.read_text(encoding="utf-8").splitlines():
        if ":" not in line:
            continue

        key, raw_value = line.split(":", 1)

        destination = _FIELD_NAMES.get(key)
        if destination is None:
            continue

        parts = raw_value.split()
        if not parts:
            continue

        try:
            values[destination] = int(parts[0])
        except ValueError:
            continue

    return ProcessMemory(**values)