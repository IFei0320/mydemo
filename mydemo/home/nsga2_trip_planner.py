import math
import random
import re
from dataclasses import dataclass
from typing import Dict, List, Tuple
# 从home.config模块导入NSGA2算法相关的配置常量
from home.config import (
    BUDGET_TARGET_RATIO,
    EXPERIENCE_HOTNESS_WEIGHT,
    EXPERIENCE_RATING_WEIGHT,
    GENERATIONS,
    INFEASIBLE_PENALTY,     # 不可行解的惩罚值
    MUTATION_RATE,         # 变异率
    POPULATION_SIZE,       # 种群大小
    SPEND_GAP_PENALTY_WEIGHT,   # 花费差距惩罚权重
    SPOTS_PER_DAY,      # 每天安排的景点数量
)
from home.data_utils import _haversine_km, _season_bonus      # 从home.data_utils模块导入辅助函数



@dataclass
class ScenicSpot:         # 定义景点数据类，用于存储景点的各种属性信息
    name: str
    city: str
    area: str
    tags: str
    rating: float
    hotness: float
    reviews: float     # 评论数量或相关指标
    cost: float
    lon: float
    lat: float      # 纬度坐标
    center_distance_km: float


def _normalize(values: List[float]) -> List[float]:     # 归一化函数，将数值列表转换到0-1范围内
    if not values:
        return []
    min_v, max_v = min(values), max(values)      # 找出最小值和最大值
    if math.isclose(min_v, max_v):         
        return [0.5 for _ in values]        
    return [(v - min_v) / (max_v - min_v) for v in values]





def build_candidates(city: str, season: str, require_coord: bool = True) -> List[ScenicSpot]:  # 构建候选景点列表的函数
    """从清洗表 CleanedAttraction 构建候选景点列表，按 name 去重保留 rating 最高"""
    from home.models import CleanedAttraction

    qs = CleanedAttraction.objects.filter(city__icontains=city)  # 查询数据库中匹配城市的景点
    if require_coord:
        qs = qs.filter(is_coord_valid=True)      # 只选择坐标有效的景点

    # 优先选择精确匹配的城市，减少跨城市误选
    primary = [row for row in qs if row.city.replace("市", "") == city.replace("市", "")]
    source_rows = primary if len(primary) >= 9 else list(qs)

    spots: List[ScenicSpot] = []      # 初始化景点列表  遍历数据库查询结果   创建ScenicSpot对象并添加到列表
    for row in source_rows:
        spots.append(
            ScenicSpot(
                name=row.name,
                city=row.city, 
                area=row.area or "",   # 如果area为None则使用空字符串
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
    seen: dict = {}       # 用于存储已见过的景点名称及其对应的最高评分景点
    for s in spots:
        if s.name not in seen or s.rating > seen[s.name].rating:
            seen[s.name] = s
    return list(seen.values())


def _route_distance_km(route_indices: List[int], spots: List[ScenicSpot], per_day: int) -> float:
    total = 0.0
    for i, idx in enumerate(route_indices):
        cur = spots[idx]
        is_new_day = i % per_day == 0
        if is_new_day:    # 如果是新一天的开始，# 加上从市中心到该景点的距离
            total += cur.center_distance_km
        elif i > 0:     # 加上从市中心到该景点的距离，# 获取前一个景点
            prev = spots[route_indices[i - 1]]
            total += _haversine_km(prev.lon, prev.lat, cur.lon, cur.lat)
    return total

# 评估路线的函数
def _evaluate_route(route_indices: List[int], spots: List[ScenicSpot], per_day: int) -> Dict[str, float]:
    costs = [spots[idx].cost for idx in route_indices]    # 提取路线中所有景点的成本
    ratings = [spots[idx].rating for idx in route_indices]
    hotness = [spots[idx].hotness for idx in route_indices]
    return {
        "cost": sum(costs),
        "distance": _route_distance_km(route_indices, spots, per_day),
        "rating": sum(ratings) / len(ratings),
        "hotness": sum(hotness) / len(hotness),
    }

 # 判断解a是否支配解b的函数
def _dominates(a: Dict, b: Dict) -> bool:
    objs_a = a["objectives"]
    objs_b = b["objectives"]
    no_worse = all(x <= y for x, y in zip(objs_a, objs_b))
    strictly_better = any(x < y for x, y in zip(objs_a, objs_b))
    return no_worse and strictly_better      # 同时满足以上两个条件才构成支配关系

 # 快速非支配排序算法
def _fast_non_dominated_sort(population: List[Dict]) -> List[List[int]]:
    fronts: List[List[int]] = [[]]      # 初始化前沿列表，第一前沿为空列表
    for p_idx, p in enumerate(population):     # 遍历种群中的每个个体
        p["dominated"] = []                    # 初始化被该个体支配的个体列表
        p["dom_count"] = 0
        for q_idx, q in enumerate(population):         # 与其他所有个体比较
            if p_idx == q_idx:                  
                continue
            if _dominates(p, q):                    # 如果p支配q，将q添加到p支配的列表中
                p["dominated"].append(q_idx)
            elif _dominates(q, p):
                p["dom_count"] += 1
        if p["dom_count"] == 0:
            p["rank"] = 0
            fronts[0].append(p_idx)

    cur = 0         # 当前前沿索引
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


def _crowding_distance(population: List[Dict], front: List[int]) -> None:   # 计算拥挤度距离的函数
    if not front:
        return
    obj_count = len(population[front[0]]["objectives"])
    for idx in front:           # 初始化前沿中所有个体的拥挤度距离为0
        population[idx]["distance"] = 0.0
    if len(front) <= 2:      # 如果前沿个体数小于等于2， 将这些个体的拥挤度距离设为无穷大（保证边界点被保留）
        for idx in front:
            population[idx]["distance"] = float("inf")
        return

    for m in range(obj_count):    # 对每个目标函数进行处理
        sorted_front = sorted(front, key=lambda i: population[i]["objectives"][m])
        population[sorted_front[0]]["distance"] = float("inf")
        population[sorted_front[-1]]["distance"] = float("inf")
        min_v = population[sorted_front[0]]["objectives"][m]
        max_v = population[sorted_front[-1]]["objectives"][m]
        if math.isclose(min_v, max_v):
            continue
        for i in range(1, len(sorted_front) - 1):
            prev_v = population[sorted_front[i - 1]]["objectives"][m]
            next_v = population[sorted_front[i + 1]]["objectives"][m]    # 计算拥挤度距离：相邻个体目标值的差除以总范围，累加到现有距离上
            population[sorted_front[i]]["distance"] += (next_v - prev_v) / (max_v - min_v)


def _tournament(population: List[Dict]) -> Dict:    # 锦标赛选择函数
    a, b = random.sample(population, 2)    # 随机选择两个个体进行比较
    if a["rank"] < b["rank"]:
        return a
    if b["rank"] < a["rank"]:
        return b
    return a if a["distance"] >= b["distance"] else b    # 等级相同时，选择拥挤度距离更大的个体（多样性更好）


def _repair_unique(route_indices: List[int], candidate_count: int) -> List[int]:   # 修复路线确保景点索引唯一且有效的函数
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


def _ordered_crossover(parent_a: List[int], parent_b: List[int]) -> List[int]:   # 有序交叉函数
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
            experience = EXPERIENCE_RATING_WEIGHT * metrics["rating"] + EXPERIENCE_HOTNESS_WEIGHT * metrics["hotness"]
            objectives = [
                metrics["cost"],   # 目标1：最小化成本
                metrics["distance"],    # 目标2：最小化距离
                -experience,    # 目标3：最大化体验（通过最小化负体验实现）
            ] 
        else:
            penalty = metrics["cost"] - budget if budget > 0 else metrics["cost"]
            objectives = [INFEASIBLE_PENALTY + penalty, INFEASIBLE_PENALTY, INFEASIBLE_PENALTY]
        item["metrics"] = metrics
        item["feasible"] = feasible
        item["objectives"] = objectives


def _next_generation(combined: List[Dict], target_size: int) -> List[Dict]:
    fronts = _fast_non_dominated_sort(combined)      # 对合并种群进行非支配排序
    new_population: List[Dict] = []
    for front in fronts:
        _crowding_distance(combined, front)    # 计算该前沿的拥挤度距离
        if len(new_population) + len(front) <= target_size:
            new_population.extend(combined[idx] for idx in front)
        else:
            ordered = sorted(front, key=lambda i: combined[i]["distance"], reverse=True)
            remain = target_size - len(new_population)
            new_population.extend(combined[idx] for idx in ordered[:remain])
            break
    return new_population    # 返回新一代种群


def run_nsga2(
    spots: List[ScenicSpot],   # 候选景点列表
    days: int,
    budget: float,
    per_day: int = SPOTS_PER_DAY,       # 每天景点数（默认值来自配置）
    pop_size: int = POPULATION_SIZE,
    generations: int = GENERATIONS,
) -> Tuple[List[Dict], int]:                 # 返回Pareto最优解集和路线长度
    route_len = min(days * per_day, len(spots))
    if route_len <= 1:
        return [], 0
    population = _build_population(spots, route_len, pop_size)     # 构建初始种群
    _evaluate_population(population, spots, per_day, budget)     # 评估初始种群

    for _ in range(generations):   # 进行指定代数的进化
        fronts = _fast_non_dominated_sort(population)
        for front in fronts:      # 计算每个前沿的拥挤度距离
            _crowding_distance(population, front)
        offspring = []
        while len(offspring) < pop_size:    # 生成指定数量的子代
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
    feasible = [item for item in first_front if item["feasible"]]      #列表推导式，结果是 List[Dict]
    return feasible if feasible else first_front, route_len       # 优先返回可行解，否则返回第一前沿的所有解


def choose_solution(pareto_set: List[Dict], sensitivities: Dict[str, float], budget: float = 0.0) -> Dict:
    if not pareto_set:   # 提取所有解的各项指标值
        return {}
    costs = [item["metrics"]["cost"] for item in pareto_set]
    distances = [item["metrics"]["distance"] for item in pareto_set]
    hotness = [item["metrics"]["hotness"] for item in pareto_set]
    ratings = [item["metrics"]["rating"] for item in pareto_set]
# 对各项指标进行归一化处理（转换到0-1范围）
    n_cost = _normalize(costs)
    n_distance = _normalize(distances)
    n_hot = _normalize(hotness)
    n_rating = _normalize(ratings)
    spend_target = BUDGET_TARGET_RATIO if budget > 0 else 0.0

    best_idx = 0
    best_score = float("inf")
    for i in range(len(pareto_set)):
        spend_ratio = (costs[i] / budget) if budget > 0 else 0.0
        spend_gap = abs(spend_ratio - spend_target) if budget > 0 else 0.0
        utility = (
            sensitivities["price"] * n_cost[i]   # 价格敏感度 × 归一化成本
            + sensitivities["distance"] * n_distance[i]      # 距离敏感度 × 归一化距离
            - sensitivities["hotness"] * n_hot[i]     # 热度偏好 × 归一化热度（负号表示正面因素）
            - sensitivities["rating"] * n_rating[i]    # 评分偏好 × 归一化评分（负号表示正面因素）
            + SPEND_GAP_PENALTY_WEIGHT * spend_gap       # 花费差距惩罚权重 × 花费差距
        )
        if utility < best_score:
            best_score = utility
            best_idx = i
    return pareto_set[best_idx]

 # 计算效用分数（utility score），这是一个加权组合：
        # - 价格和距离是负面因素（值越大越不好），所以直接相加
        # - 热度和评分是正面因素（值越大越好），所以取负号
        # - 花费差距惩罚项鼓励接近目标预算使用率
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
        result.append(    # 构建景点信息字典并添加到结果列表
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

