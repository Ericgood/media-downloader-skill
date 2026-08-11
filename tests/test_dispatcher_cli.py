import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "skill" / "media-downloader" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from media_downloader.app import _redact_url
from media_downloader.cli import build_parser, request_from_args
from media_downloader.dispatcher import BackendFailure, Dispatcher
from media_downloader.models import DownloadRequest, MediaAsset, MediaKind, Resolution
from media_downloader.platforms import Platform


class StubBackend:
    def __init__(self, name, outcome):
        self.name = name
        self.outcome = outcome
        self.calls = 0

    def resolve(self, request):
        self.calls += 1
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


class DispatcherTests(unittest.TestCase):
    def test_falls_through_and_preserves_failure_evidence(self):
        first = StubBackend("yt-dlp", BackendFailure("extractor changed"))
        second = StubBackend(
            "tikwm",
            Resolution(
                title="working",
                backend="tikwm",
                assets=[MediaAsset("https://cdn.example.com/video.mp4", MediaKind.VIDEO)],
            ),
        )
        dispatcher = Dispatcher({Platform.TIKTOK: [first, second]})
        result = dispatcher.resolve(DownloadRequest("https://www.tiktok.com/@a/video/1"))
        self.assertEqual("tikwm", result.backend)
        self.assertEqual(["yt-dlp: extractor changed"], result.failures)
        self.assertEqual(1, first.calls)
        self.assertEqual(1, second.calls)

    def test_reports_all_backend_failures(self):
        dispatcher = Dispatcher(
            {
                Platform.TIKTOK: [
                    StubBackend("one", BackendFailure("first")),
                    StubBackend("two", BackendFailure("second")),
                ]
            }
        )
        with self.assertRaises(BackendFailure) as raised:
            dispatcher.resolve(DownloadRequest("https://www.tiktok.com/@a/video/1"))
        self.assertIn("one: first", str(raised.exception))
        self.assertIn("two: second", str(raised.exception))


class CliCompatibilityTests(unittest.TestCase):
    def test_signed_query_values_are_redacted_from_output(self):
        redacted = _redact_url("https://cdn.example.com/video.mp4?id=public&X-Signature=secret&token=hidden")

        self.assertIn("id=public", redacted)
        self.assertNotIn("secret", redacted)
        self.assertNotIn("hidden", redacted)

    def test_legacy_audio_only_maps_to_audio_media(self):
        parser = build_parser()
        args = parser.parse_args(["download", "https://example.com/v", "--audio-only"])
        request = request_from_args(args)
        self.assertEqual(MediaKind.AUDIO, request.media)

    def test_new_media_option_and_resolution_are_preserved(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "download",
                "https://example.com/v",
                "--media",
                "video",
                "--resolution",
                "720",
            ]
        )
        request = request_from_args(args)
        self.assertEqual(MediaKind.VIDEO, request.media)
        self.assertEqual("720", request.resolution)

    def test_multiple_urls_are_preserved_for_batch_download(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "download",
                "https://example.com/one",
                "https://example.com/two",
            ]
        )

        self.assertEqual(
            ["https://example.com/one", "https://example.com/two"],
            args.urls,
        )
        self.assertEqual("https://example.com/two", request_from_args(args, args.urls[1]).url)


if __name__ == "__main__":
    unittest.main()
