from django.test import SimpleTestCase

from home.nsga2_trip_planner import _evaluate_route, build_candidates
from home.tests_algorithms.fixtures import DummyQuerySet, candidate_rows, route_spots


class NSGA2CandidateTests(SimpleTestCase):
    def test_build_candidates_filters_invalid_coords_and_applies_city_match(self):
        queryset = DummyQuerySet(candidate_rows())

        candidates = build_candidates(queryset, "上海", "summer")

        self.assertEqual(len(candidates), 2)
        self.assertEqual(candidates[0].name, "外滩")
        self.assertEqual(candidates[1].cost, 199.0)

    def test_evaluate_route_aggregates_cost_rating_and_hotness(self):
        metrics = _evaluate_route([0, 1, 2], route_spots(), per_day=3)

        self.assertEqual(metrics["cost"], 130)
        self.assertAlmostEqual(metrics["rating"], 4.6, places=1)
        self.assertAlmostEqual(metrics["hotness"], 8.1666, places=3)
        self.assertGreater(metrics["distance"], 6.0)
