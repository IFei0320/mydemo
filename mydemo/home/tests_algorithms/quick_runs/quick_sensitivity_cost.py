# -*- coding: utf-8 -*-
"""预算-成本匹配关系 —— 单次运行。"""
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


def _collector(spots, days, budget, per_day, pop_size, generations, runs, seed_base):
    route_len = days * per_day
    cost_list = []
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
        fea = [it["metrics"]["cost"] for it in pop if it["feasible"]]
        cost_list.append(min(fea) if fea else float("inf"))
    valid = [c for c in cost_list if c < float("inf")]
    return mean(valid) if valid else None


def collect_budget_cost(spots, days=3, per_day=3, budgets=None, runs=3):
    if budgets is None:
        budgets = [400, 600, 800, 1000, 1200, 1500, 2000]
    results = []
    for b in budgets:
        print(f"   预算={b}元 ...")
        avg_cost = _collector(spots, days, b, per_day, 30, 30, runs, 400 + b)
        results.append({"budget": b, "avg_best_cost": avg_cost})
    return results


def plot_budget_cost_cn(results, output_path):
    valid = [(r["budget"], r["avg_best_cost"]) for r in results if r["avg_best_cost"] is not None]
    if not valid:
        print("   无有效数据，跳过")
        return
    budgets, costs = zip(*valid)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(budgets, costs, marker="s", color="#1E88E5", linewidth=2, markersize=8, label="实际成本")
    if budgets:
        ax.plot([min(budgets), max(budgets)], [min(budgets), max(budgets)], 'k--', alpha=0.3, linewidth=1, label="预算线")
    ax.set_xlabel("预算（元）", fontsize=11)
    ax.set_ylabel("路线平均成本（元）", fontsize=11)
    ax.set_title("预算与实际成本的匹配关系", fontsize=12, fontweight="bold")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=9, loc="upper left")
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
    print(">> 运行预算-成本匹配分析 ...")
    results = collect_budget_cost(spots, budgets=budget_list, runs=3)
    save_json("预算成本匹配数据", results)
    plot_budget_cost_cn(results, OUTPUT_DIR / "预算成本匹配图.svg")
    print("完成。")


if __name__ == "__main__":
    main()
