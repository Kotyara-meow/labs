"""Unit-тесты проверки MAC-адресов и обработки источников данных."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests

from main import find_mac_addresses, is_valid_mac, read_text_file, read_web_page


class TestMacValidation(unittest.TestCase):
    def test_supported_formats(self) -> None:
        samples = (
            "00:1A:2B:3C:4D:5E",
            "00-1A-2B-3C-4D-5E",
            "001A.2B3C.4D5E",
            "aa:bb:cc:dd:ee:ff",
            "aBcD.1234.ef56",
        )
        for address in samples:
            with self.subTest(address=address):
                self.assertTrue(is_valid_mac(address))

    def test_invalid_addresses(self) -> None:
        samples = (
            "", "00:1A:2B:3C:4D", "00:1A:2B:3C:4D:5E:6F",
            "00:1A:2B:3C:4D:5G", "GG:1A:2B:3C:4D:5E",
            "00-1A:2B-3C:4D-5E", "001A.2B3C.4D5", "001A-2B3C-4D5E",
            " 00:1A:2B:3C:4D:5E", "00:1A:2B:3C:4D:5E ",
            "00:1A:2B:3C:4D:5E\n", "00::1A:2B:3C:4D:5E",
        )
        for address in samples:
            with self.subTest(address=address):
                self.assertFalse(is_valid_mac(address))

    def test_non_string_input_returns_false(self) -> None:
        self.assertFalse(is_valid_mac(None))  # type: ignore[arg-type]


class TestMacSearch(unittest.TestCase):
    def test_finds_all_supported_formats(self) -> None:
        text = "00:1A:2B:3C:4D:5E; AA-BB-CC-DD-EE-FF; 001A.2B3C.4D5E"
        self.assertEqual(find_mac_addresses(text), [
            "00:1A:2B:3C:4D:5E", "AA-BB-CC-DD-EE-FF", "001A.2B3C.4D5E"
        ])

    def test_duplicate_addresses_are_removed_case_insensitively(self) -> None:
        text = "AA:BB:CC:DD:EE:FF and aa:bb:cc:dd:ee:ff"
        self.assertEqual(find_mac_addresses(text), ["AA:BB:CC:DD:EE:FF"])

    def test_no_matches_and_empty_text(self) -> None:
        self.assertEqual(find_mac_addresses("Здесь нет адресов"), [])
        self.assertEqual(find_mac_addresses(""), [])

    def test_does_not_match_inside_longer_address_like_text(self) -> None:
        samples = (
            "A000:1A:2B:3C:4D:5E9",
            "00:1A:2B:3C:4D:5E:AA",
            "001A.2B3C.4D5E.extra",
        )
        for text in samples:
            with self.subTest(text=text):
                self.assertEqual(find_mac_addresses(text), [])


class TestFileReading(unittest.TestCase):
    def test_reads_utf8_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.txt"
            path.write_text("Устройство: 00:1A:2B:3C:4D:5E", encoding="utf-8")
            self.assertIn("00:1A:2B:3C:4D:5E", read_text_file(path))

    def test_missing_file_raises_clear_error(self) -> None:
        with self.assertRaisesRegex(FileNotFoundError, "Файл не найден"):
            read_text_file("this_file_should_not_exist_12345.txt")

    def test_invalid_utf8_raises_unicode_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.txt"
            path.write_bytes(b"\xff\xfe\xfa")
            with self.assertRaises(UnicodeError):
                read_text_file(path)


class TestWebReading(unittest.TestCase):
    def test_rejects_invalid_urls(self) -> None:
        for url in ("example.com", "ftp://example.com", "https://", ""):
            with self.subTest(url=url), self.assertRaises(ValueError):
                read_web_page(url)

    @patch("main.requests.get")
    def test_reads_page_text_and_sets_timeout(self, mock_get: Mock) -> None:
        response = Mock()
        response.text = "MAC 00:1A:2B:3C:4D:5E"
        response.raise_for_status.return_value = None
        mock_get.return_value = response

        self.assertIn("00:1A:2B:3C:4D:5E", read_web_page("https://example.com"))
        mock_get.assert_called_once_with("https://example.com", timeout=10)

    @patch("main.requests.get", side_effect=requests.Timeout("timeout"))
    def test_network_error_is_wrapped(self, mock_get: Mock) -> None:
        with self.assertRaisesRegex(RuntimeError, "Не удалось загрузить страницу"):
            read_web_page("https://example.com")
        mock_get.assert_called_once()

    @patch("main.requests.get")
    def test_http_error_is_wrapped(self, mock_get: Mock) -> None:
        response = Mock()
        response.raise_for_status.side_effect = requests.HTTPError("404")
        mock_get.return_value = response
        with self.assertRaises(RuntimeError):
            read_web_page("https://example.com/missing")


if __name__ == "__main__":
    unittest.main(verbosity=2)
