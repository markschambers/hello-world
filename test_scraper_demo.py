import unittest

from scraper_demo import parse_quotes


class ScraperDemoTests(unittest.TestCase):
    def test_parse_quotes_returns_expected_fields(self) -> None:
        sample_html = """
        <div class="quote">
            <span class="text">&quot;A simple test quote&quot;</span>
            <span class="author">Jane Doe</span>
            <a class="tag" href="/tag/test/">test</a>
            <a class="tag" href="/tag/demo/">demo</a>
        </div>
        """

        quotes = parse_quotes(sample_html)

        self.assertEqual(len(quotes), 1)
        self.assertEqual(quotes[0]["text"], '"A simple test quote"')
        self.assertEqual(quotes[0]["author"], "Jane Doe")
        self.assertEqual(quotes[0]["tags"], ["test", "demo"])


if __name__ == "__main__":
    unittest.main()
