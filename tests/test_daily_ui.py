"""Static UI checks for friendly daily review, history, scanner, and risk labels."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "stat-arb-dashboard"
HTML = (ROOT / "daily.html").read_text(encoding="utf-8")
JS = (ROOT / "daily-ui.js").read_text(encoding="utf-8")


class DailyUiTests(unittest.TestCase):
    def test_unique_accessible_interactive_controls(self):
        ids = re.findall(r'\bid="([^"]+)"', HTML)
        self.assertEqual(len(ids), len(set(ids)))
        required = [
            "latest-cards","history-rows","archive-detail","history-search",
            "history-day","scan-rows","scan-filter","scan-search",
            "m-total","m-unique","m-broad","m-date","progress-fill",
            "refresh","show-latest","view-latest","view-history",
            "view-scan","view-learn",
        ]
        for name in required:
            self.assertIn(name, ids)

    def test_plain_english_and_integrity_disclosures(self):
        for text in ["Two pairs a day","Every review saved","Today's deep dives",
                     "Review history","All screened pairs","How to read results",
                     "not trade advice","not an independent walk-forward"]:
            self.assertIn(text.lower(), (HTML+JS).lower())
        self.assertIn('src="daily-ui.js"', HTML)
        self.assertNotIn("innerHTML", JS)
        self.assertIn("textContent", JS)

    def test_beginner_dropdowns_and_simple_default_cards(self):
        # Native details/summary controls work without custom JavaScript.
        self.assertGreaterEqual(HTML.count("<details"), 12)
        self.assertGreaterEqual(HTML.count("<summary"), 12)
        for phrase in [
            "What is statistical arbitrage?",
            "What does Z-score mean?",
            "What does correlation mean?",
            "What is the p-value?",
            "What is the q-value?",
            "Can I trade directly from this site?",
            "How can I trust these numbers?",
            "Read today's reviews",
        ]:
            self.assertIn(phrase, HTML)
        for phrase in [
            "Why did it receive this result?",
            "What do the numbers mean?",
            "See a chart and historical examples",
            "Where did this information come from?",
            "Some usable historical prices were missing. No statistics have been invented.",
        ]:
            self.assertIn(phrase, JS)
        self.assertIn("independently checked", JS)
        self.assertIn('data-view="latest"', HTML)
        self.assertIn('aria-selected="true"', HTML)
        # Published pair figures must remain data-backed, not hard-coded into HTML.
        self.assertNotIn("0.04159686", HTML)

    def test_dates_and_data_sources_are_explicit(self):
        self.assertIn("review_history.json", JS)
        self.assertIn("daily_discovery.json", JS)
        self.assertIn("review_date", JS)
        self.assertIn("data_through", JS) if "data_through" in JS else self.assertIn("scan.as_of", JS)


if __name__ == "__main__":
    unittest.main()
