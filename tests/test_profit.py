"""core/profit.py birim testleri — dahili kâr/iskonto hesaplama motoru."""
import unittest

from core.profit import (
    calculate_margin, max_discount, margin_status,
    count_items_missing_cost, DEFAULT_YELLOW_THRESHOLD,
)


class TestCalculateMargin(unittest.TestCase):
    def test_normal_case(self):
        r = calculate_margin(total_cost=1200, total_sale=1800)
        self.assertAlmostEqual(r["profit"], 600.0)
        self.assertAlmostEqual(r["margin_pct"], 33.33, places=2)

    def test_zero_sale_no_division_error(self):
        r = calculate_margin(total_cost=100, total_sale=0)
        self.assertAlmostEqual(r["profit"], -100.0)
        self.assertAlmostEqual(r["margin_pct"], 0.0)

    def test_zero_cost(self):
        r = calculate_margin(total_cost=0, total_sale=500)
        self.assertAlmostEqual(r["profit"], 500.0)
        self.assertAlmostEqual(r["margin_pct"], 100.0)

    def test_loss_negative_margin(self):
        r = calculate_margin(total_cost=1000, total_sale=800)
        self.assertAlmostEqual(r["profit"], -200.0)
        self.assertAlmostEqual(r["margin_pct"], -25.0)

    def test_none_inputs_do_not_raise(self):
        r = calculate_margin(total_cost=None, total_sale=None)
        self.assertAlmostEqual(r["profit"], 0.0)
        self.assertAlmostEqual(r["margin_pct"], 0.0)


class TestMaxDiscount(unittest.TestCase):
    def test_normal_case(self):
        r = max_discount(total_cost=1200, total_sale=1800)
        self.assertAlmostEqual(r["max_discount_amount"], 600.0)
        self.assertAlmostEqual(r["max_discount_pct"], 33.33, places=2)

    def test_breakeven_zero_discount(self):
        r = max_discount(total_cost=1000, total_sale=1000)
        self.assertAlmostEqual(r["max_discount_amount"], 0.0)
        self.assertAlmostEqual(r["max_discount_pct"], 0.0)

    def test_already_below_cost_clamped_to_zero(self):
        """Zaten maliyetin altındaysa 'ek iskonto' negatif değil, 0 olmalı."""
        r = max_discount(total_cost=1000, total_sale=800)
        self.assertAlmostEqual(r["max_discount_amount"], 0.0)
        self.assertAlmostEqual(r["max_discount_pct"], 0.0)

    def test_zero_sale_no_division_error(self):
        r = max_discount(total_cost=0, total_sale=0)
        self.assertAlmostEqual(r["max_discount_amount"], 0.0)
        self.assertAlmostEqual(r["max_discount_pct"], 0.0)


class TestMarginStatus(unittest.TestCase):
    def test_healthy_is_green(self):
        self.assertEqual(margin_status(50.0), "green")

    def test_just_above_threshold_is_green(self):
        self.assertEqual(margin_status(DEFAULT_YELLOW_THRESHOLD + 0.01), "green")

    def test_at_threshold_is_yellow(self):
        self.assertEqual(margin_status(DEFAULT_YELLOW_THRESHOLD), "yellow")

    def test_thin_margin_is_yellow(self):
        self.assertEqual(margin_status(5.0), "yellow")

    def test_zero_is_red(self):
        self.assertEqual(margin_status(0.0), "red")

    def test_negative_is_red(self):
        self.assertEqual(margin_status(-10.0), "red")

    def test_custom_threshold(self):
        self.assertEqual(margin_status(15.0, yellow_threshold=20.0), "yellow")
        self.assertEqual(margin_status(25.0, yellow_threshold=20.0), "green")


class TestCountItemsMissingCost(unittest.TestCase):
    def test_none_missing(self):
        self.assertEqual(count_items_missing_cost([10, 20, 30]), 0)

    def test_some_missing(self):
        self.assertEqual(count_items_missing_cost([10, 0, 30, None]), 2)

    def test_all_missing(self):
        self.assertEqual(count_items_missing_cost([0, 0, 0]), 3)

    def test_empty_list(self):
        self.assertEqual(count_items_missing_cost([]), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
