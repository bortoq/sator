"""Hash based result consolidation."""

import base64

from sator.dedup import deduplicate_torrents, magnet_info_hash


def test_duplicate_hash_keeps_highest_seeder_count():
    low = {'magnet': 'magnet:?xt=urn:btih:' + 'A' * 40, 'seeders': 3, 'source': 'tpb'}
    high = {'magnet': 'magnet:?xt=urn:btih:' + 'a' * 40, 'seeders': 42,
            'source': 'torrentfunk'}
    other = {'magnet': 'magnet:?xt=urn:btih:' + 'b' * 40, 'seeders': 1}

    assert deduplicate_torrents([low, other, high]) == [high, other]


def test_base32_and_hex_info_hashes_are_equivalent():
    raw = bytes.fromhex('ab' * 20)
    base32_hash = base64.b32encode(raw).decode()

    assert magnet_info_hash('magnet:?xt=urn:btih:' + base32_hash) == (
        magnet_info_hash('magnet:?xt=urn:btih:' + raw.hex())
    )


def test_unknown_hashes_are_not_collapsed():
    rows = [{'magnet': ''}, {'magnet': 'magnet:?dn=one'}]
    assert deduplicate_torrents(rows) == rows
