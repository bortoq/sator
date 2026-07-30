#!/usr/bin/env python3
"""Utility functions for the CLI — extracted from cli.py to reduce module size."""

import json
import os
import sys


# ── File parsing ───────────────────────────────────────────────────────────

def _parse_sator_file(path: str) -> list:
    """Parse a sator-format file and return list of dicts with magnet + metadata.

    File format (sator -o output)::

        # [source] title
        # Size: ... | quality_label | seeders: N
        # Meta: {"show_name": "...", "season": N, "episode": N, ...}
        magnet:?xt=urn:btih:...

    Lines starting with ``# Meta:`` contain JSON metadata for re-ingestion.
    Plain magnet lines are also accepted (backward compat).
    """
    if not os.path.exists(path):
        print(f'\u2716 File not found: {path}', file=sys.stderr)
        sys.exit(1)
    entries = []
    current_meta = {}
    with open(path) as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            if s.startswith('# Meta:'):
                try:
                    current_meta = json.loads(s[7:].strip())
                except (json.JSONDecodeError, ValueError):
                    current_meta = {}
            elif s.startswith('#') or s.startswith('//'):
                continue
            elif s.startswith('magnet:'):
                entry: dict = {'magnet': s}
                if current_meta.get('show_name'):
                    entry['show_name'] = current_meta['show_name']
                if current_meta.get('season'):
                    entry['season'] = int(current_meta['season'])
                if current_meta.get('episode'):
                    entry['episode'] = int(current_meta['episode'])
                entries.append(entry)
                current_meta = {}
            else:
                raise ValueError(f"Unexpected line in sator file: {s[:80]!r}")
    return entries
