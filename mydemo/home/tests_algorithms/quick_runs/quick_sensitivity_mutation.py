# -*- coding: utf-8 -*-
"""突变率敏感性 —— 单次运行。"""
import random
import time
from statistics import mean
import numpy as np
import matplotlib.pyplot as plt
from _base import *
from home.nsga2_trip_planner import (
    _build_population, _evaluate_population, _fast_non_dominated_sort,
    _crowding_distance, _tournament, _ordered_crossover, _mutate, _next_generation,
)


def _compute_hv(costs, neg_ratings):
    points = sorted(zip(costs, neg_ratings), key=lambda p: p[0])
    hv = 0.0
    prev_f2 = 1.0
    for f1, f2 in points:
        if 0.0 <= f1 <= 1.0 and 0.0 <= f2 <= 1.0:
            hv += (1.0 - f1) * (prev_f2 - f2)
            prev_f2 = f2
    return max(0.0, min(1.0, hv))


def _collector(spots, days, budget, per_day, pop_size, generations, mutation_rate, runs, seed_base):
    route_len = days * per_day
    hv_list, rt_list, pareto_counts = [], [], []
    feasible_runs = 0
    for i in range(runs):
        random.seed(seed_base + i)
        start = time.perf_counter()
        pop = _build_population(spots, route_len, pop_size)
        _evaluate_population(pop, spots, per_day, budget)
        for _ in range(generations):
            fronts = _fast_non_dominated_sort(pop)
            for front in fronts:
                _crowding_distance(pop, front)
            offspring = []
            while len(offspring) < pop_size:
                p1, p2 = _tournament(pop), _tournament(pop)
                child = _mutate(_ordered_crossover(p1["route"], p2["route"]),
                                len(spots), mutation_rate=mutation_rate)
                offspring.append({"route": child})
            _evaluate_population(offspring, spots, per_day, budget)
            pop = _next_generation(pop + offspring, pop_size)
        rt_list.append(time.perf_counter() - start)
        fea_items = [it for it in pop if it["feasible"]]
        pareto_counts.append(len(fea_items))
        if fea_items:
            feasible_runs += 1
            fc = [it["metrics"]["cost"] for it in fea_items]
            nrs = [-it["metrics"]["rating"] for it in fea_items]
            c_min, c_max = min(fc), max(fc)
            nc = [(c - c_min) / (c_max - c_min) for c in fc] if c_max > c_min else [0.0] * len(fc)
            nr_min, nr_max = min(nrs), max(nrs)
            nn = [(n - nr_min) / (nr_max - nr_min) for n in nrs] if nr_max > nr_min else [0.0] * len(nrs)
            hv_list.append(_compute_hv(nc, nn))
        else:
            hv_list.append(0.0)
    return {
        "avg_hv": mean(hv_list),
        "avg_runtime": mean(rt_list),
        "feasible_rate": feasible_runs / runs,
        "avg_pareto_count": mean(pareto_counts),
    }


def collect_mutation_sensitivity(spots, budget=280, days=3, per_day=3,
                                 mutation_rates=None, runs=5):
    if mutation_rates is None:
        mutation_rates = [0.05, 0.1, 0.2, 0.3, 0.4, 0.5]
    results = []
    for mr in mutation_rates:
        print(f"   突变率={mr} ...")
        d = _collector(spots, days, budget, per_day, 40, 30, mr, runs, 900 + int(mr * 100))
        results.append({
            "mutation_rate": mr,
            "avg_hv": round(d["avg_hv"], 6),
            "feasible_rate": round(d["feasible_rate"], 4),
            "avg_pareto_count": round(d["avg_pareto_count"], 2),
            "avg_runtime": round(d["avg_runtime"], 4),
        })
    return results


def plot_mutation_sensitivity_cn(results, output_path):
    rates = [r["mutation_rate"] for r in results]
    hv_vals = [r["avg_hv"] for r in results]
    feas_vals = [r["feasible_rate"] * 100 for r in results]
    pareto_vals = [r["avg_pareto_count"] for r in results]

    fig, ax = plt.subplots(figsize=(8, 5))
    ax2 = ax.twinx()

    line1, = ax.plot(rates, hv_vals, marker="o", color="#1565C0", linewidth=2, markersize=8, label="HV")
    line2, = ax2.plot(rates, feas_vals, marker="s", color="#2E7D32", linewidth=2,
                      markersize=7, linestyle="--", label="可行解比例 (%)")

    # 标注当前的 0.2
    idx02 = rates.index(0.2)
    ax.axvline(x=0.2, color="gray", linestyle=":", linewidth=1.2, alpha=0.7)
    ax.annotate(
        f"当前值=0.2\nHV={hv_vals[idx02]:.4f}\n可行率={feas_vals[idx02]:.0f}%\nPareto={pareto_vals[idx02]:.1f}个",
        xy=(0.2, hv_vals[idx02]),
        xytext=(0.28, hv_vals[idx02] - 0.04),
        fontsize=9, fontweight="bold",
        arrowprops=dict(arrowstyle="->", color="gray", lw=1.2),
        bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.85),
    )

    # 标注 HV 最高点
    best_idx = hv_vals.index(max(hv_vals))
    ax.scatter([rates[best_idx]], [hv_vals[best_idx]], s=120, color="#E53935",
               edgecolors="white", linewidth=2, zorder=5)

    ax.set_xlabel("突变率", fontsize=11)
    ax.set_ylabel("超体积 (HV)", fontsize=11, color="#1565C0")
    ax2.set_ylabel("可行解比例 (%)", fontsize=11, color="#2E7D32")
    ax.set_title("突变率对求解质量与可行性的影响", fontsize=12, fontweight="bold")
    ax.grid(True, alpha=0.3)
    if hv_vals:
        ax.set_ylim(0, max(hv_vals) * 1.15)
    ax2.set_ylim(0, 105)

    lines = [line1, line2]
    ax.legend(lines, [l.get_label() for l in lines], fontsize=9, loc="lower right")
    fig.tight_layout()
    fig.savefig(output_path, format="svg", bbox_inches="tight")
    plt.close(fig)
    print(f"   图表已保存 -> {output_path}")


def main():
    print("加载景点数据 ...")
    spots = load_spots()
    costs = sorted(s.cost for s in spots)
    min9 = sum(costs[:9])
    budget = max(280, min9 + 50)
    print(f"   {len(spots)} 个收费景点, 预算={budget}元\n")
    print(">> 运行突变率敏感性 (pop=40, gen=30, 各5轮) ...")
    results = collect_mutation_sensitivity(spots, budget=budget, runs=5)
    save_json("突变率敏感性数据", results)
    plot_mutation_sensitivity_cn(results, OUTPUT_DIR / "突变率敏感性图.svg")

    print("\n────────── 汇总 ──────────")
    best = max(results, key=lambda r: r["avg_hv"])
    current = next(r for r in results if r["mutation_rate"] == 0.2)
    print(f"  HV 最高: 突变率={best['mutation_rate']}, HV={best['avg_hv']:.4f}")
    print(f"  0.2 当前: HV={current['avg_hv']:.4f}, 可行率={current['feasible_rate']*100:.0f}%")
    if best["mutation_rate"] == 0.2:
        print("  结论: 0.2 即为最优 ✓")
    else:
        print(f"  结论: 最优为 {best['mutation_rate']}, 与当前 0.2 有差异")
    print("完成。")


if __name__ == "__main__":
    main()
