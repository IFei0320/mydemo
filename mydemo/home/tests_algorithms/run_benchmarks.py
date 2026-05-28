from pathlib import Path

from home.tests_algorithms.benchmark_utils import (
    collect_algorithm_comparison,
    collect_budget_sensitivity,
    collect_convergence_curve,
    collect_pareto_front,
    collect_population_sensitivity,
    plot_algorithm_comparison,
    plot_budget_sensitivity,
    plot_convergence_curve,
    plot_pareto_front,
    plot_population_sensitivity,
)


BASE_DIR = Path(__file__).resolve().parents[2]
OUTPUT_DIR = BASE_DIR / "diagrams" / "output"


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    comparison = collect_algorithm_comparison()
    budget_results = collect_budget_sensitivity([200, 250, 300, 350, 400, 500])
    population_results = collect_population_sensitivity([8, 12, 18, 24, 32, 40])
    convergence_results = collect_convergence_curve()
    pareto_results = collect_pareto_front()

    plot_algorithm_comparison(comparison, OUTPUT_DIR / "fig7-1_algorithm_comparison.png")
    plot_budget_sensitivity(budget_results, OUTPUT_DIR / "fig7-2_budget_sensitivity.png")
    plot_population_sensitivity(population_results, OUTPUT_DIR / "fig7-3_population_sensitivity.png")
    plot_convergence_curve(convergence_results, OUTPUT_DIR / "fig7-4_convergence_curve.png")
    plot_pareto_front(pareto_results, OUTPUT_DIR / "fig7-5_pareto_front.png")

    print("[OK] 已生成算法测试图：")
    print(OUTPUT_DIR / "fig7-1_algorithm_comparison.png")
    print(OUTPUT_DIR / "fig7-2_budget_sensitivity.png")
    print(OUTPUT_DIR / "fig7-3_population_sensitivity.png")
    print(OUTPUT_DIR / "fig7-4_convergence_curve.png")
    print(OUTPUT_DIR / "fig7-5_pareto_front.png")
    print("\n算法对比摘要：")
    for name, metrics in comparison.items():
        print(
            f"- {name}: 平均最优成本={metrics['avg_best_cost']:.2f}元, "
            f"平均运行时间={metrics['avg_runtime']:.4f}s, "
            f"平均可行方案数={metrics['avg_solution_count']:.2f}, "
            f"可行率={metrics['feasible_rate'] * 100:.1f}%"
        )


if __name__ == "__main__":
    main()
