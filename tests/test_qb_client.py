"""qBittorrent API authentication and query construction."""

import urllib.parse
import urllib.error

from sator.qb_client import QBClient, QBConfig


class FakeResponse:
    def __init__(self, body, headers=None):
        self.body = body
        self.headers = headers or {}

    def read(self):
        return self.body.encode()


def test_authenticated_get_logs_in_once_and_sends_query(monkeypatch):
    requests = []

    def fake_urlopen(request, timeout):
        requests.append(request)
        if request.full_url.endswith('/auth/login'):
            return FakeResponse('Ok.', {'Set-Cookie': 'SID=abc; Path=/; HttpOnly'})
        return FakeResponse('[]')

    monkeypatch.setattr('sator.qb_client.urllib.request.urlopen', fake_urlopen)
    client = QBClient(QBConfig(username='alice', password='secret'))
    assert client.get_torrents(filter='completed') == []
    assert len(requests) == 2
    assert requests[0].full_url.endswith('/auth/login')
    assert requests[1].get_header('Cookie') == 'SID=abc'
    assert urllib.parse.parse_qs(urllib.parse.urlsplit(requests[1].full_url).query) == {
        'filter': ['completed']}


def test_expired_qb_cookie_reauthenticates_once(monkeypatch):
    endpoints = []

    def fake_urlopen(request, timeout):
        endpoints.append(request.full_url)
        if request.full_url.endswith('/auth/login'):
            return FakeResponse('Ok.', {'Set-Cookie': 'SID=new; Path=/'})
        if len(endpoints) == 1:
            raise urllib.error.HTTPError(request.full_url, 403, 'Forbidden', {}, None)
        return FakeResponse('[]')

    monkeypatch.setattr('sator.qb_client.urllib.request.urlopen', fake_urlopen)
    client = QBClient(QBConfig(username='alice', password='secret'))
    client._cookie = 'SID=expired'
    assert client.get_torrents() == []
    assert len(endpoints) == 3
    assert endpoints[1].endswith('/auth/login')


def test_failed_qb_login_stops_before_add(monkeypatch):
    requests = []

    def fake_urlopen(request, timeout):
        requests.append(request)
        return FakeResponse('Fails.')

    monkeypatch.setattr('sator.qb_client.urllib.request.urlopen', fake_urlopen)
    client = QBClient(QBConfig(username='alice', password='wrong'))
    assert client.add_torrent('magnet:?xt=urn:btih:' + 'a' * 40)['status'] == 'error'
    assert len(requests) == 1
