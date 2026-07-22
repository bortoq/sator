#!/usr/bin/env python3
"""qBittorrent WebUI client."""

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Optional, List

@dataclass
class QBConfig:
    url: str = "http://localhost:8090"
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
        req = urllib.request.Request(url, data=encoded.encode() if data else None,
                                     method=method)
        req.add_header('User-Agent', 'sator/0.1')
        if self._cookie:
            req.add_header('Cookie', self._cookie)

        try:
            # Auth first if needed
            if self.config.username and not self._cookie:
                self._auth()

            resp = urllib.request.urlopen(req, timeout=15)
            if endpoint == 'auth/login':
                self._cookie = resp.headers.get('Set-Cookie', '')
            body = resp.read().decode()
            if body:
                return json.loads(body)
            return {}
        except urllib.error.HTTPError as e:
            if e.code == 403 and self.config.username and not getattr(self, '_auth_attempted', False):
                self._auth_attempted = True
                self._auth()
                result = self._api_call(method, endpoint, data)
                self._auth_attempted = False
                return result
            return {"error": str(e)}
        except Exception as e:
            return {"error": str(e)}

    def _auth(self):
        """Authenticate with qBittorrent."""
        data = {'username': self.config.username, 'password': self.config.password}
        result = self._api_call('POST', 'auth/login', data)
        if result and 'error' not in result:
            self._auth_attempted = False

    def add_torrent(self, magnet: str, category: str = "", tags: str = "",
                    ratio_limit: float = -1, seed_time: int = -1) -> dict:
        """Add a torrent by magnet link."""
        data = {'urls': magnet}
        if category:
            data['category'] = category
        if tags:
            data['tags'] = tags
        if ratio_limit >= 0:
            data['ratioLimit'] = str(ratio_limit)
        if seed_time >= 0:
            data['seedingTimeLimit'] = str(seed_time)

        result = self._api_call('POST', 'torrents/add', data)
        if result and 'error' not in result:
            return {"status": "ok", "magnet": magnet[:80] + "..."}
        return {"status": "error", "error": str(result), "magnet": magnet[:80] + "..."}

    def get_torrents(self, filter: str = "all", category: str = "",
                     tags: str = "", sort: str = "") -> List[dict]:
        """Get list of torrents."""
        data = {'filter': filter}
        if category:
            data['category'] = category
        if tags:
            data['tags'] = tags
        if sort:
            data['sort'] = sort
        return self._api_call('GET', 'torrents/info', data) or []

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


def _qb_add_simple(magnet: str, qb_url: str, category: str = '', tags: str = ''):
    """Simple qBittorrent add for direct download mode."""
    from urllib.request import Request, urlopen
    from urllib.parse import urlencode
    try:
        data = urlencode({'urls': magnet})
        if category:
            data += '&' + urlencode({'category': category})
        if tags:
            data += '&' + urlencode({'tags': tags})
        req = Request(f'{qb_url.rstrip("/")}/api/v2/torrents/add',
                     data=data.encode(),
                     headers={'User-Agent': 'sator/0.1'})
        urlopen(req, timeout=10)
    except Exception:
        pass

