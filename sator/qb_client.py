#!/usr/bin/env python3
"""qBittorrent WebUI client."""

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from sator import settings
from typing import Optional, List

@dataclass
class QBConfig:
    url: str = settings.DEFAULT_QB_URL
    username: str = ""
    password: str = ""


class QBClient:
    """Client for qBittorrent WebUI API."""

    def __init__(self, config: QBConfig = None):
        self.config = config or QBConfig()
        self._cookie = None

    def _api_call(self, method: str, endpoint: str, data: dict = None) -> Optional[dict]:
        """Make an API call to qBittorrent."""
        url = f"{self.config.url.rstrip('/')}/api/v2/{endpoint.lstrip('/')}"
        encoded = urllib.parse.urlencode(data or {})
        if method.upper() == 'GET' and encoded:
            url += '?' + encoded
        for attempt in range(2):
            if self.config.username and not self._cookie and endpoint != 'auth/login':
                if not self._auth():
                    return {"error": "qBittorrent authentication failed"}
            req = urllib.request.Request(
                url, data=encoded.encode() if method.upper() != 'GET' and data else None,
                method=method)
            req.add_header('User-Agent', settings.UA_SATOR)
            if self._cookie:
                req.add_header('Cookie', self._cookie)
            try:
                resp = urllib.request.urlopen(req, timeout=settings.TIMEOUT_QB)
                body = resp.read().decode()
                if endpoint == 'auth/login':
                    self._cookie = resp.headers.get('Set-Cookie', '').split(';', 1)[0]
                    return {} if body.strip() == 'Ok.' else {"error": body.strip()}
                return json.loads(body) if body else {}
            except urllib.error.HTTPError as exc:
                if exc.code == 403 and self.config.username and attempt == 0:
                    self._cookie = None
                    continue
                return {"error": str(exc)}
            except Exception as exc:
                return {"error": str(exc)}
        return {"error": "qBittorrent authentication failed"}

    def _auth(self):
        """Authenticate once without recursively entering _api_call."""
        data = {'username': self.config.username, 'password': self.config.password}
        url = f"{self.config.url.rstrip('/')}/api/v2/auth/login"
        req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode(),
                                     headers={'User-Agent': settings.UA_SATOR}, method='POST')
        try:
            resp = urllib.request.urlopen(req, timeout=settings.TIMEOUT_QB)
            body = resp.read().decode().strip()
            self._cookie = resp.headers.get('Set-Cookie', '').split(';', 1)[0]
            if body == 'Ok.' and self._cookie:
                return True
            self._cookie = None
            return False
        except Exception:
            self._cookie = None
            return False

    def add_torrent(self, magnet: str, category: str = "", tags: str = "",
                    ratio_limit: float = -1, seed_time: int = -1) -> dict:
        """Add a torrent by magnet link."""
        data = {'urls': magnet}
        if category:
            data['category'] = category
        if tags:
            data['tags'] = tags.replace(' ', ',')
        if ratio_limit >= 0:
            data['ratioLimit'] = str(ratio_limit)
        if seed_time >= 0:
            data['seedingTimeLimit'] = str(seed_time)

        result = self._api_call('POST', 'torrents/add', data)
        if result and 'error' not in result:
            return {"status": "ok", "magnet": magnet[:settings.MAGNET_TRUNC] + "..."}
        return {"status": "error", "error": str(result), "magnet": magnet[:settings.MAGNET_TRUNC] + "..."}

    def get_torrents(self, filter: str = "all", category: str = "",
                     tags: str = "", sort: str = "") -> List[dict]:
        """Get list of torrents."""
        data = {'filter': filter}
        if category:
            data['category'] = category
        if tags:
            data['tags'] = tags.replace(' ', ',')
        if sort:
            data['sort'] = sort
        result = self._api_call('GET', 'torrents/info', data)
        return result if isinstance(result, list) else []

    def get_torrent_files(self, torrent_hash: str) -> List[dict]:
        """Get file list for a torrent by hash.

        Returns list of dicts with keys: index, name, size, progress, priority, etc.
        """
        data = {'hash': torrent_hash}
        result = self._api_call('GET', 'torrents/files', data)
        return result if isinstance(result, list) else []

    def rename_file(self, torrent_hash: str, old_path: str, new_path: str) -> dict:
        """Rename a single file inside a torrent.

        Args:
            torrent_hash: qBittorrent torrent hash.
            old_path: Current file path (relative to torrent root).
            new_path: New file path (relative to torrent root).

        Returns:
            Response dict (empty on success).
        """
        data = {
            'hash': torrent_hash,
            'oldPath': old_path,
            'newPath': new_path,
        }
        return self._api_call('POST', 'torrents/renameFile', data) or {}

    def rename_folder(self, torrent_hash: str, old_path: str, new_path: str) -> dict:
        """Rename a folder inside a torrent.

        Args:
            torrent_hash: qBittorrent torrent hash.
            old_path: Current folder path (relative to torrent root).
            new_path: New folder path (relative to torrent root).

        Returns:
            Response dict (empty on success).
        """
        data = {
            'hash': torrent_hash,
            'oldPath': old_path,
            'newPath': new_path,
        }
        return self._api_call('POST', 'torrents/renameFolder', data) or {}

    def set_category(self, hash: str, category: str) -> dict:
        """Set category for a torrent."""
        data = {'hashes': hash, 'category': category}
        return self._api_call('POST', 'torrents/setCategory', data) or {}

    def add_tags(self, hash: str, tags: str) -> dict:
        """Add tags to a torrent."""
        data = {'hashes': hash, 'tags': tags}
        return self._api_call('POST', 'torrents/addTags', data) or {}

    def set_seed_limits(self, hash: str, ratio_limit: float = -1,
                        seed_time: int = -1) -> dict:
        """Set seed ratio/time limits for a torrent."""
        data = {'hashes': hash}
        if ratio_limit >= 0:
            data['ratioLimit'] = str(ratio_limit)
        if seed_time >= 0:
            data['seedingTimeLimit'] = str(seed_time)
        return self._api_call('POST', 'torrents/setShareLimits', data) or {}


def _qb_add_simple(magnet: str, qb_url: str, category: str = '', tags: str = '', paused: bool = False) -> bool:
    """Simple qBittorrent add for direct download mode.

    Args:
        magnet: Magnet link to add.
        qb_url: Base URL of qBittorrent WebUI.
        category: Optional category label.
        tags: Optional space-separated tags.
        paused: If True, add the torrent in paused state (no download starts).

    Returns:
        True if the request was sent successfully, False on error.
    """
    from urllib.request import Request, urlopen
    from urllib.parse import urlencode
    import sys
    try:
        data = urlencode({'urls': magnet})
        if category:
            data += '&' + urlencode({'category': category})
        if tags:
            data += '&' + urlencode({'tags': tags.replace(' ', ',')})
        if paused:
            data += '&paused=true'
        req = Request(f'{qb_url.rstrip("/")}/api/v2/torrents/add',
                     data=data.encode(),
                     headers={'User-Agent': settings.UA_SATOR})
        urlopen(req, timeout=settings.TIMEOUT_QB_SIMPLE)
        return True
    except Exception as e:
        print(f'  ⚠ qB add error: {e}', file=sys.stderr)
        return False
