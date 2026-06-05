from pathlib import Path

from home.tests_algorithms.benchmark_utils import (
    collect_algorithm_comparison,
    collect_budget_sensitivity,
    collect_convergence_curve,
    collect_generations_sensitivity,
    collect_pareto_front,
    collect_population_sensitivity,
    plot_algorithm_comparison,
    plot_budget_cost_plateau,
    plot_budget_sensitivity,
    plot_convergence_curve,
    plot_generations_sensitivity,
    plot_pareto_front,
    plot_population_sensitivity,
)


BASE_DIR = Path(__file__).resolve().parents[2]
OUTPUT_DIR = BASE_DIR / "diagrams" / "output"


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(">> 1/6 算法对比实验 ...")
    comparison = collect_algorithm_comparison()

    print(">> 2/6 收敛性分析 ...")
    convergence_results = collect_convergence_curve()

    print(">> 3/6 Pareto 前沿采集 ...")
    pareto_results = collect_pareto_front()

    print(">> 4/6 预算敏感性分析 ...")
    budget_results = collect_budget_sensitivity()

    print(">> 5/6 种群规模敏感性分析 ...")
    population_results = collect_population_sensitivity()

    print(">> 6/6 进化代数敏感性分析 ...")
    generations_results = collect_generations_sensitivity()

    print(">> 生成图表 ...")
    plot_pareto_front(pareto_results, OUTPUT_DIR / "fig7-1_pareto_front.png")
    plot_convergence_curve(convergence_results, OUTPUT_DIR / "fig7-2_convergence_curve.png")
    plot_algorithm_comparison(comparison, OUTPUT_DIR / "fig7-3_algorithm_comparison.png")
    plot_population_sensitivity(population_results, OUTPUT_DIR / "fig7-4a_population_sensitivity.png")
    plot_generations_sensitivity(generations_results, OUTPUT_DIR / "fig7-4b_generations_sensitivity.png")
    plot_budget_sensitivity(budget_results, OUTPUT_DIR / "fig7-4c_budget_sensitivity.png")
    plot_budget_cost_plateau(budget_results, OUTPUT_DIR / "fig7-4d_budget_cost_plateau.png")

    print("\n[OK] 已生成算法测试图：")
    for p in sorted(OUTPUT_DIR.glob("*.png")):
        print(f"  {p.name}")

    print("\n算法对比摘要：")
    for name in ["NSGA-II", "Greedy", "Random"]:
        m = comparison[name]
        print(f"  {name}: 平均成本={mean(m['costs']):.1f}元, "
              f"平均路程={mean(m['distances']):.1f}km, "
              f"平均评分={mean(m['ratings']):.2f}, "
              f"平均热度={mean(m['hotnesses']):.2f}, "
              f"Pareto解={mean(m['pareto_counts']):.1f}个, "
              f"耗时={mean(m['runtimes']):.3f}s, "
              f"可行率={m['feasible_rate']*100:.0f}%")


def mean(lst):
    from statistics import mean as _mean
    return _mean(lst)


if __name__ == "__main__":
    main()
