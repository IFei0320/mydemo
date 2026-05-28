import random

from django.test import SimpleTestCase

from home.nsga2_trip_planner import build_route_payload, choose_solution, run_nsga2
from home.tests_algorithms.fixtures import comparison_spots


class NSGA2PlannerFlowTests(SimpleTestCase):
    def test_run_nsga2_returns_feasible_solutions_under_budget(self):
        random.seed(7)
        pareto_set, route_len = run_nsga2(
            comparison_spots(),
            days=2,
            budget=300,
            per_day=3,
            pop_size=12,
            generations=8,
        )

        self.assertEqual(route_len, 6)
        self.assertTrue(pareto_set)
        self.assertTrue(any(item["feasible"] for item in pareto_set))
        self.assertTrue(all(item["metrics"]["cost"] <= 300 for item in pareto_set if item["feasible"]))

    def test_choose_solution_and_build_route_payload_return_expected_shape(self):
        spots = comparison_spots()[:3]
        pareto_set = [
            {
                "route": [0, 1, 2],
                "metrics": {"cost": 100, "distance": 12, "rating": 4.7, "hotness": 8.9},
                "feasible": True,
            },
            {
                "route": [2, 1, 0],
                "metrics": {"cost": 100, "distance": 14, "rating": 4.6, "hotness": 8.7},
                "feasible": True,
            },
        ]
        sensitivities = {
            "price": 0.4,
            "distance": 0.2,
            "hotness": 0.2,
            "rating": 0.2,
            "crowd_avoid": 0.1,
        }

        best = choose_solution(pareto_set, sensitivities, budget=200)
        payload = build_route_payload(best, spots, days=1, per_day=3)

        self.assertTrue(best)
        self.assertEqual(len(payload), 3)
        self.assertIn("name", payload[0])
        self.assertIn("visit_time", payload[0])
        self.assertIn("estimated_cost", payload[0])
