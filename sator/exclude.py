#!/usr/bin/env python3
"""Blacklist patterns for excluding low-quality torrents."""

import re
from typing import List

_DEFAULT_EXCLUDES = [
    'CAM', 'HDCAM', 'TELESYNC', 'TS', 'SCR', 'SCREENER',
    'HC', 'SUBBED', 'DVDSCR', 'R5',
]

def is_excluded(title: str, excludes: List[str]) -> bool:
    """Check if a torrent title matches any exclude pattern.
    
    Short patterns (< 5 chars) match as whole tokens (split by separators).
    Long patterns match as substring anywhere in the title.
    Case-insensitive.
    """
    title_upper = title.upper()
    tokens = set(re.split(r'[\s._\-\[\]()]+', title_upper))
    
    for pattern in excludes:
        p = pattern.strip().upper()
        if not p:
            continue
        if len(p) < 5:
            if p in tokens:
                return True
        else:
            if p in title_upper:
                return True
    
    return False
