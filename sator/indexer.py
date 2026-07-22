#!/usr/bin/env python3
"""Tracker indexers: Nyaa, TPB, LimeTorrents."""

import html as htmlmod
import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Optional, List, Callable, Tuple
from sator.quality import QualityInfo

@dataclass
class TorrentResult:
    title: str = ""
    magnet: str = ""
    size_bytes: int = 0
    seeders: int = 0
    source: str = ""
    info_url: str = ""
    quality: QualityInfo = field(default_factory=QualityInfo)
    languages: List[str] = field(default_factory=list)


class BaseIndexer:
    """Base class for tracker indexers."""
    name = "base"

    def search(self, query: str) -> List[TorrentResult]:
        raise NotImplementedError


class NyaaIndexer(BaseIndexer):
    """Nyaa.si torrent indexer."""
    name = "nyaa"

    def search(self, query: str) -> List[TorrentResult]:
        sq = urllib.parse.quote(query)
        url = f"https://nyaa.si/?q={sq}&f=0&c=0_0"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'})
        try:
            resp = urllib.request.urlopen(req, timeout=15)
            html = resp.read().decode('utf-8', errors='replace')
        except Exception:
            return []

        results = []
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL)
        for r in rows:
            if '<th' in r:
                continue
            tm = re.search(r'href="/view/\d+"\s+title="([^"]*)"', r)
            if not tm:
                continue
            title = htmlmod.unescape(tm.group(1)).strip()
            mm = re.search(r'href="(magnet:[^"]*)"', r)
            if not mm:
                continue
            magnet = htmlmod.unescape(mm.group(1))
            sm = re.search(r'<td class="text-center">([0-9.]+)\s*(KiB|MiB|GiB|TiB)\s*</td>', r)
            size_bytes = 0
            if sm:
                num = float(sm.group(1))
                unit = sm.group(2)
                if unit == "TiB":
                    size_bytes = int(num * 1024**4)
                elif unit == "GiB":
                    size_bytes = int(num * 1024**3)
                elif unit == "MiB":
                    size_bytes = int(num * 1024**2)
                elif unit == "KiB":
                    size_bytes = int(num * 1024)
            tds = re.findall(r'<td class="text-center">([^<]*)</td>', r)
            seeders = 0
            if len(tds) >= 6:
                try:
                    seeders = int(tds[4].strip())
                except ValueError:
                    seeders = 0
            results.append(TorrentResult(
                title=title, magnet=magnet, size_bytes=size_bytes,
                seeders=seeders, source="nyaa"
            ))
        return results


class TPBIndexer(BaseIndexer):
    """The Pirate Bay torrent indexer (multiple mirrors)."""
    name = "tpb"
    mirrors = [
        "https://tpb.party",
        "https://piratebay.party",
    ]

    def search(self, query: str) -> List[TorrentResult]:
        sq = urllib.parse.quote(query)
        page_html = None
        for mirror in self.mirrors:
            url = f"{mirror}/search/{sq}/1/99/0"
            try:
                req = urllib.request.Request(url, headers={
                    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
                })
                resp = urllib.request.urlopen(req, timeout=20)
                page_html = resp.read().decode('utf-8', errors='replace')
                if page_html and 'magnet:' in page_html:
                    break
            except Exception:
                continue
            page_html = None

        if not page_html:
            return []

        results = []
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', page_html, re.DOTALL)
        for r in rows:
            if 'magnet:' not in r:
                continue
            # Title: match absolute or relative torrent URLs
            tm = re.search(r'<a[^>]*href="[^"]*/torrent/\d+/[^"]*"[^>]*>([^<]+)</a>', r)
            if not tm:
                continue
            title = htmlmod.unescape(tm.group(1)).strip()
            mm = re.search(r'href="(magnet:[^"]*)"', r)
            if not mm:
                continue
            magnet = htmlmod.unescape(mm.group(1))
            # Size: first align="right" td with GiB/MiB/KiB/TiB
            sm = re.search(r'<td[^>]*align="right"[^>]*>([0-9.]+)(?:\s|&nbsp;)*(GiB|MiB|KiB|TiB)\s*</td>', r)
            size_bytes = 0
            if sm:
                num = float(sm.group(1))
                unit = sm.group(2)
                if unit == "TiB":
                    size_bytes = int(num * 1024**4)
                elif unit == "GiB":
                    size_bytes = int(num * 1024**3)
                elif unit == "MiB":
                    size_bytes = int(num * 1024**2)
                elif unit == "KiB":
                    size_bytes = int(num * 1024)
            # Seeders: second align="right" td
            tds = re.findall(r'<td[^>]*align="right"[^>]*>(\d+)</td>', r)
            seeders = int(tds[0]) if tds else 0
            results.append(TorrentResult(
                title=title, magnet=magnet, size_bytes=size_bytes,
                seeders=seeders, source="tpb"
            ))
        return results


class LimeTorrentsIndexer(BaseIndexer):
    """LimeTorrents indexer (may be blocked by Cloudflare)."""
    name = "limetorrents"

    def search(self, query: str) -> List[TorrentResult]:
        sq = urllib.parse.quote(query)
        html = None
        # Try GET first
        url = f"https://www.limetorrents.fun/search?q={sq}"
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
            })
            resp = urllib.request.urlopen(req, timeout=15)
            html = resp.read().decode('utf-8', errors='replace')
        except Exception:
            pass

        # Check for Cloudflare block
        if html and ('access denied' in html.lower() or 'just a moment' in html.lower() or 'cloudflare' in html.lower()):
            html = None

        # Try POST if GET failed
        if not html:
            try:
                data = urllib.parse.urlencode({'q': sq}).encode()
                req = urllib.request.Request(
                    "https://www.limetorrents.fun/post/search.php",
                    data=data,
                    headers={
                        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
                        'Content-Type': 'application/x-www-form-urlencoded'
                    }
                )
                resp = urllib.request.urlopen(req, timeout=15)
                html = resp.read().decode('utf-8', errors='replace')
            except Exception:
                return []

        if not html or ('access denied' in html.lower() or 'cloudflare' in html.lower()):
            return []

        results = []
        for m in re.finditer(r'<a\s+href="(/torrent/\d+/[^"]*)"\s+title="([^"]*)"', html):
            title = htmlmod.unescape(m.group(2)).strip()
            href = "https://www.limetorrents.fun" + m.group(1)
            results.append(TorrentResult(
                title=title, magnet="", size_bytes=0, seeders=0,
                source="limetorrents", info_url=href
            ))
            if len(results) > 30:
                break
        return results


# Registry of available indexers
INDEXERS = {
    'nyaa': NyaaIndexer(),
    'tpb': TPBIndexer(),
    'limetorrents': LimeTorrentsIndexer(),
}

def search_all(query: str, trackers: List[str] = None,
               progress_cb: Callable[[str, str, int, str], None] = None
               ) -> List[TorrentResult]:
    """Search across multiple trackers.
    progress_cb(name, status, count, error_msg='') is called per tracker:
      - 'requesting': about to query
      - 'ok': success, count=results count
      - 'error': failed, error_msg=reason
    """
    if trackers is None:
        trackers = ['nyaa', 'tpb']
    results = []
    for name in trackers:
        indexer = INDEXERS.get(name)
        if not indexer:
            continue
        if progress_cb:
            progress_cb(name, 'requesting', 0, '')
        try:
            raw = indexer.search(query)
            results.extend(raw)
            if progress_cb:
                progress_cb(name, 'ok', len(raw), '')
        except Exception as e:
            if progress_cb:
                progress_cb(name, 'error', 0, str(e))
            continue
    return results

