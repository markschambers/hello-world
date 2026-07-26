import csv
import json
from typing import Any, List, Dict

import requests

BASE_URL = "https://api.worldbank.org/v2/country/all/indicator/NY.GDP.MKTP.CD?format=json&per_page=50"


def fetch_worldbank_data(url: str = BASE_URL) -> List[Dict[str, Any]]:
    response = requests.get(url, timeout=20)
    response.raise_for_status()
    payload = response.json()
    return normalize_records(payload)


def normalize_records(payload: List[Any]) -> List[Dict[str, Any]]:
    if not payload or len(payload) < 2:
        return []

    records = payload[1]
    rows: List[Dict[str, Any]] = []

    for item in records:
        if not isinstance(item, dict):
            continue

        country = item.get("country", {}).get("value")
        year = item.get("date")
        indicator = item.get("indicator", {}).get("value")
        value = item.get("value")

        if country and year and indicator is not None:
            rows.append(
                {
                    "country": country,
                    "year": int(year),
                    "indicator": indicator,
                    "value": value,
                }
            )

    return rows


def save_rows(rows: List[Dict[str, Any]], path: str = "worldbank_gdp.csv") -> str:
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["country", "year", "indicator", "value"])
        writer.writeheader()
        writer.writerows(rows)
    return path


def main() -> None:
    rows = fetch_worldbank_data()
    print(f"Fetched {len(rows)} rows")
    for row in rows[:10]:
        print(row)

    output_file = save_rows(rows)
    print(f"Saved data to {output_file}")


if __name__ == "__main__":
    main()
