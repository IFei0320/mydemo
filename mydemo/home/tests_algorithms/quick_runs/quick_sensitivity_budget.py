# -*- coding: utf-8 -*-
"""预算敏感性（可行性 + 多样性）—— 单次运行。"""
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


def _collector(spots, days, budget, per_day, pop_size, generations, runs, seed_base):
    route_len = days * per_day
    hv_list, pareto_counts, feasible = [], [], 0
    for i in range(runs):
        random.seed(seed_base + i)
        pop = _build_population(spots, route_len, pop_size)
        _evaluate_population(pop, spots, per_day, budget)
        for _ in range(generations):
            fronts = _fast_non_dominated_sort(pop)
            for front in fronts:
                _crowding_distance(pop, front)
            offspring = []
            while len(offspring) < pop_size:
                p1, p2 = _tournament(pop), _tournament(pop)
                child = _mutate(_ordered_crossover(p1["route"], p2["route"]), len(spots))
                offspring.append({"route": child})
            _evaluate_population(offspring, spots, per_day, budget)
            pop = _next_generation(pop + offspring, pop_size)
        fea_items = [it for it in pop if it["feasible"]]
        pareto_counts.append(len(fea_items))
        if fea_items:
            feasible += 1
            fc = [it["metrics"]["cost"] for it in fea_items]
            nrs = [-it["metrics"]["rating"] for it in fea_items]
            c_min, c_max = min(fc), max(fc)
            nc = [(c - c_min) / (c_max - c_min) for c in fc] if c_max > c_min else [0.0] * len(fc)
            nr_min, nr_max = min(nrs), max(nrs)
            nn = [(n - nr_min) / (nr_max - nr_min) for n in nrs] if nr_max > nr_min else [0.0] * len(nrs)
            hv_list.append(_compute_hv(nc, nn))
        else:
            hv_list.append(0.0)
    return {"hv": mean(hv_list), "pareto_count": mean(pareto_counts), "feasible_rate": feasible / runs}


def collect_budget_sensitivity(spots, days=3, per_day=3, budgets=None, runs=3):
    if budgets is None:
        budgets = [400, 600, 800, 1000, 1200, 1500, 2000]
    results = []
    for b in budgets:
        print(f"   预算={b}元 ...")
        d = _collector(spots, days, b, per_day, 30, 30, runs, 400 + b)
        results.append({"budget": b, "feasible_rate": d["feasible_rate"],
                        "avg_pareto_count": d["pareto_count"], "avg_hv": d["hv"]})
    return results


def plot_budget_sensitivity_cn(results, output_path):
    budgets = [r["budget"] for r in results]
    feas_vals = [r["feasible_rate"] * 100 for r in results]
    pareto_vals = [r["avg_pareto_count"] for r in results]

    fig, ax = plt.subplots(figsize=(8, 5))
    ax2 = ax.twinx()
    ax.plot(budgets, feas_vals, marker="o", color="#43A047", linewidth=2, markersize=8, label="可行解比例")
    ax2.plot(budgets, pareto_vals, marker="D", color="#FB8C00", linewidth=2, markersize=7, linestyle="--", label="Pareto解数")
    ax.set_xlabel("预算（元）", fontsize=11)
    ax.set_ylabel("可行解比例 (%)", fontsize=11, color="#43A047")
    ax2.set_ylabel("平均 Pareto 解数", fontsize=11, color="#FB8C00")
    ax.set_title("预算约束对可行性与多样性的影响", fontsize=12, fontweight="bold")
    ax.grid(True, alpha=0.3)
    ax.set_ylim(0, 105)
    lines = ax.get_lines() + ax2.get_lines()
    ax.legend(lines, [l.get_label() for l in lines], fontsize=8, loc="center right")
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
    b_start = max(50, int(min9 - 20))
    b_end = int(budget * 2.2)
    step = max(10, int((b_end - b_start) / 14))
    budget_list = list(range(b_start, b_end + 1, step))
    print(f"   预算范围: {b_start}~{b_end}, 步长={step}, 共{len(budget_list)}个\n")
    print(">> 运行预算敏感性 ...")
    results = collect_budget_sensitivity(spots, budgets=budget_list, runs=3)
    save_json("预算敏感性数据", results)
    plot_budget_sensitivity_cn(results, OUTPUT_DIR / "预算敏感性图.svg")
    print("完成。")


if __name__ == "__main__":
    main()
