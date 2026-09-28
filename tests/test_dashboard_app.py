"""Headless smoke tests for every dashboard analysis view."""

import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest


class DashboardAppTests(unittest.TestCase):
    def test_all_analysis_views_render_without_exceptions(self) -> None:
        for view in ["Executive overview", "Sales", "Products", "Customers"]:
            with self.subTest(view=view):
                app_path = Path(__file__).resolve().parents[1] / "dashboard" / "app.py"
                app = AppTest.from_file(app_path).run()
                app.segmented_control[0].set_value(view).run()
                self.assertEqual(
                    len(app.exception), 0,
                    "\n".join(item.message for item in app.exception),
                )

    def test_empty_filter_selection_shows_an_empty_state(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "dashboard" / "app.py"
        app = AppTest.from_file(app_path).run()
        app.multiselect[0].set_value([]).run()

        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any("No orders match" in item.value for item in app.info))


if __name__ == "__main__":
    unittest.main()