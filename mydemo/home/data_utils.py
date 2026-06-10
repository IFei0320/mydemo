"""
数据解析和处理工具函数

包含景点数据解析、坐标处理、距离计算、城市消费档位等通用工具函数。
"""
import math
import re
from typing import Dict, Tuple

# ── 城市消费档位参数表 ──────────────────────────────────────────────
# 档位由城市经济发展水平、旅游消费指数综合判定，用于估算每日生活成本。
# 餐费按每顿正餐估算，住宿按经济型单人每晚，交通按市内日均。

_CITY_TIER_TABLE: Dict[str, str] = {
    # H 档：一线/超一线城市，消费较高
    "北京": "H", "上海": "H", "深圳": "H", "广州": "H",
    # M 档：新一线/省会/热门旅游城市
    "杭州": "M", "南京": "M", "成都": "M", "重庆": "M",
    "武汉": "M", "西安": "M", "长沙": "M", "厦门": "M",
    "苏州": "M", "天津": "M", "青岛": "M", "大连": "M",
    "三亚": "M", "丽江": "M", "昆明": "M", "哈尔滨": "M",
    # L 档：二三线城市，消费较低
    "济南": "L", "洛阳": "L", "开封": "L", "南昌": "L",
    "贵阳": "L", "兰州": "L", "银川": "L", "桂林": "L",
    "镇江": "L", "扬州": "L", "绍兴": "L", "九江": "L",
    "黄山": "L", "张家界": "L", "拉萨": "L", "呼和浩特": "L",
}

def get_city_tier(city: str) -> str:
    """根据城市名返回消费档位 H/M/L，未收录城市默认 M"""
    key = (city or "").replace("市", "").strip()
    return _CITY_TIER_TABLE.get(key, "M")


def compute_living_budget(tier: str, days: int, trip_type: str = "overnight") -> Dict:
    """按城市档位和行程类型估算单人每日生活成本（餐饮+住宿+交通）。

    Args:
        tier: 城市消费档位，H(高)/M(中)/L(低)
        days: 行程天数
        trip_type: overnight(过夜游含住宿) / daytrip(当日往返) / local(本地已有住处)

    Returns:
        tier_label: 档位中文名
        meal_per_meal: 每顿正餐参考价(元)
        hotel_per_night: 每晚住宿参考价(元)
        transport_per_day: 每日市内交通参考价(元)
        daily_living: 日均生活成本(元)
        total_living: 全程生活成本合计(元)
        hotel_nights: 住宿晚数
    """
    from home.config import MEALS_PER_DAY, TIER_LABELS, TIER_PARAMS

    params = TIER_PARAMS.get(tier, TIER_PARAMS["M"])
    meal_per_day = params["meal"] * MEALS_PER_DAY
    transport_per_day = params["transport"]

    if trip_type in ("daytrip", "local"):
        hotel_nights = 0
        daily = meal_per_day + transport_per_day
        total = daily * days
    else:
        hotel_nights = max(0, days - 1)
        daily = meal_per_day + transport_per_day
        total = daily * days + params["hotel"] * hotel_nights

    return {
        "tier": tier,
        "tier_label": TIER_LABELS.get(tier, "中等消费"),
        "meal_per_meal": params["meal"],
        "hotel_per_night": params["hotel"],
        "transport_per_day": transport_per_day,
        "daily_living": round(total / days) if days > 0 else 0,
        "total_living": round(total),
        "hotel_nights": hotel_nights,
    }


def assess_feasibility(budget: float, total_estimate: float) -> Dict:
    """判定门票预算能否覆盖全程预估（门票 + 食宿交通）。

    Args:
        budget: 用户输入的门票预算
        total_estimate: 门票实际 + 食宿交通预估的合计

    Returns:
        level: insufficient(不足) / tight(偏紧) / sufficient(充裕)
        label: 中文标签
        css_class: 前端样式类
        ratio: 覆盖率(budget / total_estimate)
        gap: 缺口(负数为不足金额，正数为余量)
    """
    from home.config import FEASIBILITY_MAP

    if total_estimate <= 0:
        ratio = 1.0
    else:
        ratio = budget / total_estimate

    if ratio < 0.6:
        level = "insufficient"
    elif ratio < 1.0:
        level = "tight"
    else:
        level = "sufficient"

    info = FEASIBILITY_MAP[level]
    return {
        "level": level,
        "label": info["label"],
        "css_class": info["css_class"],
        "ratio": round(ratio, 2),
        "gap": round(budget - total_estimate),
    }

SEASON_KEYWORDS = {
    "spring": ["花", "樱", "桃", "杜鹃", "踏青"],
    "summer": ["漂流", "避暑", "峡谷", "水", "海", "湖"],
    "autumn": ["红叶", "银杏", "秋", "古镇", "层林"],
    "winter": ["雪", "冰", "温泉", "滑雪", "雾凇"],
}

CHINA_LON_MIN, CHINA_LON_MAX = 73.0, 136.0
CHINA_LAT_MIN, CHINA_LAT_MAX = 3.0, 54.0


def _safe_float(raw_value, default=0.0) -> float:
    """安全地将任意值转换为浮点数"""
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
    """解析价格字符串，返回浮点数"""
    if raw_value is None:
        return 0.0
    value = str(raw_value).strip()
    if not value or value == "免费":
        return 0.0
    return max(_safe_float(value, 0.0), 0.0)


def _parse_distance_km(raw_value) -> float:
    """解析距离字符串，统一转换为公里"""
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
    """使用 Haversine 公式计算两点间的球面距离（公里）"""
    lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    return 6371 * c


def _is_valid_china_coord(lon: float, lat: float) -> bool:
    """检查坐标是否在中国境内的粗略范围"""
    return CHINA_LON_MIN <= lon <= CHINA_LON_MAX and CHINA_LAT_MIN <= lat <= CHINA_LAT_MAX


def _normalize_coord_pair(lon_raw, lat_raw) -> Tuple[float, float]:
    """标准化坐标对，过滤异常值"""
    lon = _safe_float(lon_raw, 0.0)
    lat = _safe_float(lat_raw, 0.0)
    if not lon or not lat:
        return 0.0, 0.0
    
    if _is_valid_china_coord(lon, lat):
        return lon, lat
    
    if _is_valid_china_coord(lat, lon):
        return lat, lon
    
    return 0.0, 0.0


def dedup_by_name(queryset):
    """按 name 去重，保留排在前面的那条（先 order_by 再调用）"""
    seen = set()
    result = []
    for obj in queryset:
        if obj.name not in seen:
            seen.add(obj.name)
            result.append(obj)
    return result


def _season_bonus(tags: str, season: str) -> float:
    """根据季节和标签计算季节匹配加成"""
    keywords = SEASON_KEYWORDS.get(season, [])
    if not keywords:
        return 0.0
    text = tags or ""
    hits = sum(1 for item in keywords if item in text)
    return min(hits * 0.1, 0.4)
