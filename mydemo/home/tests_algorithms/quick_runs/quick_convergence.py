# -*- coding: utf-8 -*-
"""收敛曲线（超体积 + 可行性 双子图）—— 单次运行。"""
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


def collect_convergence(spots, days=3, budget=280, per_day=3, pop_size=40, runs=5):
    gen_steps = [1, 2, 5, 10, 15, 20, 25, 30, 40, 50]
    max_gen = max(gen_steps)
    step_set = set(gen_steps)
    route_len = days * per_day
    all_snapshots = {g: {"hv": [], "feasible": 0, "min_cost": []} for g in gen_steps}

    for run_i in range(runs):
        random.seed(700 + run_i)
        pop = _build_population(spots, route_len, pop_size)
        _evaluate_population(pop, spots, per_day, budget)
        for gen in range(1, max_gen + 1):
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
            if gen in step_set:
                feasible = [it for it in pop if it["feasible"]]
                if feasible:
                    fc = [it["metrics"]["cost"] for it in feasible]
                    fr = [it["metrics"]["rating"] for it in feasible]
                    nrs = [-r for r in fr]
                    c_min, c_max = min(fc), max(fc)
                    if c_max > c_min:
                        nc = [(c - c_min) / (c_max - c_min) for c in fc]
                    else:
                        nc = [0.0] * len(fc)
                    nr_min, nr_max = min(nrs), max(nrs)
                    if nr_max > nr_min:
                        nn = [(n - nr_min) / (nr_max - nr_min) for n in nrs]
                    else:
                        nn = [0.0] * len(nrs)
                    all_snapshots[gen]["hv"].append(_compute_hv(nc, nn))
                    all_snapshots[gen]["min_cost"].append(min(fc))
                    all_snapshots[gen]["feasible"] += 1
                else:
                    all_snapshots[gen]["hv"].append(0.0)
                    all_snapshots[gen]["min_cost"].append(float("inf"))

    results = []
    for gen in gen_steps:
        snap = all_snapshots[gen]
        valid = [c for c in snap["min_cost"] if c < float("inf")]
        results.append({
            "generations": gen,
            "avg_hv": mean(snap["hv"]) if snap["hv"] else 0.0,
            "feasible_rate": snap["feasible"] / runs,
            "avg_best_cost": mean(valid) if valid else None,
        })
    return results


def plot_convergence_cn(results, output_path):
    generations = [r["generations"] for r in results]
    hv_vals = [r["avg_hv"] for r in results]
    feasible_rates = [r["feasible_rate"] * 100 for r in results]
    best_costs = [r["avg_best_cost"] for r in results]

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    ax1 = axes[0]
    ax1.plot(generations, hv_vals, marker="o", color="#1565C0", linewidth=1.5, markersize=5, alpha=0.6, label="原始值")
    if len(hv_vals) >= 3:
        w = min(3, len(hv_vals))
        smoothed = np.convolve(hv_vals, np.ones(w) / w, mode='valid')
        ax1.plot(generations[w - 1:], smoothed, color="#0D47A1", linewidth=2.5, label="趋势线")
    ax1.set_xlabel("进化代数", fontsize=10)
    ax1.set_ylabel("超体积 (HV)", fontsize=10)
    ax1.set_title("(a) 超体积指标收敛", fontsize=11, fontweight="bold")
    ax1.grid(True, alpha=0.3)
    if hv_vals:
        ax1.set_ylim(0, max(hv_vals) * 1.1)
    ax1.legend(fontsize=8, loc="lower right")

    ax2 = axes[1]
    valid = [(g, c, f) for g, c, f in zip(generations, best_costs, feasible_rates) if c is not None]
    vg, vc, vf = [d[0] for d in valid], [d[1] for d in valid], [d[2] for d in valid]
    line1 = ax2.plot(vg, vc, marker="o", color="#E53935", linewidth=2, markersize=6, label="平均最优成本")
    ax2.set_xlabel("进化代数", fontsize=10)
    ax2.set_ylabel("平均最优成本（元）", fontsize=10, color="#E53935")
    if vc:
        ax2.set_ylim(min(vc) * 0.92, max(vc) * 1.05)
    ax3 = ax2.twinx()
    line2 = ax3.plot(vg, vf, marker="s", color="#2E7D32", linewidth=2, markersize=6, label="可行解比例")
    ax3.set_ylabel("可行解比例 (%)", fontsize=10, color="#2E7D32")
    ax2.set_title("(b) 求解质量与可行性收敛", fontsize=11, fontweight="bold")
    lines = line1 + line2
    ax2.legend(lines, [l.get_label() for l in lines], fontsize=8, loc="center right")
    ax2.grid(True, alpha=0.3)
    ax3.set_ylim(0, 105)
    fig.suptitle("NSGA-II 收敛性分析", fontsize=13, fontweight="bold")
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
    print(f"   {len(spots)} 个收费景点, 预算={budget}元")
    print(">> 运行收敛性分析（5轮）...")
    results = collect_convergence(spots, budget=budget, runs=5)
    save_json("收敛曲线数据", results)
    plot_convergence_cn(results, OUTPUT_DIR / "收敛曲线图.svg")
    print("完成。")


if __name__ == "__main__":
    main()
