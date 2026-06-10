# -*- coding: utf-8 -*-
"""Pareto前沿（成本-评分 + 成本-路程 双子图）—— 单次运行。"""
from statistics import mean as _mean
import numpy as np
import matplotlib.pyplot as plt
from _base import *


def collect_pareto(spots, days=3, budget=280, per_day=3):
    import random
    random.seed(42)
    pareto_set, _ = run_nsga2(spots, days=days, budget=budget, per_day=per_day,
                              pop_size=40, generations=50)
    feasible = [it for it in pareto_set if it["feasible"]]
    return [{"cost": it["metrics"]["cost"],
             "distance": it["metrics"]["distance"],
             "rating": it["metrics"]["rating"],
             "hotness": it["metrics"]["hotness"]} for it in feasible]


def plot_pareto_cn(results, output_path):
    costs = [p["cost"] for p in results]
    ratings = [p["rating"] for p in results]
    distances = [p["distance"] for p in results]

    pairs = list(zip(costs, ratings))
    econ_idx = min(range(len(pairs)), key=lambda i: pairs[i][0])
    exp_idx = max(range(len(pairs)), key=lambda i: pairs[i][1])
    bal_idx = econ_idx
    max_d = 0.0
    e1, e2 = pairs[econ_idx], pairs[exp_idx]
    if abs(e2[0] - e1[0]) > 1e-6:
        for i, (c, r) in enumerate(pairs):
            d = abs((e2[1] - e1[1]) * c - (e2[0] - e1[0]) * r + e2[0] * e1[1] - e2[1] * e1[0]) / \
                ((e2[1] - e1[1]) ** 2 + (e2[0] - e1[0]) ** 2) ** 0.5
            if d > max_d:
                max_d, bal_idx = d, i

    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    special = [(econ_idx, "economy", "省钱型"), (bal_idx, "balanced", "均衡型"), (exp_idx, "experience", "体验型")]

    for ax_i, (ax, ys, ylabel) in enumerate([
        (axes[0], ratings, "平均评分"),
        (axes[1], distances, "总路程（km）"),
    ]):
        ax.scatter(costs, ys, s=60, color="#BDBDBD", edgecolors="#757575", alpha=0.6)
        for idx, style, label in special:
            x, y = costs[idx], ys[idx]
            ax.scatter([x], [y], s=180, color=COLORS[style], edgecolors="white", linewidth=2, zorder=5)
            if ax_i == 0:
                ax.annotate(f"{label}\n({x:.0f}元, {y:.2f}分)", xy=(x, y),
                            xytext=(15, 10 if style != "economy" else -20),
                            textcoords="offset points", fontsize=9, fontweight="bold",
                            color=COLORS[style],
                            arrowprops=dict(arrowstyle="->", color=COLORS[style], lw=1.2),
                            bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.85))
        ax.set_xlabel("总成本（元）", fontsize=10)
        ax.set_ylabel(ylabel, fontsize=10)
        ax.grid(True, alpha=0.3)
        if ys:
            margin = (max(ys) - min(ys)) * 0.15
            ax.set_ylim(min(ys) - margin, max(ys) + margin)

    axes[0].set_title("(a) 成本-评分 Pareto前沿", fontsize=11, fontweight="bold")
    axes[1].set_title("(b) 成本-路程权衡", fontsize=11, fontweight="bold")
    fig.suptitle("NSGA-II Pareto 前沿分析", fontsize=13, fontweight="bold")
    fig.tight_layout()
    fig.savefig(output_path, format="svg", bbox_inches="tight")
    plt.close(fig)
    print(f"   图表已保存 -> {output_path}")


def main():
    print("加载景点数据 ...")
    spots = load_spots()
    costs = sorted(s.cost for s in spots)
    route_len = 9
    min9 = sum(costs[:route_len])
    budget = max(280, min9 + 50)
    print(f"   {len(spots)} 个收费景点, 预算={budget}元\n")

    print(">> 运行 NSGA-II（1轮）...")
    pareto = collect_pareto(spots, budget=budget)
    print(f"   Pareto 可行解: {len(pareto)} 个")

    summary = {
        "total_points": len(pareto),
        "cost_range": [round(min(p["cost"] for p in pareto), 2),
                       round(max(p["cost"] for p in pareto), 2)],
        "rating_range": [round(min(p["rating"] for p in pareto), 3),
                         round(max(p["rating"] for p in pareto), 3)],
        "distance_range": [round(min(p["distance"] for p in pareto), 1),
                           round(max(p["distance"] for p in pareto), 1)],
        "points": [{"cost": round(p["cost"], 2), "rating": round(p["rating"], 3),
                    "distance": round(p["distance"], 1), "hotness": round(p["hotness"], 3)}
                   for p in pareto],
    }
    save_json("Pareto前沿数据", summary)
    plot_pareto_cn(pareto, OUTPUT_DIR / "Pareto前沿图.svg")
    print("完成。")


if __name__ == "__main__":
    main()
