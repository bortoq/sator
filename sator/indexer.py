#!/usr/bin/env python3
"""Tracker indexers: Nyaa, TPB, LimeTorrents, YTS, SolidTorrents, EZTV, TGx, YourBittorrent, TorrentFunk, Magnetz, GloTorrents."""

import html as htmlmod
import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import List, Callable
from sator.quality import QualityInfo
from sator import settings

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
        req = urllib.request.Request(url, headers={'User-Agent': settings.UA_INDEXER})
        try:
            resp = urllib.request.urlopen(req, timeout=settings.TIMEOUT_NYAA)
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
            # Extract detail page URL
            um = re.search(r'href="(/view/\d+)"', r)
            info_url = "https://nyaa.si" + um.group(1) if um else ""
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
                seeders=seeders, source="nyaa", info_url=info_url
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
                resp = urllib.request.urlopen(req, timeout=settings.TIMEOUT_TPB)
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
            # Extract detail page URL
            um = re.search(r'href="([^"]*/torrent/\d+/[^"]*)"', r)
            info_url = um.group(1) if um else ""
            # Ensure absolute URL
            if info_url and not info_url.startswith('http'):
                info_url = settings.TPB_FALLBACK_URL + info_url
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
                seeders=seeders, source="tpb", info_url=info_url
            ))
        return results


class LimeTorrentsIndexer(BaseIndexer):
    """LimeTorrents indexer (may be blocked by Cloudflare)."""
    name = "limetorrents"

    def search(self, query: str) -> List[TorrentResult]:
        sq = urllib.parse.quote(query)
        html = None
        # Try GET first
        url = f"{settings.LIMETORRENTS_BASE_URL}/search?q={sq}"
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
            })
            resp = urllib.request.urlopen(req, timeout=settings.TIMEOUT_LIMETORRENTS)
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
                    f"{settings.LIMETORRENTS_BASE_URL}/post/search.php",
                    data=data,
                    headers={
                        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
                        'Content-Type': 'application/x-www-form-urlencoded'
                    }
                )
                resp = urllib.request.urlopen(req, timeout=settings.TIMEOUT_LIMETORRENTS)
                html = resp.read().decode('utf-8', errors='replace')
            except Exception:
                return []

        if not html or ('access denied' in html.lower() or 'cloudflare' in html.lower()):
            return []

        results = []
        for m in re.finditer(r'<a\s+href="(/torrent/\d+/[^"]*)"\s+title="([^"]*)"', html):
            title = htmlmod.unescape(m.group(2)).strip()
            href = settings.LIMETORRENTS_BASE_URL + m.group(1)
            results.append(TorrentResult(
                title=title, magnet="", size_bytes=0, seeders=0,
                source="limetorrents", info_url=href
            ))
            if len(results) > settings.MAX_LIMETORRENTS_RESULTS:
                break
        return results


# ── YTS (Yify) — JSON API, movies only, high quality ─────────────────────

class YTSIndexer(BaseIndexer):
    """YTS (Yify) movie torrent indexer via JSON API."""
    name = "yts"

    def search(self, query: str) -> List[TorrentResult]:
        sq = urllib.parse.quote(query)
        url = f"https://yts.mx/api/v2/list_movies.json?query_term={sq}&limit={settings.YTS_API_LIMIT}"
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
            })
            resp = urllib.request.urlopen(req, timeout=settings.TIMEOUT_YTS)
            data = json.loads(resp.read().decode())
        except Exception:
            return []

        movies = data.get('data', {}).get('movies', [])
        if not movies:
            return []

        results = []
        for movie in movies:
            title = movie.get('title', '')
            year = movie.get('year', '')
            display_title = f"{title} {year}" if year else title
            torrents = movie.get('torrents', [])
            for t in torrents:
                quality = t.get('quality', '')
                ttype = t.get('type', '')  # 'bluray' or 'web'
                size_str = t.get('size', '0')
                seeds = int(t.get('seeds', 0))
                peers = int(t.get('peers', 0))
                ih = t.get('hash', '')
                if not ih:
                    continue
                # Build magnet from info_hash + common YTS trackers
                magnet = (
                    f"magnet:?xt=urn:btih:{ih}"
                    f"&dn={urllib.parse.quote(display_title)}"
                    f"&tr=udp://tracker.coppersurfer.tk:6969/announce"
                    f"&tr=udp://tracker.leechers-paradise.org:6969/announce"
                    f"&tr=udp://tracker.opentrackr.org:1337/announce"
                    f"&tr=udp://open.demonii.com:1337/announce"
                )
                # Parse size from string like "2.5 GB"
                size_bytes = 0
                sm = re.match(r'([0-9.]+)\s*(GB|MB|KB|TB)', size_str, re.I)
                if sm:
                    num = float(sm.group(1))
                    unit = sm.group(2).upper()
                    if unit == 'TB':
                        size_bytes = int(num * 1024**4)
                    elif unit == 'GB':
                        size_bytes = int(num * 1024**3)
                    elif unit == 'MB':
                        size_bytes = int(num * 1024**2)
                    elif unit == 'KB':
                        size_bytes = int(num * 1024)
                # Compose quality label for scoring
                quality_label = f"{quality} {ttype.title()}" if ttype else quality
                title_tag = f"{display_title} {quality_label}"
                results.append(TorrentResult(
                    title=title_tag, magnet=magnet, size_bytes=size_bytes,
                    seeders=seeds + peers, source="yts"
                ))
        return results


# ── SolidTorrents — JSON API, meta-search ───────────────────────────────

class SolidTorrentsIndexer(BaseIndexer):
    """SolidTorrents meta-search indexer via JSON API."""
    name = "solidtorrents"

    def search(self, query: str) -> List[TorrentResult]:
        sq = urllib.parse.quote(query)
        url = f"{settings.SOLIDTORRENTS_API_URL}{sq}"
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
            })
            resp = urllib.request.urlopen(req, timeout=settings.TIMEOUT_SOLIDTORRENTS)
            data = json.loads(resp.read().decode())
        except Exception:
            return []

        items = data.get('results', []) if isinstance(data, dict) else []
        results = []
        for item in items[:settings.MAX_SOLIDTORRENTS_RESULTS]:
            title = item.get('title', '')
            if not title:
                continue
            ih = item.get('infohash', '')
            if not ih:
                continue
            # Build magnet link from info hash
            magnet = f"magnet:?xt=urn:btih:{ih}&dn={urllib.parse.quote(title)}&tr=udp://tracker.opentrackr.org:1337/announce&tr=udp://tracker.torrent.eu.org:451/announce"
            size_bytes = int(item.get('size', 0))
            seeds = int(item.get('seeders', 0))
            results.append(TorrentResult(
                title=htmlmod.unescape(title), magnet=magnet,
                size_bytes=size_bytes, seeders=seeds, source="solidtorrents"
            ))
        return results


# ── EZTV — TV episodes via HTML scraping ────────────────────────────────

class EZTVIndexer(BaseIndexer):
    """EZTV torrent indexer (TV shows/episodes)."""
    name = "eztv"

    def search(self, query: str) -> List[TorrentResult]:
        sq = urllib.parse.quote(query)
        url = f"https://eztvx.to/search/{sq}"
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
            })
            resp = urllib.request.urlopen(req, timeout=settings.TIMEOUT_EZTV)
            html = resp.read().decode('utf-8', errors='replace')
        except Exception:
            return []

        results = []
        for row in re.findall(r'<tr[^>]*name="hover"[^>]*>(.*?)</tr>', html, re.DOTALL):
            # Title
            tm = re.search(r'href="/ep/[^"]+"\s+[^>]*>([^<]+)</a>', row)
            if not tm:
                continue
            title = htmlmod.unescape(tm.group(1)).strip()
            # Magnet
            mm = re.search(r'href="(magnet:[^"]*)"', row)
            if not mm:
                continue
            magnet = htmlmod.unescape(mm.group(1))
            # Size
            sm = re.search(r'<td[^>]*class[^>]*>[^<]*</td>\s*<td[^>]*class[^>]*>\s*([0-9.]+)\s*(GB|MB|KB)\s*</td>', row, re.DOTALL)
            size_bytes = 0
            if sm:
                num = float(sm.group(1))
                unit = sm.group(2).upper()
                if unit == 'GB':
                    size_bytes = int(num * 1024**3)
                elif unit == 'MB':
                    size_bytes = int(num * 1024**2)
                elif unit == 'KB':
                    size_bytes = int(num * 1024)
            # Seeders
            sdm = re.search(r'<td[^>]*class[^>]*>\s*(\d+)\s*</td>\s*<td[^>]*class[^>]*>\s*\d+\s*</td>\s*<td[^>]*class[^>]*>', row, re.DOTALL)
            seeders = int(sdm.group(1)) if sdm else 0
            results.append(TorrentResult(
                title=title, magnet=magnet, size_bytes=size_bytes,
                seeders=seeders, source="eztv"
            ))
        return results


# ── TorrentGalaxy (TGx) — general torrents via HTML scraping ───────────

class TGxIndexer(BaseIndexer):
    """TorrentGalaxy torrent indexer (movies, TV, games, apps)."""
    name = "tgx"

    def search(self, query: str) -> List[TorrentResult]:
        sq = urllib.parse.quote(query)
        url = f"https://torrentgalaxy.to/torrents.php?search={sq}&sort=seeders&order=desc"
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
            })
            resp = urllib.request.urlopen(req, timeout=settings.TIMEOUT_TGX)
            html = resp.read().decode('utf-8', errors='replace')
        except Exception:
            return []

        results = []
        for row in re.findall(r'<div[^>]*class="[^"]*tgxtable[^"]*"[^>]*>(.*?)</div>\s*</div>', html, re.DOTALL):
            # Title
            tm = re.search(r'<a[^>]*href="/torrent/\d+/[^"]*"[^>]*>\s*([^<]+)\s*</a>', row)
            if not tm:
                continue
            title = htmlmod.unescape(tm.group(1)).strip()
            # Magnet
            mm = re.search(r'href="(magnet:[^"]*)"', row)
            if not mm:
                continue
            magnet = htmlmod.unescape(mm.group(1))
            # Size
            sm = re.search(r'<span[^>]*class="[^"]*badge[^"]*"[^>]*>\s*([0-9.]+)\s*(TB|GB|MB|KB)\s*</span>', row, re.I)
            size_bytes = 0
            if sm:
                num = float(sm.group(1))
                unit = sm.group(2).upper()
                if unit == 'TB':
                    size_bytes = int(num * 1024**4)
                elif unit == 'GB':
                    size_bytes = int(num * 1024**3)
                elif unit == 'MB':
                    size_bytes = int(num * 1024**2)
                elif unit == 'KB':
                    size_bytes = int(num * 1024)
            # Seeders
            sdm = re.search(r'<td[^>]*>\s*(\d+)\s*</td>\s*<td[^>]*>\s*\d+\s*</td>', row, re.DOTALL)
            seeders = int(sdm.group(1)) if sdm else 0
            results.append(TorrentResult(
                title=title, magnet=magnet, size_bytes=size_bytes,
                seeders=seeders, source="tgx"
            ))
        return results


# ── Detail page enrichment ────────────────────────────────────────────
# Language patterns for detail page parsing
_DETAIL_LANG_CODES = {
    'english': 'en', 'eng': 'en',
    'russian': 'ru', 'russkiy': 'ru', 'russkij': 'ru',
    'french': 'fr', 'français': 'fr', 'francais': 'fr',
    'german': 'de', 'deutsch': 'de',
    'spanish': 'es', 'español': 'es', 'espanol': 'es',
    'italian': 'it', 'italiano': 'it',
    'portuguese': 'pt', 'português': 'pt', 'portugues': 'pt',
    'japanese': 'ja', '日本語': 'ja',
    'chinese': 'zh', '中文': 'zh',
    'korean': 'ko', '한국어': 'ko',
    'arabic': 'ar', 'العربية': 'ar',
    'hindi': 'hi', 'हिन्दी': 'hi',
    'dutch': 'nl', 'nederlands': 'nl',
    'polish': 'pl', 'polski': 'pl',
    'swedish': 'sv', 'svenska': 'sv',
    'danish': 'da', 'dansk': 'da',
    'norwegian': 'no', 'norsk': 'no',
    'finnish': 'fi', 'suomi': 'fi',
    'czech': 'cs', 'čeština': 'cs',
    'hungarian': 'hu', 'magyar': 'hu',
    'romanian': 'ro', 'română': 'ro',
    'ukrainian': 'uk', 'українська': 'uk',
    'greek': 'el', 'ελληνικά': 'el',
    'turkish': 'tr', 'türkçe': 'tr',
    'thai': 'th', 'ไทย': 'th',
    'vietnamese': 'vi', 'tiếng việt': 'vi',
    'hebrew': 'he', 'עברית': 'he',
}

def _enrich_from_detail(result: TorrentResult) -> dict:
    '''Fetch detail page and extract metadata not found in title.
    
    Returns dict with optional keys: languages, subs, quality_override.
    Returns empty dict on any error or if no info_url.
    '''
    if not result.info_url:
        return {}

    try:
        req = urllib.request.Request(result.info_url, headers={
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
        })
        resp = urllib.request.urlopen(req, timeout=settings.TIMEOUT_DETAIL)
        html = resp.read().decode('utf-8', errors='replace')
    except Exception:
        return {}

    enriched = {}
    page_lower = html.lower()

    # Extract languages from page text
    detected_langs = set()
    for name, code in _DETAIL_LANG_CODES.items():
        if name in page_lower:
            detected_langs.add(code)
    # Also look for ISO codes in common patterns
    for iso in ('en', 'ru', 'fr', 'de', 'es', 'it', 'pt', 'ja', 'zh', 'ko'):
        if re.search(r'\blang(?:uage)?[=:;\s]+' + iso + r'\b', page_lower):
            detected_langs.add(iso)
        if re.search(r'\b' + iso + r'\s+(?:lang|audio|sub)', page_lower):
            detected_langs.add(iso)

    if detected_langs:
        enriched['languages'] = list(detected_langs)

    # Extract subtitle info
    has_subs = False
    for pat in ['subtitle', 'subtitles', 'subs', 'sub', 'closed captions']:
        if pat in page_lower:
            # Make sure it's not "no subtitles" or similar negative
            neg = re.search(r'no\s+' + pat, page_lower)
            if not neg:
                has_subs = True
                break
    
    # Extract subtitle languages
    if has_subs:
        sub_langs = set()
        for name, code in _DETAIL_LANG_CODES.items():
            # Match patterns like "subtitles: English", "sub: english"
            if re.search(r'sub(?:title)?s?[=:;\s]+' + name, page_lower):
                sub_langs.add(code)
            # Match patterns like "English subtitles"
            if re.search(name + r'\s+sub(?:title)?s?', page_lower):
                sub_langs.add(code)
        # Common patterns: "Subtitles: English", "Sub: en", etc.
        for iso in ('en', 'ru', 'fr', 'de', 'es', 'it', 'pt'):
            if re.search(r'sub(?:title)?[=:;\s]+' + iso, page_lower):
                sub_langs.add(iso)
            if re.search(iso + r'\s+sub', page_lower):
                sub_langs.add(iso)
        if sub_langs:
            enriched['subs'] = list(sub_langs)
        elif has_subs:
            enriched['subs'] = ['en']  # unknown subs assumed English

    return enriched



# ── Magnetz — JSON API ─────────────────────────────────────────────────

class MagnetzIndexer(BaseIndexer):
    """Magnetz.eu torrent search via JSON API."""
    name = "magnetz"

    def search(self, query: str) -> List[TorrentResult]:
        sq = urllib.parse.quote(query)
        url = f"https://magnetz.eu/api/magnets/search?query={sq}"
        try:
            req = urllib.request.Request(url, headers={'User-Agent': settings.UA_INDEXER})
            resp = urllib.request.urlopen(req, timeout=settings.TIMEOUT_MAGNETZ)
            data = json.loads(resp.read().decode())
        except Exception:
            return []
        items = data.get('data', [])
        results = []
        for item in items:
            name = item.get('name', '')
            magnet = item.get('magnet_link', '')
            if not name or not magnet:
                continue
            size_bytes = int(item.get('size', 0))
            health = item.get('health', 0)
            # Estimate seeders from health (0-1) and total swarm
            # health * some_factor isn't reliable; use 0 as default
            results.append(TorrentResult(
                title=name, magnet=magnet, size_bytes=size_bytes,
                seeders=0, source=self.name,
            ))
        return results


# 
# ── GloTorrents — HTML scraping ────────────────────────────────────────

class GloTorrentsIndexer(BaseIndexer):
    """GloTorrents (glodls.to) torrent indexer via HTML scraping."""
    name = "glotorrents"

    def search(self, query: str) -> List[TorrentResult]:
        sq = urllib.parse.quote(query)
        url = f"{settings.GLOTORRENTS_BASE_URL}/search_results.php?search={sq}"
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml',
            })
            resp = urllib.request.urlopen(req, timeout=settings.TIMEOUT_GLOTORRENTS)
            html = resp.read().decode('utf-8', errors='replace')
        except Exception:
            return []
        results = []
        for row in re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL):
            if '<th' in row:
                continue
            mm = re.search(r'href="(magnet:[^"]*)"', row)
            if not mm:
                continue
            magnet = htmlmod.unescape(mm.group(1))
            # Title from <a title="..."
            tm = re.search(r'<a[^>]*title="([^"]*)"', row)
            if not tm:
                continue
            title = htmlmod.unescape(tm.group(1)).strip()
            # Size: find <td class='ttable_col1' align='center'>X.XX GB</td>
            tds = re.findall(r"<td[^>]*class='ttable_col[12]'[^>]*align='center'[^>]*>([^<]*)</td>", row)
            size_bytes = 0
            if len(tds) >= 1:
                sm = re.match(r'([0-9.]+)\s*(TB|GB|MB|KB)', tds[0].strip(), re.I)
                if sm:
                    num = float(sm.group(1))
                    unit = sm.group(2).upper()
                    if unit == 'TB': size_bytes = int(num * 1024**4)
                    elif unit == 'GB': size_bytes = int(num * 1024**3)
                    elif unit == 'MB': size_bytes = int(num * 1024**2)
                    elif unit == 'KB': size_bytes = int(num * 1024)
            # Seeders: <font color='green'><b>N</b></font>
            sdm = re.search(r"<font color='green'><b>([0-9]+)</b></font>", row)
            seeders = int(sdm.group(1)) if sdm else 0
            results.append(TorrentResult(
                title=title, magnet=magnet, size_bytes=size_bytes,
                seeders=seeders, source=self.name,
            ))
        return results


# ── YourBittorrent / TorrentFunk — identical JSON API ───────────────────

class _YBLikeIndexer(BaseIndexer):
    """Base for trackers using the YourBittorrent/TorrentFunk JSON API."""
    base_url = ""  # set by subclass

    def search(self, query: str) -> List[TorrentResult]:
        sq = urllib.parse.quote(query)
        url = f"{self.base_url}/api/search.json?q={sq}&limit=100"
        try:
            req = urllib.request.Request(url, headers={'User-Agent': settings.UA_INDEXER})
            resp = urllib.request.urlopen(req, timeout=settings.TIMEOUT_YB_LIKE)
            data = json.loads(resp.read().decode())
        except Exception:
            return []
        raw = data.get('results', [])
        results = []
        for r in raw:
            name = r.get('name', '')
            magnet = r.get('magnet', '')
            if not name or not magnet:
                continue
            size_bytes = int(r.get('size_bytes', 0))
            seeds = int(r.get('seeds', 0))
            results.append(TorrentResult(
                title=name, magnet=magnet, size_bytes=size_bytes,
                seeders=seeds, source=self.name,
            ))
        return results


class YourBittorrentIndexer(_YBLikeIndexer):
    name = "yourbittorrent"
    base_url = "https://yourbittorrent.com"


class TorrentFunkIndexer(_YBLikeIndexer):
    name = "torrentfunk"
    base_url = "https://www.torrentfunk.com"


# ── AniLibria (anilibria.top) ────────────────────────────────────────────

class AniLibriaIndexer(BaseIndexer):
    """AniLibria anime torrent indexer via JSON API."""
    name = "anilibria"

    def search(self, query: str) -> List[TorrentResult]:
        sq = urllib.parse.quote(query)
        url = f"{settings.ANILIBRIA_API_URL}/releases/releases?search={sq}&limit={settings.ANILIBRIA_SEARCH_LIMIT}"
        try:
            req = urllib.request.Request(url, headers={'User-Agent': settings.UA_INDEXER})
            resp = urllib.request.urlopen(req, timeout=settings.TIMEOUT_ANILIBRIA)
            data = json.loads(resp.read().decode())
        except Exception:
            return []
        releases = data.get('data', data) if isinstance(data, dict) else data
        if isinstance(releases, dict):
            releases = releases.get('data', [])
        if not isinstance(releases, list):
            return []
        results = []
        for r in releases:
            # Extract title from various possible fields
            names = r.get('names', {}) or {}
            title = (r.get('name', '') or r.get('title', '') or
                     names.get('ru', '') or names.get('en', ''))
            if not title:
                continue
            # Extract magnet from torrent data
            magnet = r.get('magnet', '') or r.get('torrent_magnet', '')
            if not magnet:
                torrents_data = r.get('torrents', {})
                if isinstance(torrents_data, dict):
                    for t in torrents_data.values():
                        if isinstance(t, dict):
                            magnet = t.get('magnet', '') or t.get('url', '') or ''
                            if magnet:
                                break
                elif isinstance(torrents_data, list):
                    for t in torrents_data:
                        if isinstance(t, dict):
                            magnet = t.get('magnet', '') or t.get('url', '') or ''
                            if magnet:
                                break
            size_bytes = 0
            seeders = 0
            # Languages: check if title has Cyrillic
            import re as _re
            has_cyrillic = bool(_re.search(r'[а-яА-ЯёЁ]', title))
            languages = ['ru'] if has_cyrillic else []
            results.append(TorrentResult(
                title=title, magnet=magnet, size_bytes=size_bytes,
                seeders=seeders, source=self.name, languages=languages,
            ))
        return results


# ── RuTor (rutor.info) ───────────────────────────────────────────────────

class RuTorIndexer(BaseIndexer):
    """RuTor torrent indexer (Russian tracker, HTML scraping)."""
    name = "rutor"

    def search(self, query: str) -> List[TorrentResult]:
        sq = urllib.parse.quote(query)
        results = []
        mirrors = list(settings.RUTOR_MIRRORS)
        if not mirrors:
            mirrors = ['https://rutor.info']
        for base_url in mirrors:
            try:
                url = f"{base_url}/search/{sq}"
                req = urllib.request.Request(url, headers={
                    'User-Agent': settings.UA_INDEXER,
                })
                resp = urllib.request.urlopen(req, timeout=settings.TIMEOUT_RUTOR)
                html = resp.read().decode('utf-8', errors='replace')
                if not html:
                    continue
                # Parse HTML table rows
                import re as _re
                # Find torrent rows: <tr class="gai"> or <tr class="tum"> ...
                for row in _re.finditer(
                    r'<tr[^>]*class="(?:gai|tum|sun)"[^>]*>(.*?)</tr>',
                    html, _re.DOTALL | _re.IGNORECASE
                ):
                    row_html = row.group(1)
                    # Extract title from <a> tag
                    tm = _re.search(r'<a[^>]*href="(/torrent/\d+[^"]*)"[^>]*>([^<]+)</a>', row_html)
                    if not tm:
                        continue
                    title = htmlmod.unescape(tm.group(2)).strip()
                    info_url = base_url + tm.group(1)
                    # Extract magnet
                    mm = _re.search(r'href="(magnet:[^"]*)"', row_html)
                    magnet = htmlmod.unescape(mm.group(1)) if mm else ''
                    # Size
                    sm = _re.search(r'<td[^>]*>([0-9.]+)\s*(KiB|MiB|GiB|TiB)[^<]*</td>', row_html)
                    size_bytes = 0
                    if sm:
                        num = float(sm.group(1))
                        unit = sm.group(2).upper()
                        if unit == 'TiB': size_bytes = int(num * 1024**4)
                        elif unit == 'GiB': size_bytes = int(num * 1024**3)
                        elif unit == 'MiB': size_bytes = int(num * 1024**2)
                        elif unit == 'KiB': size_bytes = int(num * 1024)
                    # Seeders / leechers: typically last two <td> or <span>
                    tds = _re.findall(r'<td[^>]*>([0-9]+)</td>', row_html)
                    seeders = int(tds[-2]) if len(tds) >= 2 else 0
                    # Language detection: Cyrillic or dub markers
                    has_cyrillic = bool(_re.search(r'[а-яА-ЯёЁ]', title))
                    has_dub_marker = bool(_re.search(r'\|\s*[LDP]\s*\|', title))
                    languages = ['ru'] if (has_cyrillic or has_dub_marker) else []
                    results.append(TorrentResult(
                        title=title, magnet=magnet, size_bytes=size_bytes,
                        seeders=seeders, source=self.name, info_url=info_url,
                        languages=languages,
                    ))
                # If we got results from this mirror, stop
                if results:
                    break
            except Exception:
                continue
        return results


# Registry of available indexers
INDEXERS = {
    'nyaa': NyaaIndexer(),
    'tpb': TPBIndexer(),
    'limetorrents': LimeTorrentsIndexer(),
    'yts': YTSIndexer(),
    'solidtorrents': SolidTorrentsIndexer(),
    'eztv': EZTVIndexer(),
    'tgx': TGxIndexer(),
    'yourbittorrent': YourBittorrentIndexer(),
    'torrentfunk': TorrentFunkIndexer(),
    'magnetz': MagnetzIndexer(),
    'glotorrents': GloTorrentsIndexer(),
    'anilibria': AniLibriaIndexer(),
    'rutor': RuTorIndexer(),
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
        trackers = list(settings.DEFAULT_TRACKERS)
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

