import unittest

from worldbank_demo import normalize_records


class WorldBankDemoTests(unittest.TestCase):
    def test_normalize_records_creates_rows_with_expected_columns(self) -> None:
        payload = [
            {
                "page": 1,
                "pages": 1,
                "per_page": 2,
                "total": 2,
            },
            [
                {
                    "country": {"id": "US", "value": "United States"},
                    "date": "2022",
                    "value": 254627000000000.0,
                    "indicator": {"id": "NY.GDP.MKTP.CD", "value": "GDP (current US$)"},
                },
                {
                    "country": {"id": "CA", "value": "Canada"},
                    "date": "2022",
                    "value": 2390000000000.0,
                    "indicator": {"id": "NY.GDP.MKTP.CD", "value": "GDP (current US$)"},
                },
            ],
        ]

        rows = normalize_records(payload)

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["country"], "United States")
        self.assertEqual(rows[0]["year"], 2022)
        self.assertEqual(rows[0]["indicator"], "GDP (current US$)")
        self.assertEqual(rows[0]["value"], 254627000000000.0)


if __name__ == "__main__":
    unittest.main()
