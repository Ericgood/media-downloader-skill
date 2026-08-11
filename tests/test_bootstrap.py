import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "skill" / "media-downloader" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from bootstrap import asset_name, expected_checksum


class BootstrapTests(unittest.TestCase):
    def test_selects_supported_standalone_assets(self):
        self.assertEqual("yt-dlp_macos", asset_name("darwin", "arm64"))
        self.assertEqual("yt-dlp_linux", asset_name("linux", "x86_64"))
        self.assertEqual("yt-dlp_linux_aarch64", asset_name("linux", "aarch64"))
        self.assertEqual("yt-dlp.exe", asset_name("win32", "amd64"))

    def test_reads_exact_asset_checksum(self):
        sums = "a" * 64 + "  yt-dlp\n" + "b" * 64 + "  yt-dlp_macos\n"
        self.assertEqual("b" * 64, expected_checksum(sums, "yt-dlp_macos"))


if __name__ == "__main__":
    unittest.main()
