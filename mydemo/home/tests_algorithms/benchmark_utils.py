import random
import time
from statistics import mean

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np

from home.nsga2_trip_planner import _evaluate_route, run_nsga2
from home.tests_algorithms.benchmark_fixtures import benchmark_spots


_FONT_PRIORITY = ["Microsoft YaHei", "SimHei", "STXihei", "SimSun"]
_available_cjk_fonts = [name for name in _FONT_PRIORITY if any(f.name == name for f in fm.fontManager.ttflist)]
if _available_cjk_fonts:
    plt.rcParams["font.sans-serif"] = _available_cjk_fonts + list(plt.rcParams.get("font.sans-serif", []))
plt.rcParams["axes.unicode_minus"] = False


def greedy_baseline(spots, route_len, budget, per_day=3):
    ranked = sorted(
        range(len(spots)),
        key=lambda idx: (-spots[idx].rating, -spots[idx].hotness, spots[idx].cost),
    )
    selected = []
    total_cost = 0.0
    for idx in ranked:
        spot = spots[idx]
        if len(selected) >= route_len:
            break
        if total_cost + spot.cost > budget:
            continue
        selected.append(idx)
        total_cost += spot.cost

    if len(selected) < route_len:
        for idx in ranked:
            if idx in selected:
                continue
            selected.append(idx)
            if len(selected) >= route_len:
                break

    metrics = _evaluate_route(selected, spots, per_day=per_day)
    return {
        "route": selected,
        "metrics": metrics,
        "feasible": metrics["cost"] <= budget,
    }


def random_baseline(spots, route_len, budget, per_day=3, trials=120, seed=0):
    rng = random.Random(seed)
    candidates = list(range(len(spots)))
    best = None
    for _ in range(trials):
        route = rng.sample(candidates, route_len)
        metrics = _evaluate_route(route, spots, per_day=per_day)
        feasible = metrics["cost"] <= budget
        item = {"route": route, "metrics": metrics, "feasible": feasible}
        if not best:
            best = item
            continue
        if feasible and not best["feasible"]:
            best = item
            continue
        if feasible == best["feasible"] and metrics["cost"] < best["metrics"]["cost"]:
            best = item
    return best


def collect_algorithm_comparison(days=2, budget=300, per_day=3, pop_size=18, generations=12, runs=8):
    spots = benchmark_spots()
    route_len = days * per_day
    nsga_costs = []
    nsga_times = []
    nsga_solution_counts = []
    nsga_feasible = []

    greedy_costs = []
    greedy_times = []
    greedy_feasible = []

    random_costs = []
    random_times = []
    random_feasible = []

    for i in range(runs):
        start = time.perf_counter()
        random.seed(100 + i)
        pareto_set, _ = run_nsga2(
            spots,
            days=days,
            budget=budget,
            per_day=per_day,
            pop_size=pop_size,
            generations=generations,
        )
        nsga_times.append(time.perf_counter() - start)
        feasible_nsga = [item for item in pareto_set if item["feasible"]]
        nsga_feasible.append(1 if feasible_nsga else 0)
        nsga_solution_counts.append(len(feasible_nsga))
        nsga_costs.append(min(item["metrics"]["cost"] for item in feasible_nsga) if feasible_nsga else float("inf"))

        start = time.perf_counter()
        greedy = greedy_baseline(spots, route_len, budget, per_day=per_day)
        greedy_times.append(time.perf_counter() - start)
        greedy_feasible.append(1 if greedy["feasible"] else 0)
        greedy_costs.append(greedy["metrics"]["cost"])

        start = time.perf_counter()
        random_sol = random_baseline(spots, route_len, budget, per_day=per_day, trials=120, seed=200 + i)
        random_times.append(time.perf_counter() - start)
        random_feasible.append(1 if random_sol["feasible"] else 0)
        random_costs.append(random_sol["metrics"]["cost"])

    return {
        "NSGA-II": {
            "avg_best_cost": mean(nsga_costs),
            "avg_runtime": mean(nsga_times),
            "avg_solution_count": mean(nsga_solution_counts),
            "feasible_rate": mean(nsga_feasible),
        },
        "Greedy": {
            "avg_best_cost": mean(greedy_costs),
            "avg_runtime": mean(greedy_times),
            "avg_solution_count": 1.0,
            "feasible_rate": mean(greedy_feasible),
        },
        "Random": {
            "avg_best_cost": mean(random_costs),
            "avg_runtime": mean(random_times),
            "avg_solution_count": 1.0,
            "feasible_rate": mean(random_feasible),
        },
    }


def collect_budget_sensitivity(budgets, days=2, per_day=3, pop_size=18, generations=12, runs=6):
    spots = benchmark_spots()
    results = []
    for budget in budgets:
        feasible_rates = []
        best_costs = []
        for i in range(runs):
            random.seed(300 + i + int(budget))
            pareto_set, _ = run_nsga2(
                spots,
                days=days,
                budget=budget,
                per_day=per_day,
                pop_size=pop_size,
                generations=generations,
            )
            feasible = [item for item in pareto_set if item["feasible"]]
            feasible_rates.append(1 if feasible else 0)
            if feasible:
                best_costs.append(min(item["metrics"]["cost"] for item in feasible))
        results.append(
            {
                "budget": budget,
                "feasible_rate": mean(feasible_rates),
                "avg_best_cost": mean(best_costs) if best_costs else np.nan,
            }
        )
    return results


def collect_population_sensitivity(pop_sizes, budget=300, days=2, per_day=3, generations=12, runs=6):
    spots = benchmark_spots()
    results = []
    for pop_size in pop_sizes:
        best_costs = []
        runtimes = []
        solution_counts = []
        for i in range(runs):
            start = time.perf_counter()
            random.seed(500 + i + pop_size)
            pareto_set, _ = run_nsga2(
                spots,
                days=days,
                budget=budget,
                per_day=per_day,
                pop_size=pop_size,
                generations=generations,
            )
            runtimes.append(time.perf_counter() - start)
            feasible = [item for item in pareto_set if item["feasible"]]
            if feasible:
                best_costs.append(min(item["metrics"]["cost"] for item in feasible))
                solution_counts.append(len(feasible))
        results.append(
            {
                "pop_size": pop_size,
                "avg_best_cost": mean(best_costs) if best_costs else np.nan,
                "avg_runtime": mean(runtimes),
                "avg_solution_count": mean(solution_counts) if solution_counts else 0.0,
            }
        )
    return results


def collect_convergence_curve(days=2, budget=300, per_day=3, pop_size=18, generation_steps=None, runs=5):
    if generation_steps is None:
        generation_steps = [2, 4, 6, 8, 10, 12, 16, 20]
    spots = benchmark_spots()
    results = []
    for generations in generation_steps:
        best_costs = []
        solution_counts = []
        runtimes = []
        for i in range(runs):
            start = time.perf_counter()
            random.seed(700 + i + generations)
            pareto_set, _ = run_nsga2(
                spots,
                days=days,
                budget=budget,
                per_day=per_day,
                pop_size=pop_size,
                generations=generations,
            )
            runtimes.append(time.perf_counter() - start)
            feasible = [item for item in pareto_set if item["feasible"]]
            if feasible:
                best_costs.append(min(item["metrics"]["cost"] for item in feasible))
                solution_counts.append(len(feasible))
        results.append(
            {
                "generations": generations,
                "avg_best_cost": mean(best_costs) if best_costs else np.nan,
                "avg_solution_count": mean(solution_counts) if solution_counts else 0.0,
                "avg_runtime": mean(runtimes),
            }
        )
    return results


def collect_pareto_front(days=2, budget=300, per_day=3, pop_size=24, generations=16, seed=42):
    spots = benchmark_spots()
    random.seed(seed)
    pareto_set, _ = run_nsga2(
        spots,
        days=days,
        budget=budget,
        per_day=per_day,
        pop_size=pop_size,
        generations=generations,
    )
    feasible = [item for item in pareto_set if item["feasible"]]
    return [
        {
            "cost": item["metrics"]["cost"],
            "distance": item["metrics"]["distance"],
            "rating": item["metrics"]["rating"],
            "hotness": item["metrics"]["hotness"],
        }
        for item in feasible
    ]


def plot_algorithm_comparison(results, output_path):
    labels = list(results.keys())
    avg_cost = [results[name]["avg_best_cost"] for name in labels]
    solution_count = [results[name]["avg_solution_count"] for name in labels]
    runtime = [results[name]["avg_runtime"] for name in labels]

    fig, axes = plt.subplots(1, 3, figsize=(14, 4.5))
    colors = ["#43A047", "#1E88E5", "#FB8C00"]

    axes[0].bar(labels, avg_cost, color=colors)
    axes[0].set_title("平均最优成本")
    axes[0].set_ylabel("元")

    axes[1].bar(labels, solution_count, color=colors)
    axes[1].set_title("平均可行方案数")
    axes[1].set_ylabel("个")

    axes[2].bar(labels, runtime, color=colors)
    axes[2].set_title("平均运行时间")
    axes[2].set_ylabel("秒")

    fig.suptitle("NSGA-II 与基线算法对比")
    plt.tight_layout()
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def plot_budget_sensitivity(results, output_path):
    budgets = [item["budget"] for item in results]
    feasible_rates = [item["feasible_rate"] * 100 for item in results]
    avg_best_cost = [item["avg_best_cost"] for item in results]

    fig, ax1 = plt.subplots(figsize=(7, 4.5))
    ax2 = ax1.twinx()

    ax1.plot(budgets, feasible_rates, marker="o", color="#43A047", label="可行解比例")
    ax2.plot(budgets, avg_best_cost, marker="s", color="#1E88E5", label="平均最优成本")

    ax1.set_xlabel("预算（元）")
    ax1.set_ylabel("可行解比例（%）", color="#43A047")
    ax2.set_ylabel("平均最优成本（元）", color="#1E88E5")
    ax1.set_title("预算约束敏感性分析")

    plt.tight_layout()
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def plot_population_sensitivity(results, output_path):
    pop_sizes = [item["pop_size"] for item in results]
    best_costs = [item["avg_best_cost"] for item in results]
    runtimes = [item["avg_runtime"] for item in results]

    fig, ax1 = plt.subplots(figsize=(7, 4.5))
    ax2 = ax1.twinx()

    ax1.plot(pop_sizes, best_costs, marker="o", color="#8E24AA", label="平均最优成本")
    ax2.plot(pop_sizes, runtimes, marker="^", color="#E53935", label="平均运行时间")

    ax1.set_xlabel("种群规模")
    ax1.set_ylabel("平均最优成本（元）", color="#8E24AA")
    ax2.set_ylabel("平均运行时间（秒）", color="#E53935")
    ax1.set_title("种群规模敏感性分析")

    plt.tight_layout()
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def plot_convergence_curve(results, output_path):
    generations = [item["generations"] for item in results]
    best_costs = [item["avg_best_cost"] for item in results]
    solution_counts = [item["avg_solution_count"] for item in results]

    fig, ax1 = plt.subplots(figsize=(7.5, 4.8))
    ax2 = ax1.twinx()

    ax1.plot(generations, best_costs, marker="o", color="#1565C0", linewidth=2, label="平均最优成本")
    ax2.plot(generations, solution_counts, marker="s", color="#2E7D32", linewidth=2, label="平均可行方案数")

    ax1.set_xlabel("迭代代数")
    ax1.set_ylabel("平均最优成本（元）", color="#1565C0")
    ax2.set_ylabel("平均可行方案数（个）", color="#2E7D32")
    ax1.set_title("NSGA-II 收敛曲线")

    plt.tight_layout()
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def plot_pareto_front(results, output_path):
    costs = [item["cost"] for item in results]
    ratings = [item["rating"] for item in results]
    distances = [item["distance"] for item in results]

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))

    axes[0].scatter(costs, ratings, s=70, color="#43A047", edgecolors="#1B5E20", alpha=0.85)
    axes[0].set_xlabel("总成本（元）")
    axes[0].set_ylabel("平均评分")
    axes[0].set_title("成本-评分 Pareto 前沿")

    axes[1].scatter(distances, costs, s=70, color="#1E88E5", edgecolors="#0D47A1", alpha=0.85)
    axes[1].set_xlabel("总路程（km）")
    axes[1].set_ylabel("总成本（元）")
    axes[1].set_title("路程-成本 Pareto 前沿")

    fig.suptitle("NSGA-II Pareto 前沿散点图")
    plt.tight_layout()
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
