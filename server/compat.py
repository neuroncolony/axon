"""compat: stdlib-only stand-in for core.http_client.

Railway has no `core` package, so chain.py and pool.py fall back to this
module when the real one is missing. Uses urllib only. Non-2xx responses
do not raise; the response object just carries the status.
"""
import urllib.error
import urllib.parse
import urllib.request


class Response:
    """Minimal response object: .status_code, .text, .json(), .ok, .headers."""

    def __init__(self, status_code, text, headers):
        self.status_code = status_code
        self.text = text
        self.headers = headers
        self._json = None

    @property
    def ok(self):
        return 200 <= self.status_code < 300

    def json(self):
        if self._json is None:
            import json as _json
            self._json = _json.loads(self.text)
        return self._json


def _send(req, timeout):
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            return Response(resp.status, raw.decode('utf-8', 'replace'), dict(resp.headers.items()))
    except urllib.error.HTTPError as e:
        raw = e.read()
        return Response(e.code, raw.decode('utf-8', 'replace'), dict(e.headers.items()) if e.headers else {})
    except Exception as e:  # network error: keep the object shape, mark as failed
        return Response(0, str(e), {})


def _build_url(url, params):
    if not params:
        return url
    qs = urllib.parse.urlencode(params)
    sep = '&' if urllib.parse.urlparse(url).query else '?'
    return url + sep + qs


def proxied_get(url, headers=None, timeout=15, params=None):
    req = urllib.request.Request(_build_url(url, params), method='GET')
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    return _send(req, timeout)


def proxied_post(url, json=None, data=None, headers=None, timeout=15):
    if json is not None:
        import json as _json
        body = _json.dumps(json).encode('utf-8')
        req = urllib.request.Request(url, data=body, method='POST')
        req.add_header('Content-Type', 'application/json')
    else:
        body = data if isinstance(data, bytes) else (data.encode('utf-8') if isinstance(data, str) else (data or b''))
        req = urllib.request.Request(url, data=body, method='POST')
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    return _send(req, timeout)
