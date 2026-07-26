import csv
from typing import List, Dict

import requests
from bs4 import BeautifulSoup

URL = "https://quotes.toscrape.com/"


def fetch_html(url: str = URL) -> str:
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return response.text


def parse_quotes(html: str) -> List[Dict[str, object]]:
    soup = BeautifulSoup(html, "html.parser")
    quotes: List[Dict[str, object]] = []

    for quote_div in soup.select(".quote"):
        text = quote_div.select_one(".text")
        author = quote_div.select_one(".author")
        tags = quote_div.select(".tag")

        if text and author:
            quotes.append(
                {
                    "text": text.get_text(strip=True),
                    "author": author.get_text(strip=True),
                    "tags": [tag.get_text(strip=True) for tag in tags],
                }
            )

    return quotes


def save_quotes(quotes: List[Dict[str, object]], path: str = "quotes.csv") -> str:
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["text", "author", "tags"])
        writer.writeheader()
        for quote in quotes:
            writer.writerow(
                {
                    "text": quote["text"],
                    "author": quote["author"],
                    "tags": "; ".join(quote["tags"]),
                }
            )

    return path


def main() -> None:
    html = fetch_html()
    quotes = parse_quotes(html)

    print(f"Found {len(quotes)} quotes")
    for quote in quotes[:5]:
        print(f"- {quote['author']}: {quote['text']}")

    output_file = save_quotes(quotes)
    print(f"Saved quotes to {output_file}")


if __name__ == "__main__":
    main()
