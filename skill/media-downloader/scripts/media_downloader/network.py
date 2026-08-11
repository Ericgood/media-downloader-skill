import json
import os
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .security import UnsafeURLError, validate_public_http_url

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36 "
    "MediaDownloader/0.1"
)


class NetworkError(RuntimeError):
    pass


class DownloadValidationError(NetworkError):
    pass


class PublicRedirectHandler(HTTPRedirectHandler):
    """Reject unsafe redirect targets before urllib opens the next connection."""

    def __init__(self, *, resolve_dns: bool = True):
        super().__init__()
        self.resolve_dns = resolve_dns

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_public_http_url(newurl, resolve_dns=self.resolve_dns)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class NetworkClient:
    def __init__(
        self,
        *,
        opener=None,
        timeout: int = 30,
        resolve_dns: bool = True,
        user_agent: str = DEFAULT_USER_AGENT,
    ):
        self.opener = opener or build_opener(PublicRedirectHandler(resolve_dns=resolve_dns)).open
        self.timeout = timeout
        self.resolve_dns = resolve_dns
        self.user_agent = user_agent

    def _request(self, url: str, *, headers: Optional[Dict[str, str]] = None, data: bytes = None):
        safe_url = validate_public_http_url(url, resolve_dns=self.resolve_dns)
        request_headers = {
            "User-Agent": self.user_agent,
            "Accept-Encoding": "identity",
            "Accept-Language": "en-US,en;q=0.8,zh-CN;q=0.6",
        }
        if headers:
            request_headers.update(headers)
        return Request(safe_url, headers=request_headers, data=data)

    def fetch_text(
        self, url: str, *, headers: Optional[Dict[str, str]] = None, max_bytes: int = 8 * 1024 * 1024
    ) -> str:
        request = self._request(url, headers=headers)
        try:
            with self.opener(request, timeout=self.timeout) as response:
                validate_public_http_url(response.geturl(), resolve_dns=self.resolve_dns)
                body = response.read(max_bytes + 1)
                if len(body) > max_bytes:
                    raise NetworkError("response exceeded the configured size limit")
                charset = "utf-8"
                get_charset = getattr(response.headers, "get_content_charset", None)
                if get_charset:
                    charset = get_charset() or charset
                return body.decode(charset, errors="replace")
        except (OSError, UnsafeURLError) as exc:
            raise NetworkError(str(exc)) from exc

    def fetch_json(
        self, url: str, *, headers: Optional[Dict[str, str]] = None, max_bytes: int = 8 * 1024 * 1024
    ) -> Dict[str, Any]:
        try:
            return json.loads(self.fetch_text(url, headers=headers, max_bytes=max_bytes))
        except json.JSONDecodeError as exc:
            raise NetworkError("remote service returned invalid JSON") from exc

    def post_json(
        self,
        url: str,
        payload: Dict[str, Any],
        *,
        headers: Optional[Dict[str, str]] = None,
        max_bytes: int = 8 * 1024 * 1024,
    ) -> Dict[str, Any]:
        request_headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if headers:
            request_headers.update(headers)
        request = self._request(
            url,
            headers=request_headers,
            data=json.dumps(payload).encode("utf-8"),
        )
        try:
            with self.opener(request, timeout=self.timeout) as response:
                validate_public_http_url(response.geturl(), resolve_dns=self.resolve_dns)
                body = response.read(max_bytes + 1)
                if len(body) > max_bytes:
                    raise NetworkError("response exceeded the configured size limit")
                return json.loads(body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise NetworkError("remote service returned invalid JSON") from exc
        except (OSError, UnsafeURLError) as exc:
            raise NetworkError(str(exc)) from exc

    def download(
        self,
        url: str,
        destination: Path,
        *,
        headers: Optional[Dict[str, str]] = None,
        max_bytes: int = 2 * 1024 * 1024 * 1024,
    ) -> Path:
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(destination.name + ".part")
        request = self._request(url, headers=headers)
        try:
            with self.opener(request, timeout=self.timeout) as response:
                validate_public_http_url(response.geturl(), resolve_dns=self.resolve_dns)
                content_type = self._content_type(response.headers)
                if content_type.startswith("text/") or content_type in (
                    "application/json",
                    "application/problem+json",
                    "application/xml",
                ):
                    raise DownloadValidationError(
                        "remote server returned {} instead of media".format(content_type)
                    )
                declared = response.headers.get("Content-Length")
                if declared and int(declared) > max_bytes:
                    raise DownloadValidationError("remote file exceeds the configured size limit")
                total = 0
                with temporary.open("wb") as handle:
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        total += len(chunk)
                        if total > max_bytes:
                            raise DownloadValidationError("download exceeded the configured size limit")
                        handle.write(chunk)
                    handle.flush()
                    os.fsync(handle.fileno())
                if total == 0:
                    raise DownloadValidationError("remote server returned an empty file")
                os.replace(str(temporary), str(destination))
                return destination
        except DownloadValidationError:
            temporary.unlink(missing_ok=True)
            destination.unlink(missing_ok=True)
            raise
        except (OSError, UnsafeURLError, ValueError) as exc:
            temporary.unlink(missing_ok=True)
            destination.unlink(missing_ok=True)
            raise NetworkError(str(exc)) from exc

    @staticmethod
    def _content_type(headers) -> str:
        get_content_type = getattr(headers, "get_content_type", None)
        if get_content_type:
            return (get_content_type() or "").lower()
        return (headers.get("Content-Type", "") or "").split(";", 1)[0].lower()
