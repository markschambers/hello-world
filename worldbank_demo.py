import csv
from typing import Any, Dict, List

import requests

COUNTRY_URL = "https://api.worldbank.org/v2/country?format=json&per_page=400"
INDICATOR_URL = (
    "https://api.worldbank.org/v2/country/all/indicator/NY.GDP.MKTP.CD"
    "?format=json&per_page=20000&date=2015:2024"
)


def fetch_json(url: str) -> Any:
    response = requests.get(url, timeout=20)
    response.raise_for_status()
    return response.json()


def fetch_real_countries(url: str = COUNTRY_URL) -> Dict[str, str]:
    """Map ISO3 code -> country name, excluding region/income-group aggregates.

    The World Bank API mixes actual countries with aggregates (e.g. "World",
    "Euro area", "Africa Eastern and Southern") in the same list. Aggregates
    are identified by having no real region (region.id == "NA").
    """
    payload = fetch_json(url)
    if not payload or len(payload) < 2:
        return {}

    countries: Dict[str, str] = {}
    for item in payload[1]:
        if item.get("region", {}).get("id") == "NA":
            continue
        iso3 = item.get("id")
        name = item.get("name")
        if iso3 and name:
            countries[iso3] = name
    return countries


def normalize_records(payload: List[Any], valid_countries: Dict[str, str]) -> List[Dict[str, Any]]:
    if not payload or len(payload) < 2:
        return []

    rows: List[Dict[str, Any]] = []
    for item in payload[1]:
        if not isinstance(item, dict):
            continue

        iso3 = item.get("countryiso3code")
        if iso3 not in valid_countries:
            continue

        year = item.get("date")
        indicator = item.get("indicator", {}).get("value")
        value = item.get("value")

        if year and indicator is not None and value is not None:
            rows.append(
                {
                    "country": valid_countries[iso3],
                    "iso3_code": iso3,
                    "year": int(year),
                    "indicator": indicator,
                    "value": value,
                }
            )

    return rows


def fetch_worldbank_data(url: str = INDICATOR_URL) -> List[Dict[str, Any]]:
    valid_countries = fetch_real_countries()
    payload = fetch_json(url)
    rows = normalize_records(payload, valid_countries)
    rows.sort(key=lambda row: (row["year"], row["value"]), reverse=True)
    return rows


def save_rows(rows: List[Dict[str, Any]], path: str = "worldbank_gdp.csv") -> str:
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["country", "iso3_code", "year", "indicator", "value"]
        )
        writer.writeheader()
        writer.writerows(rows)
    return path


def main() -> None:
    rows = fetch_worldbank_data()
    print(f"Fetched {len(rows)} rows for real countries (aggregates excluded)")
    for row in rows[:10]:
        print(row)

    output_file = save_rows(rows)
    print(f"Saved data to {output_file}")


if __name__ == "__main__":
    main()
