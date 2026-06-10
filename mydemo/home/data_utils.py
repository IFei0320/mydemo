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

_TIER_PARAMS = {
    "H": {"meal": 35, "hotel": 250, "transport": 30},   # 日合计约 350
    "M": {"meal": 25, "hotel": 150, "transport": 20},   # 日合计约 220
    "L": {"meal": 15, "hotel": 80,  "transport": 15},   # 日合计约 130
}


def get_city_tier(city: str) -> str:
    """根据城市名返回消费档位 H/M/L，未收录城市默认 M"""
    key = (city or "").replace("市", "").strip()
    return _CITY_TIER_TABLE.get(key, "M")


def compute_living_budget(tier: str, days: int, trip_type: str = "overnight") -> Dict:
    """计算每日生活参考预算。trip_type: overnight(过夜游) / daytrip(当日往返) / local(本地)"""
    params = _TIER_PARAMS.get(tier, _TIER_PARAMS["M"])
    meal_per_day = params["meal"] * 2.5    # 一日 2.5 顿正餐
    transport_per_day = params["transport"]

    if trip_type == "daytrip":
        daily = meal_per_day + transport_per_day
        total = daily * days
        hotel_nights = 0
    elif trip_type == "local":
        daily = meal_per_day + transport_per_day
        total = daily * days
        hotel_nights = 0
    else:  # overnight（默认）
        hotel_nights = max(0, days - 1)     # 首日不需要前一晚住宿
        daily = meal_per_day + transport_per_day
        total = daily * days + params["hotel"] * hotel_nights

    return {
        "tier": tier,
        "tier_label": {"H": "高消费", "M": "中等消费", "L": "低消费"}.get(tier, "中等消费"),
        "meal_per_meal": params["meal"],
        "hotel_per_night": params["hotel"],
        "transport_per_day": transport_per_day,
        "daily_living": round(total / days) if days > 0 else 0,
        "total_living": round(total),
        "hotel_nights": hotel_nights,
    }


def assess_feasibility(remaining: float, total_living: float) -> Dict:
    """根据剩余预算和生活参考预算判定可行性"""
    if total_living <= 0:
        ratio = 1.0
    else:
        ratio = remaining / total_living
    if ratio < 0.6:
        level = "insufficient"
        label = "预算不足"
        css_class = "badge-red"
    elif ratio < 1.0:
        level = "tight"
        label = "预算偏紧"
        css_class = "badge-orange"
    else:
        level = "sufficient"
        label = "预算充裕"
        css_class = "badge-green"
    return {
        "level": level,
        "label": label,
        "css_class": css_class,
        "ratio": round(ratio, 2),
        "gap": round(remaining - total_living),
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


def _season_bonus(tags: str, season: str) -> float:
    """根据季节和标签计算季节匹配加成"""
    keywords = SEASON_KEYWORDS.get(season, [])
    if not keywords:
        return 0.0
    text = tags or ""
    hits = sum(1 for item in keywords if item in text)
    return min(hits * 0.1, 0.4)
