from django.test import SimpleTestCase

from home.data_utils import _normalize_coord_pair, _parse_distance_km, _parse_price


class NSGA2ParsingTests(SimpleTestCase):
    def test_parse_price_handles_free_and_numeric_strings(self):
        self.assertEqual(_parse_price("免费"), 0.0)
        self.assertEqual(_parse_price(None), 0.0)
        self.assertEqual(_parse_price("78元"), 78.0)
        self.assertEqual(_parse_price(" 99.5 "), 99.5)

    def test_parse_distance_supports_meter_and_km(self):
        self.assertEqual(_parse_distance_km("1.5km"), 1.5)
        self.assertEqual(_parse_distance_km("800m"), 0.8)
        self.assertEqual(_parse_distance_km(None), 0.0)

    def test_normalize_coord_pair_swaps_reversed_values(self):
        lon, lat = _normalize_coord_pair(31.2304, 121.4737)
        self.assertAlmostEqual(lon, 121.4737, places=4)
        self.assertAlmostEqual(lat, 31.2304, places=4)
