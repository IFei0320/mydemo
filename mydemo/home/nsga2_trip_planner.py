import math
import random
import re
from dataclasses import dataclass
from typing import Dict, List, Tuple

from home.config import (
    GENERATIONS,
    MUTATION_RATE,
    POPULATION_SIZE,
    SPOTS_PER_DAY,
)
from home.data_utils import _haversine_km, _season_bonus

# import family
#
# from home.nsga2_knowledge import retrieve_knowledge_cards
# from home.nsga2_report import call_ai_html_report, call_ai_refiner


@dataclass
class ScenicSpot:
    name: str
    city: str
    area: str
    tags: str
    rating: float
    hotness: float
    reviews: float
    cost: float
    lon: float
    lat: float
    center_distance_km: float


def _normalize(values: List[float]) -> List[float]:
    if not values:
        return []
    min_v, max_v = min(values), max(values)
    if math.isclose(min_v, max_v):
        return [0.5 for _ in values]
    return [(v - min_v) / (max_v - min_v) for v in values]





def build_candidates(city: str, season: str, require_coord: bool = True) -> List[ScenicSpot]:
    """从清洗表 CleanedAttraction 构建候选景点列表，按 name 去重保留 rating 最高"""
    from home.models import CleanedAttraction

    qs = CleanedAttraction.objects.filter(city__icontains=city)
    if require_coord:
        qs = qs.filter(is_coord_valid=True)

    # 精确匹配优先，降低跨城误入
    primary = [row for row in qs if row.city.replace("市", "") == city.replace("市", "")]
    source_rows = primary if len(primary) >= 9 else list(qs)

    spots: List[ScenicSpot] = []
    for row in source_rows:
        spots.append(
            ScenicSpot(
                name=row.name,
                city=row.city,
                area=row.area or "",
                tags=row.tags or "",
                rating=row.rating + _season_bonus(row.tags or "", season),
                hotness=row.hotness,
                reviews=float(row.review_count),
                cost=row.cost,
                lon=row.longitude,
                lat=row.latitude,
                center_distance_km=row.center_distance_km,
            )
        )

    # 按 name 去重：同名保留 rating 最高的那一条
    seen: dict = {}
    for s in spots:
        if s.name not in seen or s.rating > seen[s.name].rating:
            seen[s.name] = s
    return list(seen.values())


def _route_distance_km(route_indices: List[int], spots: List[ScenicSpot], per_day: int) -> float:
    total = 0.0
    for i, idx in enumerate(route_indices):
        cur = spots[idx]
        is_new_day = i % per_day == 0
        if is_new_day:
            total += cur.center_distance_km
        elif i > 0:
            prev = spots[route_indices[i - 1]]
            total += _haversine_km(prev.lon, prev.lat, cur.lon, cur.lat)
    return total


def _evaluate_route(route_indices: List[int], spots: List[ScenicSpot], per_day: int) -> Dict[str, float]:
    costs = [spots[idx].cost for idx in route_indices]
    ratings = [spots[idx].rating for idx in route_indices]
    hotness = [spots[idx].hotness for idx in route_indices]
    reviews = [math.log1p(spots[idx].reviews) for idx in route_indices]
    return {
        "cost": sum(costs),
        "distance": _route_distance_km(route_indices, spots, per_day),
        "rating": sum(ratings) / len(ratings),
        "hotness": sum(hotness) / len(hotness),
        "reviews": sum(reviews) / len(reviews),
    }


def _dominates(a: Dict, b: Dict) -> bool:
    objs_a = a["objectives"]
    objs_b = b["objectives"]
    no_worse = all(x <= y for x, y in zip(objs_a, objs_b))
    strictly_better = any(x < y for x, y in zip(objs_a, objs_b))
    return no_worse and strictly_better


def _fast_non_dominated_sort(population: List[Dict]) -> List[List[int]]:
    fronts: List[List[int]] = [[]]
    for p_idx, p in enumerate(population):
        p["dominated"] = []
        p["dom_count"] = 0
        for q_idx, q in enumerate(population):
            if p_idx == q_idx:
                continue
            if _dominates(p, q):
                p["dominated"].append(q_idx)
            elif _dominates(q, p):
                p["dom_count"] += 1
        if p["dom_count"] == 0:
            p["rank"] = 0
            fronts[0].append(p_idx)

    cur = 0
    while cur < len(fronts) and fronts[cur]:
        next_front: List[int] = []
        for p_idx in fronts[cur]:
            for q_idx in population[p_idx]["dominated"]:
                population[q_idx]["dom_count"] -= 1
                if population[q_idx]["dom_count"] == 0:
                    population[q_idx]["rank"] = cur + 1
                    next_front.append(q_idx)
        if next_front:
            fronts.append(next_front)
        cur += 1
    return fronts


def _crowding_distance(population: List[Dict], front: List[int]) -> None:
    if not front:
        return
    obj_count = len(population[front[0]]["objectives"])
    for idx in front:
        population[idx]["distance"] = 0.0
    if len(front) <= 2:
        for idx in front:
            population[idx]["distance"] = float("inf")
        return

    for m in range(obj_count):
        sorted_front = sorted(front, key=lambda i: population[i]["objectives"][m])
        population[sorted_front[0]]["distance"] = float("inf")
        population[sorted_front[-1]]["distance"] = float("inf")
        min_v = population[sorted_front[0]]["objectives"][m]
        max_v = population[sorted_front[-1]]["objectives"][m]
        if math.isclose(min_v, max_v):
            continue
        for i in range(1, len(sorted_front) - 1):
            prev_v = population[sorted_front[i - 1]]["objectives"][m]
            next_v = population[sorted_front[i + 1]]["objectives"][m]
            population[sorted_front[i]]["distance"] += (next_v - prev_v) / (max_v - min_v)


def _tournament(population: List[Dict]) -> Dict:
    a, b = random.sample(population, 2)
    if a["rank"] < b["rank"]:
        return a
    if b["rank"] < a["rank"]:
        return b
    return a if a["distance"] >= b["distance"] else b


def _repair_unique(route_indices: List[int], candidate_count: int) -> List[int]:
    unique = []
    seen = set()
    for idx in route_indices:
        if idx not in seen and 0 <= idx < candidate_count:
            unique.append(idx)
            seen.add(idx)
    leftovers = [i for i in range(candidate_count) if i not in seen]
    while len(unique) < len(route_indices) and leftovers:
        unique.append(leftovers.pop(random.randrange(len(leftovers))))
    return unique


def _ordered_crossover(parent_a: List[int], parent_b: List[int]) -> List[int]:
    size = len(parent_a)
    start, end = sorted(random.sample(range(size), 2))
    child = [-1] * size
    child[start : end + 1] = parent_a[start : end + 1]
    fill = [gene for gene in parent_b if gene not in child]
    cursor = 0
    for i in range(size):
        if child[i] == -1:
            child[i] = fill[cursor]
            cursor += 1
    return child


def _mutate(route_indices: List[int], candidate_count: int, mutation_rate: float = MUTATION_RATE) -> List[int]:
    result = route_indices[:]
    if random.random() < mutation_rate and len(result) > 1:
        i, j = random.sample(range(len(result)), 2)
        result[i], result[j] = result[j], result[i]
    if random.random() < mutation_rate:
        i = random.randrange(len(result))
        existing = set(result)
        choices = [x for x in range(candidate_count) if x not in existing]
        if choices:
            result[i] = random.choice(choices)
    return _repair_unique(result, candidate_count)


def _build_population(spots: List[ScenicSpot], route_len: int, pop_size: int) -> List[Dict]:
    candidates = list(range(len(spots)))
    population = []
    for _ in range(pop_size):
        route = random.sample(candidates, route_len)
        population.append({"route": route})
    return population


def _evaluate_population(population: List[Dict], spots: List[ScenicSpot], per_day: int, budget: float) -> None:
    for item in population:
        metrics = _evaluate_route(item["route"], spots, per_day)
        feasible = metrics["cost"] <= budget if budget > 0 else True
        if feasible:
            objectives = [
                metrics["cost"],
                metrics["distance"],
                -metrics["rating"],
                -metrics["hotness"],
            ]
        else:
            penalty = metrics["cost"] - budget if budget > 0 else metrics["cost"]
            objectives = [1e9 + penalty, 1e9, 1e9, 1e9]
        item["metrics"] = metrics
        item["feasible"] = feasible
        item["objectives"] = objectives


def _next_generation(combined: List[Dict], target_size: int) -> List[Dict]:
    fronts = _fast_non_dominated_sort(combined)
    new_population: List[Dict] = []
    for front in fronts:
        _crowding_distance(combined, front)
        if len(new_population) + len(front) <= target_size:
            new_population.extend(combined[idx] for idx in front)
        else:
            ordered = sorted(front, key=lambda i: combined[i]["distance"], reverse=True)
            remain = target_size - len(new_population)
            new_population.extend(combined[idx] for idx in ordered[:remain])
            break
    return new_population


def run_nsga2(
    spots: List[ScenicSpot],
    days: int,
    budget: float,
    per_day: int = SPOTS_PER_DAY,
    pop_size: int = POPULATION_SIZE,
    generations: int = GENERATIONS,
) -> Tuple[List[Dict], int]:
    route_len = min(days * per_day, len(spots))
    if route_len <= 1:
        return [], 0
    population = _build_population(spots, route_len, pop_size)
    _evaluate_population(population, spots, per_day, budget)

    for _ in range(generations):
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

    final_fronts = _fast_non_dominated_sort(population)
    first_front = [population[idx] for idx in final_fronts[0]] if final_fronts else []
    feasible = [item for item in first_front if item["feasible"]]
    return feasible if feasible else first_front, route_len


def choose_solution(pareto_set: List[Dict], sensitivities: Dict[str, float], budget: float = 0.0) -> Dict:
    if not pareto_set:
        return {}
    costs = [item["metrics"]["cost"] for item in pareto_set]
    distances = [item["metrics"]["distance"] for item in pareto_set]
    hotness = [item["metrics"]["hotness"] for item in pareto_set]
    ratings = [item["metrics"]["rating"] for item in pareto_set]

    n_cost = _normalize(costs)
    n_distance = _normalize(distances)
    n_hot = _normalize(hotness)
    n_rating = _normalize(ratings)
    n_crowd = n_hot[:]  # 热度越高，人流越大
    spend_target = 0.75 if budget > 0 else 0.0

    best_idx = 0
    best_score = float("inf")
    for i in range(len(pareto_set)):
        spend_ratio = (costs[i] / budget) if budget > 0 else 0.0
        spend_gap = abs(spend_ratio - spend_target) if budget > 0 else 0.0
        utility = (
            sensitivities["price"] * n_cost[i]
            + sensitivities["distance"] * n_distance[i]
            - sensitivities["hotness"] * n_hot[i]
            - sensitivities["rating"] * n_rating[i]
            + sensitivities["crowd_avoid"] * n_crowd[i]
            + 0.15 * spend_gap
        )
        if utility < best_score:
            best_score = utility
            best_idx = i
    return pareto_set[best_idx]


def build_route_payload(best_solution: Dict, spots: List[ScenicSpot], days: int, per_day: int = SPOTS_PER_DAY) -> List[Dict]:
    if not best_solution:
        return []
    route = best_solution["route"]
    # 在每日内部优先展示付费景点，避免全是免费点占据前排观感
    reordered = []
    for day_start in range(0, len(route), per_day):
        day_slice = route[day_start : day_start + per_day]
        day_slice_sorted = sorted(day_slice, key=lambda idx: spots[idx].cost, reverse=True)
        reordered.extend(day_slice_sorted)
    route = reordered
    result = []
    for i, idx in enumerate(route):
        day_no = i // per_day + 1
        if day_no > days:
            break
        slot = i % per_day
        time_slot = ["上午", "中午", "下午"][slot]
        spot = spots[idx]
        result.append(
            {
                "name": spot.name,
                "visit_time": f"第{day_no}天-{time_slot}",
                "features": f"评分{spot.rating:.1f}，热度{spot.hotness:.1f}",
        "area": spot.area,
                "longitude": round(spot.lon, 6),
                "latitude": round(spot.lat, 6),
                "estimated_cost": "免费" if spot.cost <= 0 else f"{int(round(spot.cost))}元",
            }
        )
    return result

