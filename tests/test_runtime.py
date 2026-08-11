import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "skill" / "media-downloader" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from media_downloader.dispatcher import Dispatcher
from media_downloader.models import DownloadRequest, MediaAsset, MediaKind, MediaProbe, Resolution
from media_downloader.network import DownloadValidationError, NetworkClient, PublicRedirectHandler
from media_downloader.platforms import Platform
from media_downloader.security import UnsafeURLError
from media_downloader.service import DownloaderService
from media_downloader.verification import ProbeError, probe_media


class FakeHeaders(dict):
    def get_content_type(self):
        return self.get("Content-Type", "application/octet-stream").split(";", 1)[0]


class FakeResponse:
    def __init__(self, body, url="https://cdn.example.com/file.mp4", content_type="video/mp4"):
        self.body = body
        self.offset = 0
        self.url = url
        self.headers = FakeHeaders({"Content-Type": content_type, "Content-Length": str(len(body))})

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size=-1):
        if self.offset >= len(self.body):
            return b""
        if size < 0:
            size = len(self.body) - self.offset
        chunk = self.body[self.offset : self.offset + size]
        self.offset += len(chunk)
        return chunk

    def geturl(self):
        return self.url


class NetworkClientTests(unittest.TestCase):
    def test_redirect_handler_rejects_private_target_before_following(self):
        handler = PublicRedirectHandler(resolve_dns=False)

        with self.assertRaises(UnsafeURLError):
            handler.redirect_request(
                None,
                None,
                302,
                "Found",
                {},
                "http://127.0.0.1/private",
            )

    def test_download_uses_part_file_then_atomically_renames(self):
        response = FakeResponse(b"0" * 16384)
        client = NetworkClient(opener=lambda request, timeout: response, resolve_dns=False)
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "video.mp4"
            result = client.download("https://cdn.example.com/video.mp4", destination, max_bytes=20000)
            self.assertEqual(destination, result)
            self.assertEqual(16384, destination.stat().st_size)
            self.assertFalse((Path(str(destination) + ".part")).exists())

    def test_download_rejects_html_error_body_and_removes_part(self):
        response = FakeResponse(b"<html>blocked</html>", content_type="text/html")
        client = NetworkClient(opener=lambda request, timeout: response, resolve_dns=False)
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "video.mp4"
            with self.assertRaises(DownloadValidationError):
                client.download("https://cdn.example.com/video.mp4", destination)
            self.assertFalse(destination.exists())
            self.assertFalse((Path(str(destination) + ".part")).exists())


class VerificationTests(unittest.TestCase):
    def test_parses_ffprobe_video_and_audio_streams(self):
        payload = {
            "format": {"format_name": "mov,mp4", "duration": "12.5", "size": "4096"},
            "streams": [
                {"codec_type": "video", "codec_name": "h264", "width": 1080, "height": 1920},
                {"codec_type": "audio", "codec_name": "aac", "sample_rate": "44100", "channels": 2},
            ],
        }

        def runner(*args, **kwargs):
            return subprocess.CompletedProcess(args[0], 0, stdout=json.dumps(payload), stderr="")

        with tempfile.NamedTemporaryFile(suffix=".mp4") as media:
            media.write(b"data")
            media.flush()
            result = probe_media(Path(media.name), runner=runner)
        self.assertEqual("h264", result.video_codec)
        self.assertEqual(1080, result.width)
        self.assertEqual("aac", result.audio_codec)
        self.assertEqual(44100, result.sample_rate)

    def test_rejects_file_without_audio_or_video_stream(self):
        payload = {"format": {"format_name": "data", "duration": "0"}, "streams": []}

        def runner(*args, **kwargs):
            return subprocess.CompletedProcess(args[0], 0, stdout=json.dumps(payload), stderr="")

        with tempfile.NamedTemporaryFile() as media:
            media.write(b"data")
            media.flush()
            with self.assertRaises(ProbeError):
                probe_media(Path(media.name), runner=runner)


class StubBackend:
    def __init__(self, name, resolution):
        self.name = name
        self.resolution = resolution

    def resolve(self, request):
        return self.resolution


class StubNetwork:
    def __init__(self):
        self.calls = []

    def download(self, url, destination, **kwargs):
        self.calls.append(url)
        if "broken" in url:
            raise DownloadValidationError("broken media")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"valid media")
        return destination


class ServiceFallbackTests(unittest.TestCase):
    def test_download_failure_moves_to_next_backend(self):
        first = StubBackend(
            "first",
            Resolution("bad", "first", [MediaAsset("https://cdn.example.com/broken.mp4", MediaKind.VIDEO)]),
        )
        second = StubBackend(
            "second",
            Resolution(
                "good", "second", [MediaAsset("https://cdn.example.com/working.mp4", MediaKind.VIDEO)]
            ),
        )
        dispatcher = Dispatcher({Platform.TIKTOK: [first, second]})

        def probe(path):
            return MediaProbe(str(path), path.stat().st_size, "mp4", 1.0, video_codec="h264")

        network = StubNetwork()
        service = DownloaderService(dispatcher, network=network, prober=probe)
        with tempfile.TemporaryDirectory() as tmp:
            request = DownloadRequest(
                "https://www.tiktok.com/@a/video/1",
                media=MediaKind.VIDEO,
                output_dir=Path(tmp),
            )
            report = service.download(request)
        self.assertEqual("second", report.backend)
        self.assertEqual(2, len(network.calls))
        self.assertIn("first: broken media", report.failures)


if __name__ == "__main__":
    unittest.main()
