import json
import subprocess
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "skill" / "media-downloader" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from media_downloader.backends import DouyinBackend, YtDlpBackend, build_default_dispatcher
from media_downloader.models import DownloadRequest, MediaKind
from media_downloader.platforms import Platform


class YtDlpBackendTests(unittest.TestCase):
    def test_resolve_uses_safe_argument_list_and_maps_metadata(self):
        calls = []
        payload = {
            "title": "Example",
            "uploader": "Artist",
            "id": "abc",
            "duration": 12.5,
            "width": 1280,
            "height": 720,
            "ext": "mp4",
        }

        def runner(command, **kwargs):
            calls.append(command)
            return subprocess.CompletedProcess(command, 0, stdout=json.dumps(payload), stderr="")

        backend = YtDlpBackend(command=["yt-dlp"], runner=runner)
        request = DownloadRequest(
            "https://example.com/video",
            media=MediaKind.VIDEO,
            proxy="http://proxy.example:8080",
            cookies_from_browser="safari",
        )
        result = backend.resolve(request)
        self.assertEqual("Example", result.title)
        self.assertEqual("Artist", result.artist)
        self.assertEqual("yt-dlp", result.backend)
        self.assertIn("--proxy", calls[0])
        self.assertIn("--cookies-from-browser", calls[0])
        self.assertEqual("--", calls[0][-2])
        self.assertEqual(request.url, calls[0][-1])


class DefaultRoutingTests(unittest.TestCase):
    def test_first_class_platform_routes_are_explicit(self):
        dispatcher = build_default_dispatcher()
        expected = {
            Platform.TIKTOK: ["yt-dlp", "tikwm", "cobalt"],
            Platform.DOUYIN: ["yt-dlp", "douyin", "douyin-api"],
            Platform.TWITTER: ["yt-dlp", "fxtwitter", "cobalt"],
            Platform.BILIBILI: ["yt-dlp", "cobalt"],
            Platform.SUNO: ["suno"],
            Platform.UDIO: ["udio"],
        }
        for platform, names in expected.items():
            with self.subTest(platform=platform):
                self.assertEqual(names, [backend.name for backend in dispatcher.routes[platform]])


class DouyinBackendTests(unittest.TestCase):
    def test_full_video_url_is_resolved_through_official_mobile_share_page(self):
        calls = []

        class FakeNetwork:
            def fetch_text(self, url, **kwargs):
                calls.append((url, kwargs))
                return (Path(__file__).parent / "fixtures" / "douyin.html").read_text(encoding="utf-8")

        source_url = "https://www.douyin.com/video/7604129988555574538"
        result = DouyinBackend(FakeNetwork()).resolve(DownloadRequest(source_url))

        self.assertEqual(
            "https://www.iesdouyin.com/share/video/7604129988555574538",
            calls[0][0],
        )
        self.assertEqual(source_url, result.source_url)
        self.assertEqual("douyin", result.backend)


if __name__ == "__main__":
    unittest.main()
