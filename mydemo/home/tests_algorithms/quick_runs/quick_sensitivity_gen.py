# -*- coding: utf-8 -*-
"""代数敏感性 —— 单次运行。"""
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


def _normalize_3d(values):
    v_min, v_max = min(values), max(values)
    if v_max <= v_min:
        return [0.0 for _ in values]
    return [(v - v_min) / (v_max - v_min) for v in values]


def _compute_hv_3d(costs, neg_ratings, distances, n_samples=20000):
    if len(costs) == 0:
        return 0.0
    points = np.column_stack([costs, neg_ratings, distances])
    rng = np.random.RandomState(42)
    samples = rng.uniform(0, 1, (n_samples, 3))
    dominated = np.any(np.all(samples[:, None, :] >= points[None, :, :], axis=2), axis=1)
    return float(dominated.mean())


def _collector(spots, days, budget, per_day, pop_size, generations, runs, seed_base):
    route_len = days * per_day
    hv_list, rt_list, feasible = [], [], 0
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
                child = _mutate(_ordered_crossover(p1["route"], p2["route"]), len(spots))
                offspring.append({"route": child})
            _evaluate_population(offspring, spots, per_day, budget)
            pop = _next_generation(pop + offspring, pop_size)
        rt_list.append(time.perf_counter() - start)
        fea_items = [it for it in pop if it["feasible"]]
        if fea_items:
            feasible += 1
            fc = [it["metrics"]["cost"] for it in fea_items]
            nrs = [-it["metrics"]["rating"] for it in fea_items]
            fd = [it["metrics"]["distance"] for it in fea_items]
            nc = _normalize_3d(fc)
            nn = _normalize_3d(nrs)
            nd = _normalize_3d(fd)
            hv_list.append(_compute_hv_3d(nc, nn, nd))
        else:
            hv_list.append(0.0)
    return {"hv": mean(hv_list), "hv_list": hv_list, "runtime": mean(rt_list),
            "rt_list": rt_list, "feasible_rate": feasible / runs}


def collect_gen_sensitivity(spots, budget=280, days=3, per_day=3, gen_steps=None, runs=3):
    if gen_steps is None:
        gen_steps = [5, 10, 15, 20, 30, 40, 50, 70, 100]
    results = []
    for gen in gen_steps:
        print(f"   代数={gen} ...")
        d = _collector(spots, days, budget, per_day, 40, gen, runs, 600 + gen)
        results.append({"generations": gen, "avg_hv": d["hv"], "feasible_rate": d["feasible_rate"],
                        "avg_runtime": d["runtime"],
                        "std_hv": float(np.std(d["hv_list"])) if len(d["hv_list"]) > 1 else 0.0,
                        "std_runtime": float(np.std(d["rt_list"])) if len(d["rt_list"]) > 1 else 0.0})
    return results


def plot_gen_sensitivity_cn(results, output_path):
    gen_steps = [r["generations"] for r in results]
    hv_vals = [r["avg_hv"] for r in results]
    feas_vals = [r["feasible_rate"] * 100 for r in results]

    fig, ax = plt.subplots(figsize=(8, 5))
    ax2 = ax.twinx()
    ax.plot(gen_steps, hv_vals, marker="o", color="#1565C0", linewidth=1.5, markersize=6, alpha=0.6)
    if len(hv_vals) >= 3:
        w = min(3, len(hv_vals))
        smoothed = np.convolve(hv_vals, np.ones(w) / w, mode='valid')
        ax.plot(gen_steps[w - 1:], smoothed, color="#0D47A1", linewidth=2.5, label="HV趋势")
    ax2.plot(gen_steps, feas_vals, marker="s", color="#2E7D32", linewidth=2, markersize=8, linestyle="--", label="可行解比例")
    if 50 in gen_steps:
        idx = gen_steps.index(50)
        ax.axvline(x=50, color="gray", linestyle=":", linewidth=1.2, alpha=0.7)
        ax.annotate(f"选取gen=50\nHV={hv_vals[idx]:.3f}\n可行率={feas_vals[idx]:.0f}%",
                    xy=(50, hv_vals[idx]), xytext=(60, hv_vals[idx] - 0.05),
                    fontsize=9, fontweight="bold",
                    arrowprops=dict(arrowstyle="->", color="gray", lw=1.2))
    ax.set_xlabel("进化代数", fontsize=11)
    ax.set_ylabel("超体积 (HV)", fontsize=11, color="#1565C0")
    ax2.set_ylabel("可行解比例 (%)", fontsize=11, color="#2E7D32")
    ax.set_title("进化代数对收敛性与可行性的影响", fontsize=12, fontweight="bold")
    ax.grid(True, alpha=0.3)
    if hv_vals:
        ax.set_ylim(0, max(hv_vals) * 1.1)
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
    print(">> 运行代数敏感性 ...")
    results = collect_gen_sensitivity(spots, budget=budget, runs=3)
    save_json("代数敏感性数据", results)
    plot_gen_sensitivity_cn(results, OUTPUT_DIR / "代数敏感性图.svg")
    print("完成。")


if __name__ == "__main__":
    main()
