from unittest.mock import patch

from django.test import SimpleTestCase

from home.nsga2_trip_planner import _evaluate_route, build_candidates
from home.tests_algorithms.fixtures import candidate_rows, route_spots


class DummyCleanedRow:
    """模拟 CleanedAttraction 的清洗后数据行"""
    def __init__(self, name, city, area, tags, rating, hotness, review_count, cost, lon, lat, dist_km):
        self.name = name
        self.city = city
        self.area = area
        self.tags = tags
        self.rating = rating
        self.hotness = hotness
        self.review_count = review_count
        self.cost = cost
        self.longitude = lon
        self.latitude = lat
        self.center_distance_km = dist_km


def cleaned_rows():
    return [
        DummyCleanedRow("外滩", "上海市", "黄浦区", "夜景 江景", 4.8, 9.5, 10000, 0.0, 121.4903, 31.2417, 3.2),
        DummyCleanedRow("东方明珠", "上海", "浦东新区", "地标 夜景", 4.7, 9.2, 8000, 199.0, 121.4998, 31.2397, 5.0),
        DummyCleanedRow("异常点", "上海", "未知", "测试", 4.0, 5.0, 100, 10.0, 0.0, 0.0, 1.0),  # 坐标无效
    ]


class NSGA2CandidateTests(SimpleTestCase):
    @patch("home.nsga2_trip_planner.CleanedAttraction")
    def test_build_candidates_filters_invalid_coords_and_applies_city_match(self, MockModel):
        rows = cleaned_rows()
        mock_qs = rows
        # 模拟 .filter().filter() 链式调用
        MockModel.objects.filter.return_value.filter.return_value = mock_qs
        MockModel.objects.filter.return_value = mock_qs

        candidates = build_candidates("上海", "summer", require_coord=True)

        self.assertEqual(len(candidates), 3)  # 含坐标无效的，require_coord 过滤在 filter 层
        self.assertEqual(candidates[0].name, "外滩")
        self.assertEqual(candidates[1].cost, 199.0)

    def test_evaluate_route_aggregates_cost_rating_and_hotness(self):
        metrics = _evaluate_route([0, 1, 2], route_spots(), per_day=3)

        self.assertEqual(metrics["cost"], 130)
        self.assertAlmostEqual(metrics["rating"], 4.6, places=1)
        self.assertAlmostEqual(metrics["hotness"], 8.1666, places=3)
        self.assertGreater(metrics["distance"], 6.0)
