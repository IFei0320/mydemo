import random
import time
from statistics import mean

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np

from home.data_utils import (
    _safe_float,
    _parse_price,
    _parse_distance_km,
    _normalize_coord_pair,
)
from home.nsga2_trip_planner import (
    ScenicSpot,
    _build_population,
    _crowding_distance,
    _evaluate_population,
    _evaluate_route,
    _fast_non_dominated_sort,
    _mutate,
    _next_generation,
    _ordered_crossover,
    _tournament,
    run_nsga2,
)


def db_spots(city="上海", limit=200):
    """从数据库加载真实景点数据构造 ScenicSpot 列表（仅收费+有效坐标）。"""
    import django
    django.setup()
    from home.models import TravelInfo
    queryset = TravelInfo.objects.filter(city__icontains=city).exclude(
        longitude__isnull=True
    ).exclude(latitude__isnull=True)
    spots = []
    for row in queryset:
        lon, lat = _normalize_coord_pair(row.longitude, row.latitude)
        if not lon or not lat:
            continue
        cost = _parse_price(row.actual_price)
        if cost <= 0:
            continue
        rating = _safe_float(row.rating, 3.0)
        if rating <= 0:
            continue
        spots.append(ScenicSpot(
            name=row.name or "未知",
            city=row.city or city,
            area=row.area or "",
            tags=row.tags or "",
            rating=rating,
            hotness=_safe_float(row.popularity_score, 5.0),
            reviews=_safe_float(row.review_count, 0),
            cost=cost,
            lon=lon,
            lat=lat,
            center_distance_km=_parse_distance_km(row.distance_from_center),
        ))
        if len(spots) >= limit:
            break
    return spots


_FONT_PRIORITY = ["Microsoft YaHei", "SimHei", "STXihei", "SimSun"]
_available_cjk_fonts = [name for name in _FONT_PRIORITY if any(f.name == name for f in fm.fontManager.ttflist)]
if _available_cjk_fonts:
    plt.rcParams["font.sans-serif"] = _available_cjk_fonts + list(plt.rcParams.get("font.sans-serif", []))
plt.rcParams["axes.unicode_minus"] = False

_COLORS = {"nsga2": "#43A047", "greedy": "#1E88E5", "random": "#FB8C00",
           "economy": "#43A047", "balanced": "#1E88E5", "experience": "#E53935"}


def _compute_hv(costs, neg_ratings):
    """归一化二维超体积。cost(最小化), neg_rating(最小化=最高评分)。参考点(1,1)。"""
    points = sorted(zip(costs, neg_ratings), key=lambda p: p[0])
    hv = 0.0
    prev_f2 = 1.0
    for f1, f2 in points:
        if 0.0 <= f1 <= 1.0 and 0.0 <= f2 <= 1.0:
            hv += (1.0 - f1) * (prev_f2 - f2)
            prev_f2 = f2
    return max(0.0, min(1.0, hv))


def _normalize_metrics(costs, neg_ratings, cost_ref, rating_ref):
    """归一化：0=最好，1=最差。"""
    cost_min, cost_max = min(costs), max(costs)
    if cost_max <= cost_min:
        norm_costs = [0.0 for _ in costs]
    else:
        norm_costs = [(c - cost_min) / (cost_max - cost_min) for c in costs]

    nr_min, nr_max = min(neg_ratings), max(neg_ratings)
    if nr_max <= nr_min:
        norm_nrs = [0.0 for _ in neg_ratings]
    else:
        norm_nrs = [(nr - nr_min) / (nr_max - nr_min) for nr in neg_ratings]

    return norm_costs, norm_nrs


def _collector_base(spots, days, budget, per_day, pop_size, generations, runs, seed_base):
    """通用收集器：重复运行 NSGA-II，返回各次运行的指标列表。"""
    route_len = days * per_day
    metrics_list = []
    min_cost_list = []
    hv_list = []
    runtimes = []
    feasible_counts = []

    for i in range(runs):
        start = time.perf_counter()
        random.seed(seed_base + i)
        pareto_set, _ = run_nsga2(spots, days=days, budget=budget, per_day=per_day,
                                  pop_size=pop_size, generations=generations)
        runtimes.append(time.perf_counter() - start)

        feasible = [item for item in pareto_set if item["feasible"]]
        feasible_counts.append(len(feasible))

        if feasible:
            costs = [item["metrics"]["cost"] for item in feasible]
            ratings = [item["metrics"]["rating"] for item in feasible]
            neg_ratings = [-r for r in ratings]
            c_ref = max(costs) * 1.1 if costs else budget * 1.1
            r_min = min(ratings) if ratings else 0
            nrs = [-r for r in ratings]

            norm_c, norm_nr = _normalize_metrics(costs, nrs, c_ref, -r_min)
            hv = _compute_hv(norm_c, norm_nr)
            hv_list.append(hv)

            best_idx = max(range(len(ratings)), key=lambda j: ratings[j] * 10 - costs[j] / 100)
            metrics_list.append({
                "cost": costs[best_idx],
                "distance": feasible[best_idx]["metrics"]["distance"],
                "rating": feasible[best_idx]["metrics"]["rating"],
                "hotness": feasible[best_idx]["metrics"]["hotness"],
            })
            min_cost_list.append(min(costs))
        else:
            hv_list.append(0.0)
            metrics_list.append({"cost": float("inf"), "distance": float("inf"),
                                 "rating": 0.0, "hotness": 0.0})
            min_cost_list.append(float("inf"))

    return {
        "runtimes": runtimes,
        "feasible_counts": feasible_counts,
        "hv_list": hv_list,
        "metrics_list": metrics_list,
        "min_cost_list": min_cost_list,
    }


def greedy_baseline(spots, route_len, budget, per_day=3):
    """贪心基线：按评分降序选择，超预算时回退。"""
    ranked = sorted(
        range(len(spots)),
        key=lambda idx: (-spots[idx].rating, -spots[idx].hotness, spots[idx].cost),
    )
    selected, total_cost = [], 0.0
    for idx in ranked:
        if len(selected) >= route_len:
            break
        if total_cost + spots[idx].cost > budget:
            continue
        selected.append(idx)
        total_cost += spots[idx].cost
    # 回退：如果超预算，尝试用更便宜的替换
    while total_cost > budget and len(selected) > 1:
        # 移除成本最高的
        worst_idx = max(selected, key=lambda i: spots[i].cost)
        selected.remove(worst_idx)
        total_cost -= spots[worst_idx].cost
    # 填满
    while len(selected) < route_len:
        for idx in ranked:
            if idx not in selected:
                selected.append(idx)
                break
    metrics = _evaluate_route(selected, spots, per_day=per_day)
    return {"route": selected, "metrics": metrics, "feasible": metrics["cost"] <= budget}


def random_baseline(spots, route_len, budget, per_day=3, trials=1000, seed=0):
    """随机基线：随机采样trials次取最优。"""
    rng = random.Random(seed)
    candidates = list(range(len(spots)))
    best = None
    for _ in range(trials):
        route = rng.sample(candidates, route_len)
        metrics = _evaluate_route(route, spots, per_day=per_day)
        feasible = metrics["cost"] <= budget
        item = {"route": route, "metrics": metrics, "feasible": feasible}
        if not best or (feasible and not best["feasible"]) or \
           (feasible == best["feasible"] and metrics["cost"] < best["metrics"]["cost"]):
            best = item
    return best


# ── 采集函数 ──────────────────────────────────────────────

def collect_algorithm_comparison(spots=None, days=3, budget=800, per_day=3, pop_size=40, generations=50, runs=10):
    if spots is None:
        spots = db_spots()
    route_len = days * per_day

    def _run(label):
        if label == "NSGA-II":
            data = _collector_base(spots, days, budget, per_day, pop_size, generations, runs, seed_base=100)
            return {
                "costs": [m["cost"] for m in data["metrics_list"]],
                "distances": [m["distance"] for m in data["metrics_list"]],
                "ratings": [m["rating"] for m in data["metrics_list"]],
                "hotnesses": [m["hotness"] for m in data["metrics_list"]],
                "pareto_counts": data["feasible_counts"],
                "runtimes": data["runtimes"],
                "feasible_rate": sum(1 for c in data["feasible_counts"] if c > 0) / runs,
                "avg_solution_count": mean(data["feasible_counts"]),
            }
        elif label == "Greedy":
            costs, dists, rats, hots, rts = [], [], [], [], []
            fea = 0
            for i in range(runs):
                random.seed(200 + i)
                start = time.perf_counter()
                sol = greedy_baseline(spots, route_len, budget, per_day=per_day)
                rts.append(time.perf_counter() - start)
                costs.append(sol["metrics"]["cost"])
                dists.append(sol["metrics"]["distance"])
                rats.append(sol["metrics"]["rating"])
                hots.append(sol["metrics"]["hotness"])
                if sol["feasible"]:
                    fea += 1
            return {
                "costs": costs, "distances": dists, "ratings": rats,
                "hotnesses": hots, "pareto_counts": [1] * runs,
                "runtimes": rts, "feasible_rate": fea / runs,
                "avg_solution_count": 1.0,
            }
        else:
            costs, dists, rats, hots, rts = [], [], [], [], []
            fea = 0
            for i in range(runs):
                start = time.perf_counter()
                sol = random_baseline(spots, route_len, budget, per_day=per_day, trials=1000, seed=300 + i)
                rts.append(time.perf_counter() - start)
                costs.append(sol["metrics"]["cost"])
                dists.append(sol["metrics"]["distance"])
                rats.append(sol["metrics"]["rating"])
                hots.append(sol["metrics"]["hotness"])
                if sol["feasible"]:
                    fea += 1
            return {
                "costs": costs, "distances": dists, "ratings": rats,
                "hotnesses": hots, "pareto_counts": [1] * runs,
                "runtimes": rts, "feasible_rate": fea / runs,
                "avg_solution_count": 1.0,
            }

    return {"NSGA-II": _run("NSGA-II"), "Greedy": _run("Greedy"), "Random": _run("Random")}


def collect_budget_sensitivity(budgets=None, spots=None, days=3, per_day=3, pop_size=30, generations=30, runs=10):
    if budgets is None:
        budgets = [400, 600, 800, 1000, 1200, 1500, 2000]
    if spots is None:
        spots = db_spots()
    results = []
    for budget in budgets:
        data = _collector_base(spots, days, budget, per_day, pop_size, generations, runs, seed_base=400 + int(budget))
        feasible_rate = sum(1 for c in data["feasible_counts"] if c > 0) / runs
        avg_pareto = mean(data["feasible_counts"])
        valid_costs = [c for c in [m["cost"] for m in data["metrics_list"]] if c < float("inf")]
        results.append({
            "budget": budget,
            "feasible_rate": feasible_rate,
            "avg_pareto_count": avg_pareto,
            "avg_best_cost": mean(valid_costs) if valid_costs else np.nan,
            "avg_hv": mean(data["hv_list"]),
        })
    return results


def collect_generations_sensitivity(spots=None, gen_steps=None, budget=800, days=3, per_day=3, pop_size=40, runs=10):
    if gen_steps is None:
        gen_steps = [5, 10, 15, 20, 30, 40, 50, 70, 100]
    if spots is None:
        spots = db_spots()
    results = []
    for generations in gen_steps:
        data = _collector_base(spots, days, budget, per_day, pop_size, generations, runs, seed_base=600 + generations)
        feasible_rate = sum(1 for c in data["feasible_counts"] if c > 0) / runs
        avg_pareto = mean(data["feasible_counts"])
        results.append({
            "generations": generations,
            "avg_hv": mean(data["hv_list"]),
            "feasible_rate": feasible_rate,
            "avg_pareto_count": avg_pareto,
            "avg_runtime": mean(data["runtimes"]),
        })
    return results


def collect_population_sensitivity(pop_sizes=None, spots=None, budget=800, days=3, per_day=3, generations=50, runs=10):
    if pop_sizes is None:
        pop_sizes = [10, 20, 30, 40, 60, 80, 100]
    if spots is None:
        spots = db_spots()
    results = []
    for pop_size in pop_sizes:
        data = _collector_base(spots, days, budget, per_day, pop_size, generations, runs, seed_base=800 + pop_size)
        feasible_rate = sum(1 for c in data["feasible_counts"] if c > 0) / runs
        results.append({
            "pop_size": pop_size,
            "avg_hv": mean(data["hv_list"]),
            "feasible_rate": feasible_rate,
            "avg_pareto_count": mean(data["feasible_counts"]),
            "avg_runtime": mean(data["runtimes"]),
        })
    return results


def collect_convergence_curve(spots=None, days=3, budget=800, per_day=3, pop_size=40, generation_steps=None, runs=10):
    """在同一次演化内追踪快照，避免独立种子导致的曲线抖动。"""
    if generation_steps is None:
        generation_steps = [1, 2, 5, 10, 15, 20, 25, 30, 40, 50]
    if spots is None:
        spots = db_spots()
    max_gen = max(generation_steps)
    step_set = set(generation_steps)
    route_len = days * per_day

    all_snapshots = {g: {"hv": [], "feasible": 0, "min_cost": []} for g in generation_steps}
    for run_i in range(runs):
        random.seed(700 + run_i)
        population = _build_population(spots, route_len, pop_size)
        _evaluate_population(population, spots, per_day, budget)

        for gen in range(1, max_gen + 1):
            fronts = _fast_non_dominated_sort(population)
            for front in fronts:
                _crowding_distance(population, front)
            offspring = []
            while len(offspring) < pop_size:
                p1 = _tournament(population)
                p2 = _tournament(population)
                child_route = _ordered_crossover(p1["route"], p2["route"])
                child_route = _mutate(child_route, len(spots))
                offspring.append({"route": child_route})
            _evaluate_population(offspring, spots, per_day, budget)
            combined = population + offspring
            population = _next_generation(combined, pop_size)

            if gen in step_set:
                feasible = [it for it in population if it["feasible"]]
                if feasible:
                    fc = [it["metrics"]["cost"] for it in feasible]
                    fr = [it["metrics"]["rating"] for it in feasible]
                    nrs = [-r for r in fr]
                    c_ref = max(fc) * 1.1 if fc else budget * 1.1
                    norm_c, norm_nr = _normalize_metrics(fc, nrs, c_ref, -min(fr) if fr else 0)
                    all_snapshots[gen]["hv"].append(_compute_hv(norm_c, norm_nr))
                    all_snapshots[gen]["min_cost"].append(min(fc))
                    all_snapshots[gen]["feasible"] += 1
                else:
                    all_snapshots[gen]["hv"].append(0.0)
                    all_snapshots[gen]["min_cost"].append(float("inf"))

    results = []
    for generations in generation_steps:
        snap = all_snapshots[generations]
        valid_costs = [c for c in snap["min_cost"] if c < float("inf")]
        results.append({
            "generations": generations,
            "avg_hv": mean(snap["hv"]) if snap["hv"] else 0.0,
            "feasible_rate": snap["feasible"] / runs,
            "avg_best_cost": mean(valid_costs) if valid_costs else np.nan,
        })
    return results


def collect_pareto_front(spots=None, days=3, budget=800, per_day=3, pop_size=40, generations=50, seed=42):
    if spots is None:
        spots = db_spots()
    random.seed(seed)
    pareto_set, _ = run_nsga2(spots, days=days, budget=budget, per_day=per_day,
                              pop_size=pop_size, generations=generations)
    feasible = [item for item in pareto_set if item["feasible"]]
    points = []
    for item in feasible:
        points.append({
            "cost": item["metrics"]["cost"],
            "distance": item["metrics"]["distance"],
            "rating": item["metrics"]["rating"],
            "hotness": item["metrics"]["hotness"],
        })
    return points


# ── 绘图函数 ──────────────────────────────────────────────

def plot_algorithm_comparison(results, output_path):
    labels = list(results.keys())
    metrics_def = [
        ("avg_cost", "总成本", "元"),
        ("avg_distance", "总路程", "km"),
        ("avg_rating", "平均评分", ""),
        ("avg_hotness", "平均热度", ""),
        ("avg_runtime", "运行时间", "秒"),
    ]

    fig, axes = plt.subplots(1, 5, figsize=(20, 4.5))
    colors = [_COLORS["nsga2"], _COLORS["greedy"], _COLORS["random"]]

    for idx, (key, title, unit) in enumerate(metrics_def):
        if key == "avg_cost":
            vals = [mean(results[name]["costs"]) for name in labels]
            axes[idx].bar(labels, vals, color=colors, edgecolor="white", linewidth=0.5)
            axes[idx].set_yscale('log')
            axes[idx].set_ylabel(unit + " (对数)", fontsize=9)
            for i, v in enumerate(vals):
                axes[idx].text(i, v * 1.15, f"{v:.0f}", ha="center", fontsize=8)
        elif key == "avg_distance":
            vals = [mean(results[name]["distances"]) for name in labels]
            axes[idx].bar(labels, vals, color=colors, edgecolor="white", linewidth=0.5)
            axes[idx].set_ylabel(unit, fontsize=9)
            for i, v in enumerate(vals):
                axes[idx].text(i, v + max(vals) * 0.02, f"{v:.0f}", ha="center", fontsize=8)
        elif key == "avg_rating":
            vals = [mean(results[name]["ratings"]) for name in labels]
            axes[idx].bar(labels, vals, color=colors, edgecolor="white", linewidth=0.5)
            axes[idx].set_ylim(min(vals) * 0.95, max(vals) * 1.02)
            axes[idx].set_ylabel(unit, fontsize=9)
            for i, v in enumerate(vals):
                axes[idx].text(i, v + (max(vals) - min(vals)) * 0.01, f"{v:.2f}", ha="center", fontsize=8)
        elif key == "avg_hotness":
            vals = [mean(results[name]["hotnesses"]) for name in labels]
            axes[idx].bar(labels, vals, color=colors, edgecolor="white", linewidth=0.5)
            axes[idx].set_ylabel(unit, fontsize=9)
            for i, v in enumerate(vals):
                axes[idx].text(i, v + max(vals) * 0.02, f"{v:.2f}", ha="center", fontsize=8)
        else:
            vals = [mean(results[name]["runtimes"]) for name in labels]
            axes[idx].bar(labels, vals, color=colors, edgecolor="white", linewidth=0.5)
            axes[idx].set_ylabel(unit, fontsize=9)
            for i, v in enumerate(vals):
                axes[idx].text(i, v + max(vals) * 0.02, f"{v:.3f}", ha="center", fontsize=8)
        
        axes[idx].set_title(title, fontsize=11, fontweight="bold")

    fig.suptitle("NSGA-II 与基线算法多维对比", fontsize=13, fontweight="bold")
    plt.tight_layout()
    fig.savefig(output_path, format="svg", bbox_inches="tight")
    plt.close(fig)


def plot_convergence_curve(results, output_path):
    generations = [item["generations"] for item in results]
    hv_vals = [item["avg_hv"] for item in results]
    feasible_rates = [item["feasible_rate"] * 100 for item in results]
    best_costs = [item["avg_best_cost"] if not np.isnan(item["avg_best_cost"]) else None for item in results]

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # (a) 超体积收敛 - 添加移动平均平滑线
    ax1 = axes[0]
    ax1.plot(generations, hv_vals, marker="o", color="#1565C0", linewidth=1.5, markersize=5, alpha=0.6, label="原始值")
    if len(hv_vals) >= 3:
        window = min(3, len(hv_vals))
        smoothed = np.convolve(hv_vals, np.ones(window)/window, mode='valid')
        smooth_gens = generations[window-1:]
        ax1.plot(smooth_gens, smoothed, color="#0D47A1", linewidth=2.5, label="趋势线")
    ax1.set_xlabel("进化代数", fontsize=10)
    ax1.set_ylabel("超体积 (HV)", fontsize=10)
    ax1.set_title("(a) 超体积指标收敛", fontsize=11, fontweight="bold")
    ax1.grid(True, alpha=0.3)
    ax1.set_ylim(0, max(hv_vals) * 1.1)
    ax1.legend(fontsize=8, loc="lower right")

    # (b) 求解质量 + 可行性 双轴 - 收紧成本坐标
    ax2 = axes[1]
    valid_data = [(g, c, f) for g, c, f in zip(generations, best_costs, feasible_rates) if c is not None and not np.isnan(c)]
    valid_gens = [d[0] for d in valid_data]
    valid_costs = [d[1] for d in valid_data]
    valid_feas = [d[2] for d in valid_data]
    line1 = ax2.plot(valid_gens, valid_costs, marker="o",
                     color="#E53935", linewidth=2, markersize=6, label="平均最优成本")
    ax2.set_xlabel("进化代数", fontsize=10)
    ax2.set_ylabel("平均最优成本（元）", fontsize=10, color="#E53935")
    if valid_costs:
        ax2.set_ylim(min(valid_costs) * 0.92, max(valid_costs) * 1.05)
    ax3 = ax2.twinx()
    line2 = ax3.plot(valid_gens, valid_feas, marker="s",
                     color="#2E7D32", linewidth=2, markersize=6, label="可行解比例")
    ax3.set_ylabel("可行解比例 (%)", fontsize=10, color="#2E7D32")
    ax2.set_title("(b) 求解质量与可行性收敛", fontsize=11, fontweight="bold")
    lines = line1 + line2
    ax2.legend(lines, [l.get_label() for l in lines], fontsize=8, loc="center right")
    ax2.grid(True, alpha=0.3)
    ax3.set_ylim(0, 105)

    fig.suptitle("NSGA-II 收敛性分析", fontsize=13, fontweight="bold")
    plt.tight_layout()
    fig.savefig(output_path, format="svg", bbox_inches="tight")
    plt.close(fig)


def plot_pareto_front(results, output_path):
    costs = [item["cost"] for item in results]
    ratings = [item["rating"] for item in results]

    if len(results) < 3:
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.scatter(costs, ratings, s=70, color="#43A047", edgecolors="#1B5E20", alpha=0.85)
        ax.set_title("Pareto 前沿散点图 (可行解不足3个)", fontsize=12)
        fig.savefig(output_path, format="svg", bbox_inches="tight")
        plt.close(fig)
        return

    pairs = list(zip(costs, ratings))
    # economy: 最低成本
    econ_idx = min(range(len(pairs)), key=lambda i: pairs[i][0])
    # experience: 最高评分
    exp_idx = max(range(len(pairs)), key=lambda i: pairs[i][1])
    # balanced: 距 economy-experience 连线最远
    e1, e2 = pairs[econ_idx], pairs[exp_idx]
    bal_idx = econ_idx
    max_dist = 0.0
    if abs(e2[0] - e1[0]) > 1e-6:
        for i, (c, r) in enumerate(pairs):
            d = abs((e2[1] - e1[1]) * c - (e2[0] - e1[0]) * r + e2[0] * e1[1] - e2[1] * e1[0]) / \
                ((e2[1] - e1[1]) ** 2 + (e2[0] - e1[0]) ** 2) ** 0.5
            if d > max_dist:
                max_dist = d
                bal_idx = i

    fig, ax = plt.subplots(figsize=(9, 6.5))
    ax.scatter(costs, ratings, s=60, color="#BDBDBD", edgecolors="#757575", alpha=0.6)

    special = [(econ_idx, "economy", "省钱型"), (bal_idx, "balanced", "均衡型"), (exp_idx, "experience", "体验型")]
    for idx, style, label in special:
        c, r = pairs[idx]
        ax.scatter([c], [r], s=180, color=_COLORS[style], edgecolors="white", linewidth=2, zorder=5)
        ax.annotate(f"{label}\n({c:.0f}元, {r:.2f}分)", xy=(c, r),
                    xytext=(15, 10 if style != "economy" else -20),
                    textcoords="offset points", fontsize=10, fontweight="bold",
                    color=_COLORS[style],
                    arrowprops=dict(arrowstyle="->", color=_COLORS[style], lw=1.5),
                    bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.85))

    ax.set_xlabel("总成本（元）", fontsize=11)
    ax.set_ylabel("平均评分", fontsize=11)
    ax.set_title("NSGA-II Pareto 前沿散点图", fontsize=12, fontweight="bold")
    ax.grid(True, alpha=0.3)
    
    if ratings:
        y_margin = (max(ratings) - min(ratings)) * 0.15
        ax.set_ylim(min(ratings) - y_margin, max(ratings) + y_margin)

    fig.tight_layout()
    fig.savefig(output_path, format="svg", bbox_inches="tight")
    plt.close(fig)


def plot_generations_sensitivity(results, output_path):
    gen_steps = [item["generations"] for item in results]
    hv_vals = [item["avg_hv"] for item in results]
    feasible_rates = [item["feasible_rate"] * 100 for item in results]

    fig, ax1 = plt.subplots(figsize=(8, 5))
    ax2 = ax1.twinx()

    ax1.plot(gen_steps, hv_vals, marker="o", color="#1565C0", linewidth=1.5, markersize=6, alpha=0.6)
    if len(hv_vals) >= 3:
        from scipy.ndimage import gaussian_filter1d
        try:
            smoothed_hv = gaussian_filter1d(hv_vals, sigma=1.0)
            ax1.plot(gen_steps, smoothed_hv, color="#0D47A1", linewidth=2.5, label="HV趋势")
        except:
            ax1.plot(gen_steps, hv_vals, color="#0D47A1", linewidth=2.5)
    
    ax2.plot(gen_steps, feasible_rates, marker="s", color="#2E7D32", linewidth=2, markersize=8,
             linestyle="--", label="可行解比例")

    ax1.set_xlabel("进化代数", fontsize=11)
    ax1.set_ylabel("超体积 (HV)", fontsize=11, color="#1565C0")
    ax2.set_ylabel("可行解比例 (%)", fontsize=11, color="#2E7D32")
    ax1.set_title("(a) 进化代数对收敛性与可行性的影响", fontsize=12, fontweight="bold")
    ax1.grid(True, alpha=0.3)
    ax1.set_ylim(0, max(hv_vals) * 1.1)

    if 50 in gen_steps:
        idx_50 = gen_steps.index(50)
        ax1.annotate(f"选取gen=50\nHV={hv_vals[idx_50]:.3f}\n可行率={feasible_rates[idx_50]:.0f}%",
                     xy=(50, hv_vals[idx_50]),
                     xytext=(50 + 10, hv_vals[idx_50] - 0.05),
                     fontsize=9, fontweight="bold",
                     arrowprops=dict(arrowstyle="->", color="gray", lw=1.2))

    fig.tight_layout()
    fig.savefig(output_path, format="svg", bbox_inches="tight")
    plt.close(fig)


def plot_budget_sensitivity(results, output_path):
    budgets = [item["budget"] for item in results]
    feasible_rates = [item["feasible_rate"] * 100 for item in results]
    pareto_counts = [item["avg_pareto_count"] for item in results]

    fig, ax1 = plt.subplots(figsize=(8, 5))
    ax2 = ax1.twinx()

    ax1.plot(budgets, feasible_rates, marker="o", color="#43A047", linewidth=2, markersize=8)
    ax2.plot(budgets, pareto_counts, marker="D", color="#FB8C00", linewidth=2, markersize=7,
             linestyle="--")

    ax1.set_xlabel("预算（元）", fontsize=11)
    ax1.set_ylabel("可行解比例 (%)", fontsize=11, color="#43A047")
    ax2.set_ylabel("平均 Pareto 解数 (个)", fontsize=11, color="#FB8C00")
    ax1.set_title("(b) 预算约束对可行性与多样性的影响", fontsize=12, fontweight="bold")
    ax1.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(output_path, format="svg", bbox_inches="tight")
    plt.close(fig)


def plot_budget_cost_plateau(results, output_path):
    budgets = [item["budget"] for item in results]
    avg_costs = [item["avg_best_cost"] if not np.isnan(item["avg_best_cost"]) else None for item in results]
    valid_budgets = [b for i, b in enumerate(budgets) if avg_costs[i] is not None]
    valid_costs = [c for c in avg_costs if c is not None]

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(valid_budgets, valid_costs, marker="s", color="#1E88E5", linewidth=2, markersize=8, label="实际成本")
    
    if valid_budgets:
        ax.plot([min(valid_budgets), max(valid_budgets)], 
                [min(valid_budgets), max(valid_budgets)], 
                'k--', alpha=0.3, linewidth=1, label="预算线")
    
    ax.set_xlabel("预算（元）", fontsize=11)
    ax.set_ylabel("路线平均成本（元）", fontsize=11)
    ax.set_title("(c) 预算与实际成本的匹配关系", fontsize=12, fontweight="bold")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=9, loc="upper left")

    fig.tight_layout()
    fig.savefig(output_path, format="svg", bbox_inches="tight")
    plt.close(fig)
