import ipaddress
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "skill" / "media-downloader" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from media_downloader.platforms import Platform, detect_platform
from media_downloader.security import UnsafeURLError, validate_public_http_url


class PlatformDetectionTests(unittest.TestCase):
    def test_detects_first_class_platforms(self):
        cases = {
            "https://www.tiktok.com/@name/video/123": Platform.TIKTOK,
            "https://v.douyin.com/abc123/": Platform.DOUYIN,
            "https://x.com/name/status/123": Platform.TWITTER,
            "https://www.bilibili.com/video/BV1xx": Platform.BILIBILI,
            "https://suno.com/song/00000000-0000-0000-0000-000000000000": Platform.SUNO,
            "https://www.udio.com/songs/abc": Platform.UDIO,
            "https://www.youtube.com/watch?v=abc": Platform.YOUTUBE,
            "https://example.com/video": Platform.GENERIC,
        }
        for url, expected in cases.items():
            with self.subTest(url=url):
                self.assertEqual(expected, detect_platform(url))


class SafeUrlTests(unittest.TestCase):
    def test_accepts_public_https_url_without_dns_resolution(self):
        self.assertEqual(
            "https://cdn.example.com/video.mp4",
            validate_public_http_url("https://cdn.example.com/video.mp4", resolve_dns=False),
        )

    def test_rejects_local_and_non_http_urls(self):
        unsafe = [
            "file:///etc/passwd",
            "data:text/plain,hello",
            "http://localhost/video.mp4",
            "http://127.0.0.1/video.mp4",
            "http://[::1]/video.mp4",
            "http://10.0.0.1/video.mp4",
            "http://192.168.1.5/video.mp4",
        ]
        for url in unsafe:
            with self.subTest(url=url), self.assertRaises(UnsafeURLError):
                validate_public_http_url(url, resolve_dns=False)

    def test_rejects_hostname_when_dns_resolves_private(self):
        def private_resolver(host, port, type=0):
            return [(2, 1, 6, "", (str(ipaddress.ip_address("10.1.2.3")), port))]

        with self.assertRaises(UnsafeURLError):
            validate_public_http_url(
                "https://looks-public.example/file.mp4",
                resolve_dns=True,
                resolver=private_resolver,
            )

    def test_allows_rfc2544_synthetic_dns_used_by_local_proxies(self):
        def synthetic_resolver(host, port, type=0):
            return [(2, 1, 6, "", ("198.18.1.42", port))]

        self.assertEqual(
            "https://public.example/file.mp4",
            validate_public_http_url(
                "https://public.example/file.mp4",
                resolve_dns=True,
                resolver=synthetic_resolver,
            ),
        )

    def test_rejects_direct_rfc2544_ip_literal(self):
        with self.assertRaises(UnsafeURLError):
            validate_public_http_url("http://198.18.1.42/file.mp4", resolve_dns=False)


if __name__ == "__main__":
    unittest.main()
