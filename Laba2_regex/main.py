"""Лабораторная работа № 2: регулярные выражения и unit-тестирование.

Тема: проверка и поиск синтаксически корректных MAC-адресов (вариант 18).
"""

import argparse
import re
from pathlib import Path
from urllib.parse import urlparse

import requests

# Поддерживаемые форматы: AA:BB:CC:DD:EE:FF, AA-BB-CC-DD-EE-FF и AABB.CCDD.EEFF.
_HEX = r"[0-9A-Fa-f]"
_MAC_BODY = (
    r"(?:"
    rf"(?:{_HEX}{{2}}:){{5}}{_HEX}{{2}}"
    rf"|(?:{_HEX}{{2}}-){{5}}{_HEX}{{2}}"
    rf"|(?:{_HEX}{{4}}\.){{2}}{_HEX}{{4}}"
    r")"
)
MAC_FULL_PATTERN = re.compile(_MAC_BODY)
# Не допускаем извлечение части адреса из более длинной MAC-подобной записи.
MAC_SEARCH_PATTERN = re.compile(
    rf"(?<![0-9A-Fa-f:.-]){_MAC_BODY}(?![0-9A-Fa-f:.-])"
)


def is_valid_mac(value: str) -> bool:
    """Вернуть True, если вся строка — MAC-адрес одного из поддерживаемых форматов."""
    if not isinstance(value, str) or not value:
        return False
    return MAC_FULL_PATTERN.fullmatch(value) is not None


def find_mac_addresses(text: str) -> list[str]:
    """Найти уникальные MAC-адреса в тексте, сохранив порядок первого появления.

    Сравнение уникальности не зависит от регистра символов.
    """
    if not isinstance(text, str) or not text:
        return []

    found = MAC_SEARCH_PATTERN.findall(text)
    unique: list[str] = []
    seen: set[str] = set()
    for address in found:
        normalized = address.casefold()
        if normalized not in seen:
            seen.add(normalized)
            unique.append(address)
    return unique


def read_text_file(file_path: str | Path) -> str:
    """Прочитать UTF-8-файл; поднять понятную ошибку при проблеме с чтением."""
    path = Path(file_path)
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise FileNotFoundError(f"Файл не найден: {path}") from error
    except UnicodeError as error:
        raise UnicodeError(f"Файл не является корректным UTF-8: {path}") from error
    except OSError as error:
        raise OSError(f"Не удалось прочитать файл {path}: {error}") from error


def read_web_page(url: str) -> str:
    """Загрузить HTTP(S)-страницу и вернуть её текст.

    Raises:
        ValueError: URL не является полным HTTP(S)-адресом.
        RuntimeError: возникла ошибка запроса или HTTP-статуса.
    """
    if not isinstance(url, str):
        raise ValueError("URL должен быть строкой.")
    parsed_url = urlparse(url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise ValueError("Введите полный URL, начинающийся с http:// или https://.")

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except requests.RequestException as error:
        raise RuntimeError(f"Не удалось загрузить страницу: {error}") from error
    return response.text


def show_results(text: str) -> None:
    """Вывести уникальные найденные адреса или сообщение об отсутствии совпадений."""
    addresses = find_mac_addresses(text)
    if not addresses:
        print("MAC-адреса не найдены.")
        return

    print(f"Найдено уникальных MAC-адресов: {len(addresses)}")
    for number, address in enumerate(addresses, start=1):
        print(f"{number}. {address}")


def run_interactive() -> None:
    """Запустить консольное меню программы."""
    while True:
        print("\nПроверка и поиск MAC-адресов")
        print("1 — проверить один адрес")
        print("2 — найти адреса в файле")
        print("3 — найти адреса на веб-странице")
        print("4 — найти адреса во введённом тексте")
        print("0 — выход")
        choice = input("Выберите действие: ").strip()

        try:
            if choice == "1":
                address = input("Введите MAC-адрес: ")
                if is_valid_mac(address):
                    print("Адрес соответствует выбранному формату.")
                else:
                    print("Некорректный MAC-адрес.")
            elif choice == "2":
                show_results(read_text_file(input("Путь к текстовому файлу: ").strip()))
            elif choice == "3":
                show_results(read_web_page(input("Введите URL страницы: ").strip()))
            elif choice == "4":
                show_results(input("Введите текст для поиска: "))
            elif choice == "0":
                print("Работа завершена.")
                return
            else:
                print("Такого пункта нет. Выберите 0, 1, 2, 3 или 4.")
        except (ValueError, OSError, RuntimeError) as error:
            print(f"Ошибка: {error}")


def main() -> None:
    """Обработать аргументы командной строки и запустить выбранный режим."""
    parser = argparse.ArgumentParser(description="Проверка и поиск MAC-адресов.")
    parser.add_argument("--demo", action="store_true", help="поиск в демонстрационном файле")
    parser.add_argument("--file", default="sample.txt", help="путь к текстовому файлу")
    args = parser.parse_args()

    if not args.demo:
        run_interactive()
        return
    try:
        show_results(read_text_file(args.file))
    except (OSError, RuntimeError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
