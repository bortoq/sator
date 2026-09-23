"""Choose one result per BitTorrent info hash."""

import base64
import binascii
import re
import urllib.parse


def magnet_info_hash(magnet: str) -> str:
    """Return a canonical v1/v2 hash, or empty string for unknown magnets."""
    if not isinstance(magnet, str) or not magnet.startswith('magnet:?'):
        return ''
    topics = urllib.parse.parse_qs(urllib.parse.urlsplit(magnet).query).get('xt', [])
    for topic in topics:
        if re.fullmatch(r'urn:btih:[0-9a-fA-F]{40}', topic):
            return 'btih:' + topic[9:].lower()
        if re.fullmatch(r'urn:btih:[A-Za-z2-7]{32}', topic):
            try:
                return 'btih:' + base64.b32decode(topic[9:].upper()).hex()
            except binascii.Error:
                continue
        if re.fullmatch(r'urn:btmh:1220[0-9a-fA-F]{64}', topic):
            return 'btmh:' + topic[13:].lower()
    return ''


def deduplicate_torrents(torrents: list) -> list:
    """Keep the most seeded result for each known hash, preserving unknowns."""
    selected = []
    positions = {}
    for torrent in torrents:
        key = magnet_info_hash(torrent.get('magnet', ''))
        if not key:
            selected.append(torrent)
        elif key not in positions:
            positions[key] = len(selected)
            selected.append(torrent)
        elif torrent.get('seeders', 0) > selected[positions[key]].get('seeders', 0):
            selected[positions[key]] = torrent
    return selected
