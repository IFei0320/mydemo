# -*- coding: utf-8 -*-
"""算法对比（NSGA-II / Greedy / Random 五维子图）—— 单次运行。"""
import random
import time
from statistics import mean
import matplotlib.pyplot as plt
from _base import *
from home.nsga2_trip_planner import (
    _build_population, _evaluate_population, _fast_non_dominated_sort,
    _crowding_distance, _tournament, _ordered_crossover, _mutate, _next_generation,
    _evaluate_route,
)


def _run_nsga2_once(spots, days, budget, per_day, pop_size, generations, seed):
    route_len = days * per_day
    random.seed(seed)
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
    feasible = [it for it in pop if it["feasible"]]
    costs = [it["metrics"]["cost"] for it in feasible]
    ratings = [it["metrics"]["rating"] for it in feasible]
    if ratings:
        best = max(range(len(ratings)), key=lambda j: ratings[j] * 10 - costs[j] / 100)
        return feasible[best]["metrics"], len(feasible)
    return {"cost": float("inf"), "distance": float("inf"), "rating": 0.0, "hotness": 0.0}, 0


def _greedy(spots, route_len, budget, per_day):
    ranked = sorted(range(len(spots)), key=lambda i: (-spots[i].rating, -spots[i].hotness, spots[i].cost))
    sel, total = [], 0.0
    for i in ranked:
        if len(sel) >= route_len:
            break
        if total + spots[i].cost <= budget:
            sel.append(i)
            total += spots[i].cost
    m = _evaluate_route(sel, spots, per_day=per_day)
    return m


def _random_best(spots, route_len, budget, per_day, trials=1000, seed=0):
    rng = random.Random(seed)
    cand = list(range(len(spots)))
    best_m, best_f = None, False
    for _ in range(trials):
        route = rng.sample(cand, route_len)
        m = _evaluate_route(route, spots, per_day=per_day)
        f = m["cost"] <= budget
        if best_m is None or (f and not best_f) or (f == best_f and m["cost"] < best_m["cost"]):
            best_m, best_f = m, f
    return best_m


def collect_comparison(spots, days=3, budget=280, per_day=3, runs=3):
    route_len = days * per_day
    result = {}
    for algo, fn in [("NSGA-II", lambda s: _run_nsga2_once(spots, days, budget, per_day, 40, 50, 100 + s)),
                     ("贪心算法", None), ("随机算法", None)]:
        costs, dists, rats, hots, rts, pcs = [], [], [], [], [], []
        fea = 0
        for i in range(runs):
            start = time.perf_counter()
            if algo == "NSGA-II":
                m, pc = fn(i)
                pcs.append(pc)
            elif algo == "贪心算法":
                random.seed(200 + i)
                m = _greedy(spots, route_len, budget, per_day)
                pcs.append(1)
            else:
                m = _random_best(spots, route_len, budget, per_day, 1000, 300 + i)
                pcs.append(1)
            rts.append(time.perf_counter() - start)
            costs.append(m["cost"])
            dists.append(m["distance"])
            rats.append(m["rating"])
            hots.append(m["hotness"])
            if m["cost"] <= budget:
                fea += 1
        result[algo] = {"costs": costs, "distances": dists, "ratings": rats,
                        "hotnesses": hots, "runtimes": rts, "pareto_counts": pcs,
                        "feasible_rate": fea / runs}
    return result


def plot_comparison_cn(results, output_path):
    labels = list(results.keys())
    metrics = [("avg_cost", "总成本", "元"), ("avg_distance", "总路程", "km"),
               ("avg_rating", "平均评分", ""), ("avg_hotness", "平均热度", ""),
               ("avg_runtime", "运行时间", "秒")]
    fig = plt.figure(figsize=(16, 9))
    gs = fig.add_gridspec(2, 3, hspace=0.3, wspace=0.3)
    axes = [fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1]), fig.add_subplot(gs[0, 2]),
            fig.add_subplot(gs[1, 0]), fig.add_subplot(gs[1, 1])]
    colors = [COLORS["nsga2"], COLORS["greedy"], COLORS["random"]]

    for idx, (key, title, unit) in enumerate(metrics):
        ax = axes[idx]
        if key == "avg_cost":
            vals = [mean(results[name]["costs"]) for name in labels]
            ax.bar(labels, vals, color=colors, edgecolor="white", linewidth=0.5)
            ax.set_yscale('log')
            ax.set_ylabel(unit + " (对数)", fontsize=9)
            for i, v in enumerate(vals):
                ax.text(i, v * 1.15, f"{v:.0f}", ha="center", fontsize=8)
        elif key == "avg_distance":
            vals = [mean(results[name]["distances"]) for name in labels]
            ax.bar(labels, vals, color=colors, edgecolor="white", linewidth=0.5)
            ax.set_ylabel(unit, fontsize=9)
            for i, v in enumerate(vals):
                ax.text(i, v + max(vals) * 0.02, f"{v:.0f}", ha="center", fontsize=8)
        elif key == "avg_rating":
            vals = [mean(results[name]["ratings"]) for name in labels]
            ax.bar(labels, vals, color=colors, edgecolor="white", linewidth=0.5)
            ax.set_ylim(min(vals) * 0.95, max(vals) * 1.02)
            ax.set_ylabel(unit, fontsize=9)
            for i, v in enumerate(vals):
                ax.text(i, v + (max(vals) - min(vals)) * 0.01, f"{v:.2f}", ha="center", fontsize=8)
        elif key == "avg_hotness":
            vals = [mean(results[name]["hotnesses"]) for name in labels]
            ax.bar(labels, vals, color=colors, edgecolor="white", linewidth=0.5)
            ax.set_ylabel(unit, fontsize=9)
            for i, v in enumerate(vals):
                ax.text(i, v + max(vals) * 0.02, f"{v:.2f}", ha="center", fontsize=8)
        else:
            vals = [mean(results[name]["runtimes"]) for name in labels]
            ax.bar(labels, vals, color=colors, edgecolor="white", linewidth=0.5)
            ax.set_ylabel(unit, fontsize=9)
            for i, v in enumerate(vals):
                ax.text(i, v + max(vals) * 0.02, f"{v:.3f}", ha="center", fontsize=8)
        ax.set_title(title, fontsize=11, fontweight="bold")

    fig.suptitle("NSGA-II 与基线算法多维对比", fontsize=13, fontweight="bold")
    plt.tight_layout()
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

    print(">> 运行算法对比（NSGA-II/贪心/随机 各3轮）...")
    result = collect_comparison(spots, budget=budget, runs=3)

    summary = {}
    for name in result:
        m = result[name]
        summary[name] = {
            "avg_cost": round(mean(m["costs"]), 2),
            "avg_distance": round(mean(m["distances"]), 1),
            "avg_rating": round(mean(m["ratings"]), 2),
            "avg_hotness": round(mean(m["hotnesses"]), 2),
            "avg_runtime_s": round(mean(m["runtimes"]), 4),
            "avg_pareto_count": round(mean(m["pareto_counts"]), 1),
            "feasible_rate_pct": round(m["feasible_rate"] * 100, 1),
            "raw_costs": [round(v, 2) for v in m["costs"]],
            "raw_distances": [round(v, 1) for v in m["distances"]],
            "raw_ratings": [round(v, 3) for v in m["ratings"]],
            "raw_hotnesses": [round(v, 3) for v in m["hotnesses"]],
            "raw_runtimes": [round(v, 4) for v in m["runtimes"]],
        }
    save_json("算法对比数据", summary)
    plot_comparison_cn(result, OUTPUT_DIR / "算法对比图.svg")
    print("完成。")


if __name__ == "__main__":
    main()
