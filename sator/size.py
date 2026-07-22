#!/usr/bin/env python3
"""Size parsing and formatting utilities."""

import re
from typing import Optional

# ═══════════════════════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def parse_size(val: str) -> Optional[int]:
    """Convert human-readable size to bytes."""
    val = val.strip().lower().replace(' ', '')
    m = re.match(r'^([0-9]+\.?[0-9]*)([kmgt]?i?b?)$', val)
    if not m:
        m = re.match(r'^([0-9]+\.?[0-9]*)([kmgt])$', val)
    if not m:
        return None
    num = float(m.group(1))
    unit = m.group(2)
    multipliers = {
        'k': 1024, 'kb': 1024, 'kib': 1024,
        'm': 1024**2, 'mb': 1024**2, 'mib': 1024**2,
        'g': 1024**3, 'gb': 1024**3, 'gib': 1024**3,
        't': 1024**4, 'tb': 1024**4, 'tib': 1024**4,
    }
    return int(num * multipliers.get(unit, 1))


def bytes_to_human(bytes_val: int) -> str:
    """Convert bytes to human-readable string."""
    if bytes_val >= 1024**4:
        return f"{bytes_val / 1024**4:.1f} TiB"
    elif bytes_val >= 1024**3:
        return f"{bytes_val / 1024**3:.1f} GiB"
    elif bytes_val >= 1024**2:
        return f"{bytes_val / 1024**2:.1f} MiB"
    elif bytes_val >= 1024:
        return f"{bytes_val / 1024:.1f} KiB"
    return f"{bytes_val} B"

