#!/usr/bin/env python3
"""Collect AEMO generation reports into SQLite and the CSV used by plots.r.

Dispatch SCADA reports arrive every five minutes. Run this script at least
every five minutes to collect them promptly; each run also catches up with
unseen reports still present in NEMWeb's Current folder. That folder is
rolling, so a long outage can still leave gaps.

The export combines unit SCADA grouped by registration-list region and fuel
with AEMO's half-hourly rooftop PV measurement report. Settlement timestamps
are kept in NEM local time as published by AEMO.
"""

import csv
import io
import math
import os
import re
import sqlite3
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Callable, Pattern
from urllib.parse import urljoin

import requests

from aemo_nem_scraper import ensure_registration_list, load_duid_map

SCADA_URL = "https://nemweb.com.au/Reports/Current/Dispatch_SCADA/"
ROOFTOP_URL = "https://nemweb.com.au/Reports/Current/ROOFTOP_PV/ACTUAL/"
DB_PATH = "nem_scada.sqlite"
LEGACY_CSV = "nem_generation_by_fuel.csv"
OUTPUT_CSV = "nem_generation_by_fuel_frequent.csv"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}
SCADA_FILE_RE = re.compile(
    r'href=["\']([^"\']*PUBLIC_DISPATCHSCADA_\d{12}_\d+\.zip)["\']', re.I
)
ROOFTOP_FILE_RE = re.compile(
    r'href=["\']([^"\']*PUBLIC_ROOFTOP_PV_ACTUAL_MEASUREMENT_\d+_\d+\.zip)["\']',
    re.I,
)
OUTPUT_FIELDS = ["settlement_date", "region", "fuel_source", "total_mw"]


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS unit_scada (
            settlementdate TEXT NOT NULL,
            duid TEXT NOT NULL,
            scadavalue REAL,
            PRIMARY KEY (settlementdate, duid)
        );
        CREATE TABLE IF NOT EXISTS rooftop_pv (
            settlementdate TEXT NOT NULL,
            region TEXT NOT NULL,
            power_mw REAL NOT NULL,
            PRIMARY KEY (settlementdate, region)
        );
        CREATE TABLE IF NOT EXISTS unit_metadata (
            duid TEXT PRIMARY KEY,
            region TEXT NOT NULL,
            fuel_source TEXT NOT NULL,
            dispatch_type TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS generation_by_fuel (
            settlement_date TEXT NOT NULL,
            region TEXT NOT NULL,
            fuel_source TEXT NOT NULL,
            total_mw REAL NOT NULL,
            PRIMARY KEY (settlement_date, region, fuel_source)
        );
        CREATE TABLE IF NOT EXISTS files_loaded (
            filename TEXT PRIMARY KEY,
            loaded_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS collector_state (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """
    )


def list_files(
    session: requests.Session, base_url: str, file_re: Pattern[str]
) -> list[str]:
    response = session.get(base_url, timeout=60)
    response.raise_for_status()
    return sorted(
        {urljoin(base_url, href) for href in file_re.findall(response.text)}
    )


def normalize_settlement_date(value: str) -> str:
    return value.strip().replace("/", "-")


def parse_scada_csv(text: str) -> list[tuple[str, str, float | None]]:
    header: list[str] | None = None
    records: list[tuple[str, str, float | None]] = []
    required = {"SETTLEMENTDATE", "DUID", "SCADAVALUE"}

    for row in csv.reader(io.StringIO(text)):
        if len(row) >= 3 and row[:3] == ["I", "DISPATCH", "UNIT_SCADA"]:
            header = row
            missing = required.difference(header)
            if missing:
                raise ValueError(f"SCADA report header is missing {sorted(missing)}")
            continue
        if len(row) >= 3 and row[:3] == ["D", "DISPATCH", "UNIT_SCADA"]:
            if header is None:
                raise ValueError("SCADA data appeared before its header")
            record = dict(zip(header, row))
            value_text = record["SCADAVALUE"].strip()
            value = float(value_text) if value_text else None
            if value is not None and not math.isfinite(value):
                raise ValueError(f"Invalid SCADA value: {value_text}")
            records.append(
                (
                    normalize_settlement_date(record["SETTLEMENTDATE"]),
                    record["DUID"].strip(),
                    value,
                )
            )

    if header is None or not records:
        raise ValueError("SCADA report contained no usable unit readings")
    return records


def parse_rooftop_csv(text: str) -> list[tuple[str, str, float]]:
    header: list[str] | None = None
    records: list[tuple[str, str, float]] = []
    required = {"INTERVAL_DATETIME", "REGIONID", "POWER", "TYPE"}

    for row in csv.reader(io.StringIO(text)):
        if len(row) >= 3 and row[:3] == ["I", "ROOFTOP", "ACTUAL"]:
            header = row
            missing = required.difference(header)
            if missing:
                raise ValueError(f"Rooftop report header is missing {sorted(missing)}")
            continue
        if len(row) >= 3 and row[:3] == ["D", "ROOFTOP", "ACTUAL"]:
            if header is None:
                raise ValueError("Rooftop data appeared before its header")
            record = dict(zip(header, row))
            if record["TYPE"].strip().upper() != "MEASUREMENT":
                continue
            value_text = record["POWER"].strip()
            value = float(value_text)
            if not math.isfinite(value):
                raise ValueError(f"Invalid rooftop PV value: {value_text}")
            records.append(
                (
                    normalize_settlement_date(record["INTERVAL_DATETIME"]),
                    record["REGIONID"].strip(),
                    value,
                )
            )

    if header is None or not records:
        raise ValueError("Rooftop report contained no measurement readings")
    return records


def read_zip_csv(content: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        csv_files = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if not csv_files:
            raise ValueError("ZIP report did not contain a CSV file")
        return archive.read(csv_files[0]).decode("utf-8-sig")


def fetch_with_retry(
    session: requests.Session, url: str, tries: int = 3
) -> bytes:
    for attempt in range(1, tries + 1):
        try:
            response = session.get(url, timeout=60)
            response.raise_for_status()
            return response.content
        except requests.RequestException:
            if attempt == tries:
                raise
            time.sleep(5 * attempt)
    raise RuntimeError(f"Could not download {url}")


def seed_export(conn: sqlite3.Connection, path: str) -> None:
    """Preserve historical rows written by the previous snapshot scraper."""
    if not os.path.exists(path):
        return
    if conn.execute("SELECT 1 FROM generation_by_fuel LIMIT 1").fetchone():
        return
    with open(path, newline="", encoding="utf-8-sig") as handle, conn:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or not set(OUTPUT_FIELDS).issubset(reader.fieldnames):
            raise ValueError(f"{path} does not have the expected generation CSV columns")
        for row in reader:
            conn.execute(
                """
                INSERT OR REPLACE INTO generation_by_fuel
                    (settlement_date, region, fuel_source, total_mw)
                VALUES (?, ?, ?, ?)
                """,
                (
                    normalize_settlement_date(row["settlement_date"]),
                    row["region"],
                    row["fuel_source"],
                    float(row["total_mw"]),
                ),
            )


def update_unit_metadata(
    conn: sqlite3.Connection, duid_map: dict[str, tuple[str, str, str]]
) -> None:
    with conn:
        conn.executemany(
            """
            INSERT INTO unit_metadata (duid, region, fuel_source, dispatch_type)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(duid) DO UPDATE SET
                region = excluded.region,
                fuel_source = excluded.fuel_source,
                dispatch_type = excluded.dispatch_type
            """,
            (
                (duid, region, fuel_source, dispatch_type)
                for duid, (region, fuel_source, dispatch_type) in duid_map.items()
            ),
        )


def aggregate_generation(conn: sqlite3.Connection) -> None:
    with conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO generation_by_fuel
                (settlement_date, region, fuel_source, total_mw)
            SELECT s.settlementdate, m.region, m.fuel_source,
                   SUM(CASE WHEN m.dispatch_type = 'Load'
                            THEN -s.scadavalue ELSE s.scadavalue END)
            FROM unit_scada AS s
            JOIN unit_metadata AS m ON m.duid = s.duid
            WHERE s.scadavalue IS NOT NULL
            GROUP BY s.settlementdate, m.region, m.fuel_source
            """
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO generation_by_fuel
                (settlement_date, region, fuel_source, total_mw)
            SELECT settlementdate, region, 'Rooftop Solar', SUM(power_mw)
            FROM rooftop_pv
            GROUP BY settlementdate, region
            """
        )


def aggregate_new_intervals(
    conn: sqlite3.Connection, report_type: str, rows: list[tuple]
) -> None:
    settlement_dates = {row[0] for row in rows}
    for settlement_date in settlement_dates:
        if report_type == "scada":
            conn.execute(
                """
                INSERT OR REPLACE INTO generation_by_fuel
                    (settlement_date, region, fuel_source, total_mw)
                SELECT s.settlementdate, m.region, m.fuel_source,
                       SUM(CASE WHEN m.dispatch_type = 'Load'
                                THEN -s.scadavalue ELSE s.scadavalue END)
                FROM unit_scada AS s
                JOIN unit_metadata AS m ON m.duid = s.duid
                WHERE s.settlementdate = ? AND s.scadavalue IS NOT NULL
                GROUP BY s.settlementdate, m.region, m.fuel_source
                """,
                (settlement_date,),
            )
        else:
            conn.execute(
                """
                INSERT OR REPLACE INTO generation_by_fuel
                    (settlement_date, region, fuel_source, total_mw)
                SELECT settlementdate, region, 'Rooftop Solar', SUM(power_mw)
                FROM rooftop_pv
                WHERE settlementdate = ?
                GROUP BY settlementdate, region
                """,
                (settlement_date,),
            )


def write_export(conn: sqlite3.Connection, path: str = OUTPUT_CSV) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=str(output_path.parent),
            delete=False,
        ) as handle:
            temporary_path = handle.name
            writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS)
            writer.writeheader()
            for settlement_date, region, fuel_source, total_mw in conn.execute(
                """
                SELECT settlement_date, region, fuel_source, total_mw
                FROM generation_by_fuel
                ORDER BY settlement_date, region, fuel_source
                """
            ):
                writer.writerow(
                    {
                        "settlement_date": settlement_date,
                        "region": region,
                        "fuel_source": fuel_source,
                        "total_mw": round(total_mw, 3),
                    }
                )
        os.replace(temporary_path, output_path)
    finally:
        if temporary_path and os.path.exists(temporary_path):
            os.unlink(temporary_path)


def load_reports(
    session: requests.Session,
    conn: sqlite3.Connection,
    base_url: str,
    file_re: Pattern[str],
    parser: Callable[
        [str],
        list[tuple[str, str, float | None]] | list[tuple[str, str, float]],
    ],
    report_type: str,
    seen: set[str],
) -> tuple[int, int]:
    failures = 0
    loaded_count = 0
    for url in list_files(session, base_url, file_re):
        filename = url.rsplit("/", 1)[-1]
        if filename in seen:
            continue
        try:
            rows = parser(read_zip_csv(fetch_with_retry(session, url)))
            with conn:
                if report_type == "scada":
                    conn.executemany(
                        "INSERT OR REPLACE INTO unit_scada VALUES (?, ?, ?)", rows
                    )
                else:
                    conn.executemany(
                        "INSERT OR REPLACE INTO rooftop_pv VALUES (?, ?, ?)", rows
                    )
                aggregate_new_intervals(conn, report_type, rows)
                conn.execute(
                    "INSERT INTO files_loaded (filename) VALUES (?)", (filename,)
                )
            seen.add(filename)
            loaded_count += 1
            print(f"Loaded {filename}: {len(rows)} readings")
        except (
            requests.RequestException,
            zipfile.BadZipFile,
            UnicodeDecodeError,
            csv.Error,
            KeyError,
            ValueError,
            sqlite3.Error,
        ) as error:
            failures += 1
            print(f"Failed {filename}: {error}", file=sys.stderr)
        finally:
            time.sleep(0.2)
    return loaded_count, failures


def main() -> int:
    registration_path = ensure_registration_list()
    duid_map = load_duid_map(registration_path)

    conn = sqlite3.connect(DB_PATH)
    try:
        init_db(conn)
        seed_export(conn, OUTPUT_CSV if os.path.exists(OUTPUT_CSV) else LEGACY_CSV)
        update_unit_metadata(conn, duid_map)
        if not conn.execute(
            "SELECT 1 FROM collector_state WHERE key = 'aggregation_backfilled'"
        ).fetchone():
            aggregate_generation(conn)
            with conn:
                conn.execute(
                    "INSERT INTO collector_state (key, value) VALUES (?, ?)",
                    ("aggregation_backfilled", "1"),
                )
        seen = {row[0] for row in conn.execute("SELECT filename FROM files_loaded")}

        with requests.Session() as session:
            session.headers.update(HEADERS)
            scada_loaded, scada_failures = load_reports(
                session,
                conn,
                SCADA_URL,
                SCADA_FILE_RE,
                parse_scada_csv,
                "scada",
                seen,
            )
            rooftop_loaded, rooftop_failures = load_reports(
                session,
                conn,
                ROOFTOP_URL,
                ROOFTOP_FILE_RE,
                parse_rooftop_csv,
                "rooftop",
                seen,
            )

        write_export(conn)
        print(
            f"Loaded {scada_loaded} SCADA and {rooftop_loaded} rooftop reports; "
            f"exported {OUTPUT_CSV}"
        )
        failures = scada_failures + rooftop_failures
        if failures:
            print(
                f"{failures} report(s) failed and will be retried on the next run.",
                file=sys.stderr,
            )
            return 1
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
