import random

from django.test import SimpleTestCase

from home.nsga2_trip_planner import _evaluate_route, run_nsga2
from home.tests_algorithms.fixtures import comparison_spots


class NSGA2ComparisonTests(SimpleTestCase):
    def test_nsga2_has_advantage_over_greedy_in_solution_diversity_and_cost(self):
        spots = comparison_spots()

        random.seed(11)
        pareto_set, _ = run_nsga2(spots, days=2, budget=300, per_day=3, pop_size=18, generations=12)
        greedy_solution = self._greedy_baseline(spots, route_len=6, budget=300)

        self.assertTrue(pareto_set)
        self.assertTrue(greedy_solution["feasible"])

        nsga_costs = sorted({round(item["metrics"]["cost"], 2) for item in pareto_set if item["feasible"]})
        greedy_cost = greedy_solution["metrics"]["cost"]
        best_nsga_cost = min(nsga_costs)

        self.assertGreaterEqual(len(nsga_costs), 2)
        self.assertLessEqual(best_nsga_cost, greedy_cost)

    def _greedy_baseline(self, spots, route_len, budget):
        ranked = sorted(
            range(len(spots)),
            key=lambda idx: (-spots[idx].rating, -spots[idx].hotness, spots[idx].cost),
        )
        selected = []
        total_cost = 0.0
        for idx in ranked:
            spot = spots[idx]
            if len(selected) >= route_len:
                break
            if total_cost + spot.cost > budget:
                continue
            selected.append(idx)
            total_cost += spot.cost

        if len(selected) < route_len:
            for idx in ranked:
                if idx in selected:
                    continue
                selected.append(idx)
                if len(selected) >= route_len:
                    break

        metrics = _evaluate_route(selected, spots, per_day=3)
        return {
            "route": selected,
            "metrics": metrics,
            "feasible": metrics["cost"] <= budget,
        }
