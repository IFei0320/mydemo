import math
import random
import re
import json
import html
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Tuple

from openai import OpenAI


SEASON_KEYWORDS = {
    "spring": ["花", "樱", "桃", "杜鹃", "踏青"],
    "summer": ["漂流", "避暑", "峡谷", "水", "海", "湖"],
    "autumn": ["红叶", "银杏", "秋", "古镇", "层林"],
    "winter": ["雪", "冰", "温泉", "滑雪", "雾凇"],
}

# 粗略中国经纬度边界，用于过滤异常点（例如 0,0）
CHINA_LON_MIN, CHINA_LON_MAX = 73.0, 136.0
CHINA_LAT_MIN, CHINA_LAT_MAX = 3.0, 54.0


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


def _safe_float(raw_value, default=0.0) -> float:
    if raw_value is None:
        return default
    value = str(raw_value).strip()
    if not value:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        digits = re.findall(r"-?\d+\.?\d*", value)
        if digits:
            try:
                return float(digits[0])
            except ValueError:
                return default
    return default


def _parse_price(raw_value) -> float:
    if raw_value is None:
        return 0.0
    value = str(raw_value).strip()
    if not value or value == "免费":
        return 0.0
    return max(_safe_float(value, 0.0), 0.0)


def _parse_distance_km(raw_value) -> float:
    if raw_value is None:
        return 0.0
    value = str(raw_value).strip()
    if not value:
        return 0.0
    km = _safe_float(value, 0.0)
    if "m" in value and "km" not in value.lower():
        km = km / 1000.0
    return max(km, 0.0)


def _haversine_km(lon1, lat1, lon2, lat2) -> float:
    lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    return 6371 * c


def _is_valid_china_coord(lon: float, lat: float) -> bool:
    return CHINA_LON_MIN <= lon <= CHINA_LON_MAX and CHINA_LAT_MIN <= lat <= CHINA_LAT_MAX


def _normalize_coord_pair(lon_raw, lat_raw) -> Tuple[float, float]:
    lon = _safe_float(lon_raw, 0.0)
    lat = _safe_float(lat_raw, 0.0)
    if not lon or not lat:
        return 0.0, 0.0

    # 情况1：正常中国坐标
    if _is_valid_china_coord(lon, lat):
        return lon, lat

    # 情况2：疑似经纬度颠倒（很多脏数据会把 121/31 反着存）
    if _is_valid_china_coord(lat, lon):
        return lat, lon

    return 0.0, 0.0


def _normalize(values: List[float]) -> List[float]:
    if not values:
        return []
    min_v, max_v = min(values), max(values)
    if math.isclose(min_v, max_v):
        return [0.5 for _ in values]
    return [(v - min_v) / (max_v - min_v) for v in values]


def _load_travel_knowledge() -> List[Dict]:
    knowledge_path = Path(__file__).resolve().parent / "travel_knowledge.json"
    if not knowledge_path.exists():
        return []
    try:
        payload = json.loads(knowledge_path.read_text(encoding="utf-8"))
        return payload.get("items", []) if isinstance(payload, dict) else []
    except Exception:
        return []


def retrieve_knowledge_cards(city: str, route_data: List[Dict], max_cards: int = 10) -> List[Dict]:
    items = _load_travel_knowledge()
    if not items:
        return []
    city_norm = (city or "").replace("市", "").strip().lower()
    matched: List[Dict] = []
    seen = set()
    for route in route_data:
        spot_name = str(route.get("name", "")).strip()
        if not spot_name:
            continue
        spot_lower = spot_name.lower()
        for item in items:
            item_city = str(item.get("city", "")).replace("市", "").strip().lower()
            if item_city != city_norm:
                continue
            keywords = item.get("spot_keywords", []) or []
            hit = any((kw and (kw.lower() in spot_lower or spot_lower in kw.lower())) for kw in keywords)
            if not hit:
                continue
            key = f"{item_city}|{','.join(keywords)}"
            if key in seen:
                continue
            seen.add(key)
            matched.append(
                {
                    "spot_name": spot_name,
                    "best_time": item.get("best_time", ""),
                    "booking_tip": item.get("booking_tip", ""),
                    "transport_tip": item.get("transport_tip", ""),
                    "pitfalls": item.get("pitfalls", []),
                    "crowd_level": item.get("crowd_level", ""),
                    "duration_suggestion": item.get("duration_suggestion", ""),
                }
            )
            if len(matched) >= max_cards:
                return matched
    return matched


def _season_bonus(tags: str, season: str) -> float:
    keywords = SEASON_KEYWORDS.get(season, [])
    if not keywords:
        return 0.0
    text = tags or ""
    hits = sum(1 for item in keywords if item in text)
    return min(hits * 0.1, 0.4)


def build_candidates(queryset, city: str, season: str) -> List[ScenicSpot]:
    spots: List[ScenicSpot] = []
    city_qs = queryset.filter(city__icontains=city)
    # 先精确匹配“上海” vs “上海市”，再补充包含匹配，降低跨城误入概率
    primary = [row for row in city_qs if str(row.city or "").replace("市", "") == city.replace("市", "")]
    source_rows = primary if len(primary) >= 9 else list(city_qs)
    for row in source_rows:
        lon, lat = _normalize_coord_pair(row.longitude, row.latitude)
        if not lon or not lat:
            continue
        rating = _safe_float(row.rating, 0.0)
        hotness = _safe_float(row.popularity_score, 0.0)
        reviews = _safe_float(row.review_count, 0.0)
        tags = row.tags or ""
        spots.append(
            ScenicSpot(
                name=row.name or "未知景点",
                city=row.city or city,
                area=row.area or "",
                tags=tags,
                rating=rating + _season_bonus(tags, season),
                hotness=hotness,
                reviews=reviews,
                cost=_parse_price(row.actual_price),
                lon=lon,
                lat=lat,
                center_distance_km=_parse_distance_km(row.distance_from_center),
            )
        )
    return spots


def _route_distance_km(route_indices: List[int], spots: List[ScenicSpot], per_day: int) -> float:
    total = 0.0
    for i, idx in enumerate(route_indices):
        cur = spots[idx]
        total += cur.center_distance_km
        is_new_day = i % per_day == 0
        if i > 0 and not is_new_day:
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
    a = random.choice(population)
    b = random.choice(population)
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


def _mutate(route_indices: List[int], candidate_count: int, mutation_rate: float = 0.2) -> List[int]:
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
    per_day: int = 3,
    pop_size: int = 60,
    generations: int = 70,
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
        _evaluate_population(population, spots, per_day, budget)

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


def build_route_payload(best_solution: Dict, spots: List[ScenicSpot], days: int, per_day: int = 3) -> List[Dict]:
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
                "features": f"{spot.area}，评分{spot.rating:.1f}，热度{spot.hotness:.1f}",
                "longitude": round(spot.lon, 6),
                "latitude": round(spot.lat, 6),
                "estimated_cost": "免费" if spot.cost <= 0 else f"{int(round(spot.cost))}元",
            }
        )
    return result


def call_ai_refiner(
    city: str,
    season: str,
    days: int,
    budget: float,
    route_data: List[Dict],
    knowledge_cards: List[Dict],
) -> str:
    prompt = (
        "你是资深旅游策划师。请基于给定的结构化行程，输出详细攻略。"
        "要求：1) 按天分段；2) 每个景点说明亮点与游玩建议；3) 给出交通衔接建议；"
        "4) 给出预算提醒和避坑建议；5) 用中文，结构清晰；"
        "6) 只输出纯文本，不要 Markdown，不要星号，不要表格线；"
        "7) 优先使用我提供的“本地知识卡（RAG）”，把最佳时段、预约提示、避坑点融入内容。"
    )
    user_content = {
        "city": city,
        "season": season,
        "days": days,
        "budget": budget,
        "route": route_data,
        "local_knowledge_cards": knowledge_cards,
    }
    try:
        client = OpenAI(
            api_key="sk-d2e0034a6f264140a8017b1e98359312",
            base_url="https://api.deepseek.com",
        )
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": str(user_content)},
            ],
            max_tokens=1200,
            stream=False,
            extra_body={"thinking": {"type": "disabled"}},
        )
        return response.choices[0].message.content or ""
    except Exception as exc:
        return f"AI润色暂时不可用，已返回算法行程结果。错误信息：{exc}"


def call_ai_html_report(
    city: str,
    season: str,
    days: int,
    budget: float,
    route_data: List[Dict],
    metrics: Dict,
    knowledge_cards: List[Dict],
) -> str:
    # 固定模板渲染，避免模型输出超长HTML被截断
    route_data = route_data or []
    metrics = metrics or {}
    knowledge_cards = knowledge_cards or []

    day_groups: Dict[int, List[Dict]] = {}
    for row in route_data:
        match = re.search(r"第(\d+)天", str(row.get("visit_time", "")))
        day_no = int(match.group(1)) if match else 1
        day_groups.setdefault(day_no, []).append(row)

    day_cards_html = []
    day_budget_rows = []
    total_cost = 0.0
    traffic_rows = []
    for day_no in sorted(day_groups.keys()):
        items = day_groups[day_no]
        row_html = []
        day_cost = 0.0
        for i, item in enumerate(items):
            spot_name = html.escape(str(item.get("name", "")))
            visit_time = html.escape(str(item.get("visit_time", "")))
            features = html.escape(str(item.get("features", "")))
            estimated_cost = str(item.get("estimated_cost", "免费"))
            amount = _safe_float(estimated_cost, 0.0)
            day_cost += amount
            total_cost += amount
            lon = item.get("longitude", "")
            lat = item.get("latitude", "")
            row_html.append(
                f"""
                <div class="spot-card">
                    <div class="spot-title">{spot_name}</div>
                    <div class="spot-meta">{visit_time}</div>
                    <div class="spot-desc">{features}</div>
                    <div class="spot-line"><b>建议停留：</b>1-2小时</div>
                    <div class="spot-line"><b>预计花费：</b>{html.escape(estimated_cost)}</div>
                    <div class="spot-line"><b>坐标：</b>{html.escape(str(lat))}, {html.escape(str(lon))}</div>
                </div>
                """
            )
            if i < len(items) - 1:
                from_name = html.escape(str(item.get("name", "")))
                to_name = html.escape(str(items[i + 1].get("name", "")))
                traffic_rows.append(
                    f"<li><b>{from_name}</b> -> <b>{to_name}</b>：建议优先地铁/公交，若时间紧可打车；以地图App实时导航为准。</li>"
                )
        day_cards_html.append(
            f"""
            <section class="day-block">
              <h3>第{day_no}天行程</h3>
              <div class="spot-grid">{''.join(row_html)}</div>
              <div class="day-summary">当日小结：建议先完成核心景点，再安排拍照/休息时段，避免反复折返。</div>
            </section>
            """
        )
        day_budget_rows.append(f"<tr><td>第{day_no}天</td><td>{day_cost:.2f} 元</td></tr>")

    budget_usage = (total_cost / budget * 100.0) if budget > 0 else 0.0
    risk_text = "预算充足" if (budget <= 0 or total_cost <= budget) else "存在超支风险"

    knowledge_html = []
    for card in knowledge_cards[:12]:
        pitfalls = card.get("pitfalls", []) or []
        pitfalls_text = "；".join(html.escape(str(p)) for p in pitfalls[:3]) if pitfalls else "建议以现场提示为准"
        knowledge_html.append(
            f"""
            <div class="knowledge-item">
              <div class="knowledge-title">{html.escape(str(card.get('spot_name', '')))}</div>
              <div>最佳时段：{html.escape(str(card.get('best_time', '-')))}</div>
              <div>预约提示：{html.escape(str(card.get('booking_tip', '-')))}</div>
              <div>避坑要点：{pitfalls_text}</div>
            </div>
            """
        )

    traffic_html = "".join(traffic_rows) if traffic_rows else "<li>建议以地铁优先，跨区段可打车衔接，以导航实时路况为准。</li>"
    knowledge_section = (
        f"<div class='knowledge-box'>{''.join(knowledge_html)}</div>"
        if knowledge_html
        else "<p class='muted'>本次未命中本地知识卡，建议以官方公告与地图App信息为准。</p>"
    )

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(city)} 行程报告</title>
  <style>
    body {{ font-family: -apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif; margin:0; background:#f5f7fb; color:#1f2937; }}
    .wrap {{ max-width: 1080px; margin: 24px auto; padding: 0 16px; }}
    .header {{ background:#fff; border-radius:12px; padding:18px 20px; box-shadow:0 2px 10px rgba(0,0,0,.06); }}
    h1 {{ margin:0 0 8px; font-size:24px; }}
    .sub {{ color:#6b7280; margin:0; }}
    .grid {{ display:grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap:12px; margin-top:14px; }}
    .card {{ background:#fff; border-radius:12px; padding:14px; box-shadow:0 2px 10px rgba(0,0,0,.05); }}
    .k {{ color:#6b7280; font-size:13px; }}
    .v {{ font-size:18px; font-weight:700; margin-top:4px; }}
    .section {{ background:#fff; border-radius:12px; padding:16px; box-shadow:0 2px 10px rgba(0,0,0,.05); margin-top:14px; }}
    .section h2 {{ margin:0 0 10px; font-size:19px; color:#1677ff; }}
    .day-block {{ border:1px solid #e5e7eb; border-radius:10px; padding:12px; margin-top:10px; }}
    .day-block h3 {{ margin:0 0 8px; font-size:17px; }}
    .spot-grid {{ display:grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap:10px; }}
    .spot-card {{ border:1px solid #e5e7eb; border-radius:8px; padding:10px; background:#fafcff; }}
    .spot-title {{ font-weight:700; margin-bottom:4px; }}
    .spot-meta {{ color:#2563eb; font-size:13px; margin-bottom:6px; }}
    .spot-desc {{ font-size:13px; margin-bottom:6px; }}
    .spot-line {{ font-size:13px; color:#374151; }}
    .day-summary {{ margin-top:8px; color:#374151; font-size:13px; }}
    ul {{ margin:8px 0 0 18px; padding:0; }}
    li {{ margin:6px 0; }}
    table {{ width:100%; border-collapse:collapse; }}
    th, td {{ border:1px solid #e5e7eb; padding:8px 10px; text-align:left; }}
    th {{ background:#f3f4f6; }}
    .risk-ok {{ color:#16a34a; font-weight:700; }}
    .risk-warn {{ color:#dc2626; font-weight:700; }}
    .knowledge-box {{ display:grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap:10px; }}
    .knowledge-item {{ border:1px solid #e5e7eb; border-radius:8px; padding:10px; background:#fffdf7; }}
    .knowledge-title {{ font-weight:700; margin-bottom:4px; }}
    .muted {{ color:#6b7280; }}
    @media (max-width: 900px) {{ .grid, .spot-grid, .knowledge-box {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="header">
      <h1>{html.escape(city)} {html.escape(season)}出行报告</h1>
      <p class="sub">基于NSGA-II多目标优化 + 本地知识库RAG增强，适合答辩展示与落地执行。</p>
      <div class="grid">
        <div class="card"><div class="k">城市</div><div class="v">{html.escape(city)}</div></div>
        <div class="card"><div class="k">季节</div><div class="v">{html.escape(season)}</div></div>
        <div class="card"><div class="k">天数</div><div class="v">{days} 天</div></div>
        <div class="card"><div class="k">预算</div><div class="v">{budget:.2f} 元</div></div>
        <div class="card"><div class="k">预计花费</div><div class="v">{total_cost:.2f} 元</div></div>
        <div class="card"><div class="k">景点数</div><div class="v">{len(route_data)} 个</div></div>
      </div>
    </div>

    <div class="section">
      <h2>行程总览摘要</h2>
      <p>策略：在预算约束下平衡评分、热度与路程，优先保证核心景点覆盖，再优化交通衔接与体验节奏。</p>
      {''.join(day_cards_html)}
    </div>

    <div class="section">
      <h2>交通衔接建议</h2>
      <ul>{traffic_html}</ul>
    </div>

    <div class="section">
      <h2>RAG本地知识卡（命中 {len(knowledge_cards)} 条）</h2>
      {knowledge_section}
    </div>

    <div class="section">
      <h2>注意事项</h2>
      <ul>
        <li>天气与穿搭：春秋季昼夜温差较大，建议叠穿并备轻薄外套。</li>
        <li>预约与排队：热门场馆优先预约，尽量错峰（早场/工作日）。</li>
        <li>财物安全：在人流密集区域注意随身物品，手机与证件分开存放。</li>
        <li>文明游览：遵守景区秩序，拍照时避免影响他人通行。</li>
        <li>导航建议：交通与开放信息可能变化，出发前请以官方公告和地图App实时信息为准。</li>
      </ul>
    </div>

    <div class="section">
      <h2>预算明细</h2>
      <table>
        <thead><tr><th>日期</th><th>预计花费</th></tr></thead>
        <tbody>{''.join(day_budget_rows)}</tbody>
      </table>
      <p style="margin-top:10px;">
        总计：<b>{total_cost:.2f} 元</b>，
        预算利用率：<b>{budget_usage:.1f}%</b>，
        风险评估：<span class="{'risk-ok' if risk_text == '预算充足' else 'risk-warn'}">{risk_text}</span>
      </p>
    </div>

    <div class="section">
      <h2>应急与备选方案</h2>
      <ul>
        <li>雨天：优先博物馆/商圈/室内观景点，户外点顺延到次日。</li>
        <li>拥堵：跨区移动改为地铁优先，压缩非核心打卡点。</li>
        <li>超支：减少高票价项目，增加免费景点与步行线路。</li>
      </ul>
    </div>

    <div class="section">
      <h2>出发前清单</h2>
      <ul>
        <li>证件：身份证、学生证/优惠证件</li>
        <li>设备：充电宝、充电线、耳机</li>
        <li>行前：门票预约截图、酒店/交通订单截图</li>
        <li>工具：离线地图、应急联系人、常用药品</li>
      </ul>
    </div>
  </div>
</body>
</html>"""
