import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skill" / "media-downloader" / "scripts"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(SCRIPTS))

from media_downloader.models import MediaKind
from media_downloader.parsers import (
    parse_cobalt_response,
    parse_douyin_page,
    parse_fxtwitter_response,
    parse_suno_page,
    parse_tikwm_response,
    parse_udio_page,
)


def fixture_text(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def fixture_json(name):
    return json.loads(fixture_text(name))


class ParserTests(unittest.TestCase):
    def test_parses_suno_public_page(self):
        result = parse_suno_page(fixture_text("suno.html"))
        self.assertEqual("Midnight Test", result.title)
        self.assertEqual("Test Artist", result.artist)
        self.assertEqual("11111111-2222-3333-4444-555555555555", result.source_id)
        self.assertEqual("https://cdn1.suno.ai/11111111-2222-3333-4444-555555555555.mp3", result.audio_url)
        self.assertEqual(
            "https://cdn2.suno.ai/image_large_11111111-2222-3333-4444-555555555555.jpeg", result.cover_url
        )

    def test_parses_udio_public_page(self):
        result = parse_udio_page(fixture_text("udio.html"))
        self.assertEqual("Chasing Tests", result.title)
        self.assertEqual("Udio Artist", result.artist)
        self.assertEqual("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", result.source_id)
        self.assertEqual("https://storage.googleapis.com/example/song.mp3", result.audio_url)
        self.assertEqual("[Verse]\nTesting", result.lyrics)

    def test_tikwm_prefers_hd_video_and_can_select_audio(self):
        data = fixture_json("tikwm.json")
        video = parse_tikwm_response(data, MediaKind.VIDEO)
        audio = parse_tikwm_response(data, MediaKind.AUDIO)
        self.assertEqual("https://www.tikwm.com/video/hdplay.mp4", video.assets[0].url)
        self.assertEqual("https://cdn.example.test/music.mp3", audio.assets[0].url)
        self.assertEqual("Tester", video.artist)

    def test_parses_douyin_router_data(self):
        result = parse_douyin_page(fixture_text("douyin.html"))
        self.assertEqual("Douyin test", result.title)
        self.assertEqual("Douyin Artist", result.artist)
        self.assertIn("video_id=v0200testvideoid", result.assets[0].url)
        self.assertEqual(1080, result.width)
        self.assertEqual(1920, result.height)

    def test_fxtwitter_chooses_highest_bitrate_article_video(self):
        result = parse_fxtwitter_response(fixture_json("fxtwitter.json"))
        self.assertEqual("Article test", result.title)
        self.assertEqual("https://video.example.test/high.mp4", result.assets[0].url)

    def test_cobalt_normalizes_picker_items(self):
        result = parse_cobalt_response(fixture_json("cobalt.json"))
        self.assertEqual(2, len(result.assets))
        self.assertEqual(MediaKind.VIDEO, result.assets[0].kind)
        self.assertEqual(MediaKind.IMAGE, result.assets[1].kind)


if __name__ == "__main__":
    unittest.main()
