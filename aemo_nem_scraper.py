import csv
import io
import os
import re
import zipfile
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple

import openpyxl
import requests

NEMWEB_SCADA_DIR = "https://nemweb.com.au/Reports/Current/Dispatch_SCADA/"
NEMWEB_ROOFTOP_DIR = "https://nemweb.com.au/Reports/Current/ROOFTOP_PV/ACTUAL/"
REGISTRATION_LIST_URL = (
    "https://www.aemo.com.au/-/media/files/electricity/nem/"
    "participant_information/nem-registration-and-exemption-list.xlsx"
)
REGISTRATION_CACHE_PATH = "nem_registration_list.xlsx"
REGISTRATION_CACHE_MAX_AGE = timedelta(days=7)
OUTPUT_CSV = "nem_generation_by_fuel.csv"

# AEMO's site returns 403 to requests without a browser-like User-Agent.
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

# The registration list's "Fuel Source - Descriptor" column has inconsistent
# casing/whitespace/typos (e.g. "Solar ", "solar", "Natrual Gas/ Diesel").
# Canonicalize the common ones; anything unrecognized falls back to a
# stripped version of the original value.
FUEL_SOURCE_CANONICAL = {
    "solar": "Solar",
    "wind": "Wind",
    "water": "Hydro",
    "black coal": "Black Coal",
    "brown coal": "Brown Coal",
    "natural gas": "Natural Gas",
    "natural gas / diesel": "Natural Gas / Diesel",
    "natrual gas/ diesel": "Natural Gas / Diesel",
    "natural gas / fuel oil": "Natural Gas / Fuel Oil",
    "diesel": "Diesel",
    "kerosene": "Kerosene",
    "coal seam methane": "Coal Seam Methane",
    "landfill methane / landfill gas": "Landfill Gas",
    "bagasse": "Bagasse",
    "bagasse and diesel": "Bagasse / Diesel",
    "biogas - sludge": "Biogas",
    "sewerage / waste water": "Sewerage / Waste Water",
    "waste coal mine gas": "Waste Coal Mine Gas",
    "ethane": "Ethane",
    "grid": "Battery Storage",
    "-": "Unknown",
}


def ensure_registration_list(path: str = REGISTRATION_CACHE_PATH) -> str:
    """Download the NEM Registration and Exemption List, caching it locally.

    This workbook maps each DUID to its region and fuel source. It only
    changes when generating units register, retire, or get reclassified,
    so it's refreshed weekly rather than on every scrape.
    """
    if os.path.exists(path):
        age = datetime.now() - datetime.fromtimestamp(os.path.getmtime(path))
        if age < REGISTRATION_CACHE_MAX_AGE:
            return path

    response = requests.get(REGISTRATION_LIST_URL, headers=BROWSER_HEADERS, timeout=60)
    response.raise_for_status()
    with open(path, "wb") as handle:
        handle.write(response.content)
    return path


def normalize_fuel_source(descriptor: Any) -> str:
    key = (descriptor or "").strip().lower()
    return FUEL_SOURCE_CANONICAL.get(key, (descriptor or "Unknown").strip())


def load_duid_map(path: str) -> Dict[str, Tuple[str, str, str]]:
    """Parse the registration workbook into DUID -> (region, fuel_source, dispatch_type).

    dispatch_type is "Load" for pump/charging units (e.g. pumped-hydro pumps,
    battery charge-side DUIDs) that draw power rather than generate it.
    """
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    sheet = workbook["PU and Scheduled Loads"]

    duid_map: Dict[str, Tuple[str, str, str]] = {}
    for row in sheet.iter_rows(min_row=2, values_only=True):
        region, fuel_descriptor, dispatch_type, duid = row[2], row[7], row[3], row[12]
        if not duid or not region:
            continue
        duid_map[duid] = (region, normalize_fuel_source(fuel_descriptor), dispatch_type or "")

    workbook.close()
    return duid_map


def find_latest_scada_report(directory_url: str = NEMWEB_SCADA_DIR) -> str:
    response = requests.get(directory_url, headers=BROWSER_HEADERS, timeout=20)
    response.raise_for_status()

    matches = re.findall(
        r'HREF="([^"]+PUBLIC_DISPATCHSCADA_\d+_\d+\.zip)"', response.text, re.IGNORECASE
    )
    if not matches:
        raise RuntimeError("No Dispatch_SCADA reports found in NEMWeb directory listing")

    latest = sorted(matches)[-1]
    return f"https://nemweb.com.au{latest}" if latest.startswith("/") else latest


def find_latest_rooftop_report(directory_url: str = NEMWEB_ROOFTOP_DIR) -> str:
    """Find the latest Rooftop PV Actual "measurement" report.

    NEMWeb publishes both MEASUREMENT (metered-sample based) and SATELLITE
    (independent satellite-derived estimate) reports for each 30-minute
    interval; MEASUREMENT is AEMO's primary rooftop PV figure.
    """
    response = requests.get(directory_url, headers=BROWSER_HEADERS, timeout=20)
    response.raise_for_status()

    matches = re.findall(
        r'HREF="([^"]+PUBLIC_ROOFTOP_PV_ACTUAL_MEASUREMENT_\d+_\d+\.zip)"',
        response.text,
        re.IGNORECASE,
    )
    if not matches:
        raise RuntimeError("No Rooftop PV measurement reports found in NEMWeb directory listing")

    latest = sorted(matches)[-1]
    return f"https://nemweb.com.au{latest}" if latest.startswith("/") else latest


def fetch_scada_snapshot(report_url: str) -> Tuple[str, List[Tuple[str, float]]]:
    """Download and parse a Dispatch_SCADA report into (settlement_date, [(duid, mw), ...])."""
    response = requests.get(report_url, headers=BROWSER_HEADERS, timeout=30)
    response.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        content = archive.read(archive.namelist()[0]).decode("utf-8")

    settlement_date = ""
    readings: List[Tuple[str, float]] = []
    for row in csv.reader(io.StringIO(content)):
        if not row or row[0] != "D":
            continue
        settlement_date = row[4]
        readings.append((row[5], float(row[6])))

    return settlement_date, readings


def fetch_rooftop_snapshot(report_url: str) -> Tuple[str, Dict[Tuple[str, str], float]]:
    """Download and parse a Rooftop PV Actual report.

    Unlike Dispatch_SCADA, this report is already aggregated by region, so
    no DUID join against the registration list is needed. Returns
    (settlement_date, {(region, "Rooftop Solar"): mw}).
    """
    response = requests.get(report_url, headers=BROWSER_HEADERS, timeout=30)
    response.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        content = archive.read(archive.namelist()[0]).decode("utf-8")

    settlement_date = ""
    totals: Dict[Tuple[str, str], float] = {}
    for row in csv.reader(io.StringIO(content)):
        if not row or row[0] != "D":
            continue
        settlement_date = row[4]
        totals[(row[5], "Rooftop Solar")] = float(row[6])

    return settlement_date, totals


def aggregate_by_region_and_fuel(
    readings: List[Tuple[str, float]], duid_map: Dict[str, Tuple[str, str, str]]
) -> Dict[Tuple[str, str], float]:
    totals: Dict[Tuple[str, str], float] = {}
    for duid, mw in readings:
        mapping = duid_map.get(duid)
        if mapping is None:
            continue  # not a registered generating unit (e.g. interconnector metering)
        region, fuel_source, dispatch_type = mapping
        if dispatch_type == "Load":
            mw = -mw  # pump/charging load draws power rather than generating it
        key = (region, fuel_source)
        totals[key] = totals.get(key, 0.0) + mw
    return totals


def save_snapshot(
    settlement_date: str, totals: Dict[Tuple[str, str], float], path: str = OUTPUT_CSV
) -> str:
    file_exists = os.path.exists(path)
    with open(path, "a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["settlement_date", "region", "fuel_source", "total_mw"]
        )
        if not file_exists:
            writer.writeheader()
        for (region, fuel_source), total_mw in sorted(totals.items()):
            writer.writerow(
                {
                    "settlement_date": settlement_date,
                    "region": region,
                    "fuel_source": fuel_source,
                    "total_mw": round(total_mw, 3),
                }
            )
    return path


def main() -> None:
    registration_path = ensure_registration_list()
    duid_map = load_duid_map(registration_path)
    print(f"Loaded {len(duid_map)} generating units from the registration list")

    report_url = find_latest_scada_report()
    settlement_date, readings = fetch_scada_snapshot(report_url)
    print(f"Fetched {len(readings)} SCADA readings for {settlement_date}")

    totals = aggregate_by_region_and_fuel(readings, duid_map)
    output_file = save_snapshot(settlement_date, totals)
    print(f"Appended {len(totals)} region/fuel rows to {output_file}")

    rooftop_report_url = find_latest_rooftop_report()
    rooftop_date, rooftop_totals = fetch_rooftop_snapshot(rooftop_report_url)
    save_snapshot(rooftop_date, rooftop_totals)
    print(f"Appended {len(rooftop_totals)} rooftop solar rows for {rooftop_date}")

    for (region, fuel_source), total_mw in sorted(totals.items(), key=lambda kv: -kv[1])[:10]:
        print(f"  {region:6s} {fuel_source:20s} {total_mw:>10.1f} MW")


if __name__ == "__main__":
    main()
