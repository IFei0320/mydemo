from django.test import SimpleTestCase

from home.tests_algorithms.benchmark_utils import (
    collect_algorithm_comparison,
    collect_budget_sensitivity,
    collect_population_sensitivity,
)


class NSGA2BenchmarkTests(SimpleTestCase):
    def test_algorithm_comparison_returns_expected_metrics(self):
        results = collect_algorithm_comparison(runs=2)

        self.assertIn("NSGA-II", results)
        self.assertIn("Greedy", results)
        self.assertIn("Random", results)
        self.assertGreaterEqual(results["NSGA-II"]["avg_solution_count"], 1.0)

    def test_budget_sensitivity_returns_budget_series(self):
        results = collect_budget_sensitivity([250, 300], runs=2)

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["budget"], 250)
        self.assertIn("feasible_rate", results[0])

    def test_population_sensitivity_returns_population_series(self):
        results = collect_population_sensitivity([8, 12], runs=2)

        self.assertEqual(len(results), 2)
        self.assertEqual(results[1]["pop_size"], 12)
        self.assertIn("avg_runtime", results[1])
