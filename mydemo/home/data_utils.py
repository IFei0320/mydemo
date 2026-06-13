"""
数据解析和处理工具函数

包含景点数据解析、坐标处理、距离计算、城市消费档位等通用工具函数。
"""
import math  
import re                             # 导入正则表达式模块，用于字符串模式匹配
from typing import Dict, Tuple         # 导入类型提示，用于函数参数和返回值类型声明

# ── 城市消费档位参数表 ──────────────────────────────────────────────
# 档位由城市经济发展水平、旅游消费指数综合判定，用于估算每日生活成本。
# 餐费按每顿正餐估算，住宿按经济型单人每晚，交通按市内日均。

_CITY_TIER_TABLE: Dict[str, str] = {  # 定义城市消费档位字典，键为城市名，值为档位(H/M/L)
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

def get_city_tier(city: str) -> str:                             # 根据城市名返回消费档位 H/M/L，未收录城市默认 M
    """根据城市名返回消费档位 H/M/L，未收录城市默认 M"""
    key = (city or "").replace("市", "").strip()                # 清理城市名：去除"市"字和空白字符
    return _CITY_TIER_TABLE.get(key, "M")                      # 从字典中获取档位，如果找不到则返回默认值"M"


def compute_living_budget(tier: str, days: int, trip_type: str = "overnight") -> Dict:      # 按城市档位和行程类型估算单人每日生活成本（餐饮+住宿+交通）
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
    from home.config import MEALS_PER_DAY, TIER_LABELS, TIER_PARAMS        # 导入配置常量：每日餐数、档位标签、档位参数

    params = TIER_PARAMS.get(tier, TIER_PARAMS["M"])                      # 获取对应档位的参数，如果找不到则使用M档参数
    meal_per_day = params["meal"] * MEALS_PER_DAY                               # 计算每日餐饮费用（每餐价格 × 每日餐数）
    transport_per_day = params["transport"]                                              # 获取每日交通费用

    if trip_type in ("daytrip", "local"):  # 如果是当日往返或本地游（不需要住宿）
        hotel_nights = 0  # 住宿晚数为0
        daily = meal_per_day + transport_per_day  # 日均成本 = 餐饮 + 交通
        total = daily * days  # 总成本 = 日均成本 × 天数
    else:  # 如果是过夜游（需要住宿）
        hotel_nights = max(0, days - 1)  # 住宿晚数 = 天数 - 1（第一天到达，最后一天离开）
        daily = meal_per_day + transport_per_day  
        total = daily * days + params["hotel"] * hotel_nights  # 总成本 = 日均成本×天数 + 住宿费×晚数

    return {                                                                       # 返回预算详情字典
        "tier": tier,  # 城市档位代码
        "tier_label": TIER_LABELS.get(tier, "中等消费"),  # 档位中文标签
        "meal_per_meal": params["meal"],  
        "hotel_per_night": params["hotel"], 
        "transport_per_day": transport_per_day,  
        "daily_living": round(total / days) if days > 0 else 0,  # 日均生活成本（四舍五入取整）
        "total_living": round(total),  # 全程生活成本合计（四舍五入取整）
        "hotel_nights": hotel_nights,  
    }


def assess_feasibility(budget: float, total_estimate: float) -> Dict:  # 判定门票预算能否覆盖全程预估（门票 + 食宿交通）
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
    from home.config import FEASIBILITY_MAP, FEASIBILITY_RATIO_SUFFICIENT, FEASIBILITY_RATIO_TIGHT  # 导入可行性评估配置

    if total_estimate <= 0: 
        ratio = 1.0  
    else:  # 正常情况
        ratio = budget / total_estimate  # 计算覆盖率（预算/总预估）

    if ratio < FEASIBILITY_RATIO_TIGHT:  # 如果覆盖率低于紧张阈值
        level = "insufficient"  # 标记为"不足"
    elif ratio < FEASIBILITY_RATIO_SUFFICIENT:  # 如果覆盖率低于充裕阈值但高于紧张阈值
        level = "tight"  # 标记为"偏紧"
    else:  # 如果覆盖率高于充裕阈值
        level = "sufficient"  # 标记为"充裕"

    info = FEASIBILITY_MAP[level]  # 获取对应级别的详细信息
    return {  # 返回可行性评估结果字典
        "level": level,  # 可行性级别代码
        "label": info["label"],  # 中文标签
        "css_class": info["css_class"],  # 前端CSS样式类
        "ratio": round(ratio, 2),  # 覆盖率（保留2位小数）
        "gap": round(budget - total_estimate),  # 资金缺口（四舍五入取整，负数表示不足，正数表示余量）
    }

SEASON_KEYWORDS = {  # 定义季节关键词字典，用于判断景点是否适合特定季节
    "spring": ["花", "樱", "桃", "杜鹃", "踏青"],  # 春季关键词：花卉、樱花、桃花、杜鹃花、踏青活动
    "summer": ["漂流", "避暑", "峡谷", "水", "海", "湖"],  # 夏季关键词：漂流、避暑、峡谷、水上活动、海边、湖边
    "autumn": ["红叶", "银杏", "秋", "古镇", "层林"],  # 秋季关键词：红叶、银杏、秋色、古镇、层林尽染
    "winter": ["雪", "冰", "温泉", "滑雪", "雾凇"],  # 冬季关键词：雪景、冰雕、温泉、滑雪、雾凇景观
}

CHINA_LON_MIN, CHINA_LON_MAX = 73.0, 136.0  # 中国经度范围：东经73°到136°
CHINA_LAT_MIN, CHINA_LAT_MAX = 3.0, 54.0  # 中国纬度范围：北纬3°到54°


def _safe_float(raw_value, default=0.0) -> float:  # 安全地将任意值转换为浮点数
    """安全地将任意值转换为浮点数"""
    if raw_value is None:  # 如果输入值为None
        return default  # 返回默认值
    value = str(raw_value).strip()  # 转换为字符串并去除首尾空白
    if not value:  # 如果字符串为空
        return default  # 返回默认值
    try:
        return float(value)  # 尝试直接转换为浮点数
    except (TypeError, ValueError):  # 如果转换失败（类型错误或值错误）
        digits = re.findall(r"-?\d+\.?\d*", value)  # 使用正则表达式提取数字部分
        if digits:  # 如果找到数字
            try:
                return float(digits[0])  # 返回第一个找到的数字
            except ValueError:  # 如果转换仍然失败
                return default  # 返回默认值
    return default  # 其他情况返回默认值


def _parse_price(raw_value) -> float:  # 解析价格字符串，返回浮点数
 
    if raw_value is None:  # 如果输入值为None
        return 0.0  # 返回0.0
    value = str(raw_value).strip()  # 转换为字符串并去除首尾空白
    if not value or value == "免费":  # 如果字符串为空或等于"免费"
        return 0.0  # 返回0.0（免费景点）
    return max(_safe_float(value, 0.0), 0.0)  


def _parse_distance_km(raw_value) -> float:  # 解析距离字符串，统一转换为公里
    """解析距离字符串，统一转换为公里"""
    if raw_value is None:  # 如果输入值为None   返回0.0
        return 0.0  
    value = str(raw_value).strip()  # 转换为字符串并去除首尾空白
    if not value:  
        return 0.0  
    km = _safe_float(value, 0.0)  # 安全转换为浮点数
    if "m" in value and "km" not in value.lower():  
        km = km / 1000.0  
    return max(km, 0.0)  


def _haversine_km(lon1, lat1, lon2, lat2) -> float:  # 使用 Haversine 公式计算两点间的球面距离（公里）
    """使用 Haversine 公式计算两点间的球面距离（公里）"""
    lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])  # 将所有经纬度从度数转换为弧度
    dlon = lon2 - lon1  
    dlat = lat2 - lat1  
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2  # Haversine公式中间变量a
    c = 2 * math.asin(math.sqrt(a))  # Haversine公式中间变量c（圆心角）
    return 6371 * c  


def _is_valid_china_coord(lon: float, lat: float) -> bool:                                        # 检查坐标是否在中国境内的粗略范围
   
    return CHINA_LON_MIN <= lon <= CHINA_LON_MAX and CHINA_LAT_MIN <= lat <= CHINA_LAT_MAX       # 检查经纬度是否在中国范围内


def _normalize_coord_pair(lon_raw, lat_raw) -> Tuple[float, float]:  # 标准化坐标对，过滤异常值
    """标准化坐标对，过滤异常值"""
    lon = _safe_float(lon_raw, 0.0)  # 安全转换经度
    lat = _safe_float(lat_raw, 0.0)  # 安全转换纬度
    if not lon or not lat:  # 如果经度或纬度为0（无效坐标）
        return 0.0, 0.0  # 返回(0.0, 0.0)
    
    if _is_valid_china_coord(lon, lat):  # 如果坐标顺序正确且在中国范围内
        return lon, lat  # 返回原始坐标
    
    if _is_valid_china_coord(lat, lon):  # 如果坐标可能颠倒了（经纬度互换后在中国范围内）
        return lat, lon  # 返回互换后的坐标
    
    return 0.0, 0.0  # 如果都不在中国范围内，返回(0.0, 0.0)


def dedup_by_name(queryset):  # 按 name 去重，保留排在前面的那条（先 order_by 再调用）
    """按 name 去重，保留排在前面的那条（先 order_by 再调用）"""
    seen = set()  # 创建集合用于记录已见过的名称
    result = []  # 创建列表用于存储去重后的结果
    for obj in queryset:  # 遍历查询集中的每个对象
        if obj.name not in seen:  # 如果对象名称还未出现过
            seen.add(obj.name)  # 将名称添加到已见集合
            result.append(obj)  # 将对象添加到结果列表
    return result  # 返回去重后的列表


def _season_bonus(tags: str, season: str) -> float:  # 根据季节和标签计算季节匹配加成
    """根据季节和标签计算季节匹配加成"""
    keywords = SEASON_KEYWORDS.get(season, [])  # 获取对应季节的关键词列表
    if not keywords:  # 如果没有关键词（季节无效）
        return 0.0  # 返回0.0（无加成）
    text = tags or ""  # 获取标签文本，如果为None则用空字符串
    hits = sum(1 for item in keywords if item in text)  # 计算标签中包含的季节关键词数量
    return min(hits * 0.1, 0.4)  # 返回加成值：每个关键词0.1分，最多0.4分（限制上限）