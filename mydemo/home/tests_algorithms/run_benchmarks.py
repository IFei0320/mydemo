"""论文图表生成 —— 使用数据库真实数据, 自动适配参数。"""
import json
import math
from pathlib import Path
from statistics import mean as _mean

from home.tests_algorithms.benchmark_utils import (
    collect_algorithm_comparison,
    collect_budget_sensitivity,
    collect_convergence_curve,
    collect_generations_sensitivity,
    collect_pareto_front,
    collect_population_sensitivity,
    db_spots,
    plot_algorithm_comparison,
    plot_convergence_curve,
    plot_pareto_front,
    plot_sensitivity_grid,
)


BASE_DIR = Path(__file__).resolve().parents[2]
OUTPUT_DIR = BASE_DIR / "diagrams" / "output"
DATA_DIR = BASE_DIR / "diagrams" / "data"


def _clean(obj):
    """递归把 nan/inf 替换成 None，使 JSON 可序列化。"""
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean(v) for v in obj]
    return obj


def save_json(name: str, data) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / f"{name}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(_clean(data), f, ensure_ascii=False, indent=2)
    print(f"   [data] 已保存 {path.name}")


def mean(lst):
    return _mean(lst)


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    spots = db_spots()
    costs = sorted(s.cost for s in spots)
    days = 3
    per_day = 3
    route_len = days * per_day

    min9 = sum(costs[:route_len])
    max9 = sum(costs[-route_len:])
    median9 = sum(sorted(costs)[len(costs)//2 - route_len//2: len(costs)//2 - route_len//2 + route_len])

    budget = 280
    budget = max(budget, min9 + 50)

    print(f"数据: {len(spots)}个收费景点, 价格{costs[0]:.0f}-{costs[-1]:.0f}元")
    print(f"9景点成本范围: {min9:.0f}-{max9:.0f}元, 中位成本: {median9:.0f}元")
    print(f"实验参数: {days}天×{per_day}景点/天={route_len}景点, 预算={budget}元\n")

    # ── 1. 算法对比 ──
    print(">> 1/6 算法对比 ...")
    comparison = collect_algorithm_comparison(
        spots, days=days, budget=budget, per_day=per_day, runs=8)

    # 整理成论文表格格式
    comparison_summary = {}
    for name in ["NSGA-II", "Greedy", "Random"]:
        m = comparison[name]
        comparison_summary[name] = {
            "avg_cost":          round(mean(m["costs"]), 2),
            "avg_distance":      round(mean(m["distances"]), 1),
            "avg_rating":        round(mean(m["ratings"]), 2),
            "avg_hotness":       round(mean(m["hotnesses"]), 2),
            "avg_runtime_s":     round(mean(m["runtimes"]), 4),
            "avg_pareto_count":  round(mean(m["pareto_counts"]), 1),
            "feasible_rate_pct": round(m["feasible_rate"] * 100, 1),
            "raw_costs":         [round(v, 2) for v in m["costs"]],
            "raw_distances":     [round(v, 1) for v in m["distances"]],
            "raw_ratings":       [round(v, 3) for v in m["ratings"]],
            "raw_hotnesses":     [round(v, 3) for v in m["hotnesses"]],
            "raw_runtimes":      [round(v, 4) for v in m["runtimes"]],
            "raw_pareto_counts": list(m["pareto_counts"]),
        }
    save_json("table7-6_algorithm_comparison", comparison_summary)

    # ── 2. 收敛性 ──
    print(">> 2/6 收敛性分析 ...")
    convergence_results = collect_convergence_curve(
        spots, days=days, budget=budget, per_day=per_day, runs=10)
    save_json("fig7-2_convergence_curve", convergence_results)

    # ── 3. Pareto前沿 ──
    print(">> 3/6 Pareto前沿 ...")
    pareto_results = collect_pareto_front(
        spots, days=days, budget=budget, per_day=per_day)
    pareto_summary = {
        "total_points": len(pareto_results),
        "cost_range":   [round(min(p["cost"] for p in pareto_results), 2),
                         round(max(p["cost"] for p in pareto_results), 2)],
        "rating_range": [round(min(p["rating"] for p in pareto_results), 3),
                         round(max(p["rating"] for p in pareto_results), 3)],
        "distance_range": [round(min(p["distance"] for p in pareto_results), 1),
                           round(max(p["distance"] for p in pareto_results), 1)],
        "points": [{"cost": round(p["cost"], 2),
                    "rating": round(p["rating"], 3),
                    "distance": round(p["distance"], 1),
                    "hotness": round(p["hotness"], 3)}
                   for p in pareto_results],
    }
    save_json("fig7-1_pareto_front", pareto_summary)

    # ── 4. 预算敏感性 ──
    print(">> 4/6 预算敏感性 ...")
    b_start = max(50, int(min9 - 20))
    b_end = int(budget * 2.2)
    step = max(10, int((b_end - b_start) / 14))
    budget_list = list(range(b_start, b_end + 1, step))
    budget_results = collect_budget_sensitivity(
        budget_list, spots=spots, days=days, per_day=per_day,
        pop_size=30, generations=30, runs=10,
    )
    save_json("fig7-4c_budget_sensitivity", budget_results)

    # ── 5. 代数敏感性 ──
    print(">> 5/6 代数敏感性 ...")
    generations_results = collect_generations_sensitivity(
        spots, budget=budget, days=days, per_day=per_day, runs=8)
    save_json("fig7-4b_generations_sensitivity", generations_results)

    # ── 6. 种群大小敏感性 ──
    print(">> 6/6 种群大小敏感性 ...")
    population_results = collect_population_sensitivity(
        pop_sizes=[10, 20, 30, 40, 60, 80, 100],
        spots=spots, budget=budget, days=days, per_day=per_day, generations=50, runs=6)
    save_json("fig7-4a_population_sensitivity", population_results)

    # ── 生成图表 ──
    print(">> 生成图表 ...")
    plot_pareto_front(pareto_results, OUTPUT_DIR / "fig7-1_pareto_front.svg")
    plot_convergence_curve(convergence_results, OUTPUT_DIR / "fig7-2_convergence_curve.svg")
    plot_algorithm_comparison(comparison, OUTPUT_DIR / "fig7-3_algorithm_comparison.svg")
    plot_sensitivity_grid(
        population_results, generations_results, budget_results,
        OUTPUT_DIR / "fig7-4_sensitivity.svg"
    )

    print("\n[OK] 已生成图表：")
    for p in sorted(OUTPUT_DIR.glob("*.svg")):
        print(f"  {p.name}")

    print(f"\n[OK] 已保存原始数据：")
    for p in sorted(DATA_DIR.glob("*.json")):
        print(f"  {p.name}")

    # ── 终端打印论文关键数据 ──
    print(f"\n{'='*60}")
    print(f"【论文表7-6 关键数据】（{days}天{route_len}景点，预算{budget}元，各算法8次均值）")
    print(f"{'='*60}")
    print(f"{'算法':<12} {'成本(元)':<10} {'路程(km)':<10} {'评分':<8} {'热度':<8} {'时间(s)':<10} {'Pareto数':<10} {'可行率'}")
    print(f"{'-'*80}")
    for name in ["NSGA-II", "Greedy", "Random"]:
        s = comparison_summary[name]
        print(f"{name:<12} {s['avg_cost']:<10.2f} {s['avg_distance']:<10.1f} "
              f"{s['avg_rating']:<8.2f} {s['avg_hotness']:<8.2f} "
              f"{s['avg_runtime_s']:<10.4f} {s['avg_pareto_count']:<10.1f} "
              f"{s['feasible_rate_pct']:.1f}%")

    print(f"\n【论文图7-1 Pareto前沿】")
    print(f"  总解数: {pareto_summary['total_points']} 个")
    print(f"  成本范围: {pareto_summary['cost_range'][0]} ~ {pareto_summary['cost_range'][1]} 元")
    print(f"  评分范围: {pareto_summary['rating_range'][0]} ~ {pareto_summary['rating_range'][1]}")
    print(f"  路程范围: {pareto_summary['distance_range'][0]} ~ {pareto_summary['distance_range'][1]} km")

    print(f"\n【论文图7-2 收敛曲线关键节点】")
    print(f"  {'代数':<8} {'HV均值':<10} {'可行率':<10} {'最优成本(元)'}")
    for r in convergence_results:
        cost_str = f"{r['avg_best_cost']:.1f}" if r['avg_best_cost'] is not None else "N/A"
        print(f"  {r['generations']:<8} {r['avg_hv']:<10.4f} {r['feasible_rate']*100:<10.1f}% {cost_str}")


if __name__ == "__main__":
    main()
