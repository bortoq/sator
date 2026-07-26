#!/usr/bin/env python3
"""Size parsing and formatting utilities."""

import re
from typing import Optional
from sator import settings

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
        'k': settings.KIB, 'kb': settings.KIB, 'kib': settings.KIB,
        'm': settings.MIB, 'mb': settings.MIB, 'mib': settings.MIB,
        'g': settings.GIB, 'gb': settings.GIB, 'gib': settings.GIB,
        't': settings.TIB, 'tb': settings.TIB, 'tib': settings.TIB,
    }
    return int(num * multipliers.get(unit, 1))


def bytes_to_human(bytes_val: int) -> str:
    """Convert bytes to human-readable string."""
    if bytes_val >= settings.TIB:
        return f"{bytes_val / settings.TIB:.1f} TiB"
    elif bytes_val >= settings.GIB:
        return f"{bytes_val / settings.GIB:.1f} GiB"
    elif bytes_val >= settings.MIB:
        return f"{bytes_val / settings.MIB:.1f} MiB"
    elif bytes_val >= settings.KIB:
        return f"{bytes_val / settings.KIB:.1f} KiB"
    return f"{bytes_val} B"

