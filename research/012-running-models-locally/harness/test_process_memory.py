from __future__ import annotations

import os

from .process_memory import read_process_memory


def test_reads_current_process_memory() -> None:
    memory = read_process_memory(os.getpid())

    assert memory.vm_size_kb is not None
    assert memory.vm_size_kb > 0

    assert memory.vm_rss_kb is not None
    assert memory.vm_rss_kb > 0

    assert memory.vm_hwm_kb is not None
    assert memory.vm_hwm_kb >= memory.vm_rss_kb

    assert memory.vm_swap_kb is not None
    assert memory.vm_swap_kb >= 0