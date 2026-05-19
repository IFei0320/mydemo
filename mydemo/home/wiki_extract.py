import re
from typing import List

LLM_ERROR_MARKERS = [
    "[LLM 调用异常:",
    "No module named 'jiter.jiter'",
    "'NoneType' object has no attribute",
]


def has_llm_error(text: str) -> bool:
    value = text or ""
    return any(marker in value for marker in LLM_ERROR_MARKERS)


def clean_text(text: str) -> str:
    value = (text or "").strip()
    if has_llm_error(value):
        return ""
    return value


def normalize_entity_name(name: str) -> str:
    text = clean_text(name)
    if not text:
        return ""
    text = re.sub(r"^\d+\s*[\.、]\s*", "", text)
    text = re.sub(r"^[（(]?[一二三四五六七八九十]+[)）]\s*", "", text)
    text = re.sub(r"^[①②③④⑤⑥⑦⑧⑨⑩]\s*", "", text)
    return text.strip()


def safe_list(values, limit: int = 12) -> List[str]:
    result: List[str] = []
    for item in values or []:
        text = clean_text(str(item))
        if text and text not in result:
            result.append(text)
        if len(result) >= limit:
            break
    return result


def slugify(name: str) -> str:
    value = re.sub(r"[^\w一-鿿\-]+", "-", name.strip().lower())
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value or "untitled"


def extract_title(content: str, fallback: str) -> str:
    for line in content.splitlines():
        text = line.strip()
        if text.startswith("#"):
            return text.lstrip("#").strip()
    return fallback


def extract_focus_lines(content: str, limit: int = 12) -> List[str]:
    patterns = ["交通", "门票", "开放", "预约", "避雷", "预算", "路线", "时间", "推荐"]
    selected: List[str] = []
    for line in content.splitlines():
        text = line.strip()
        if not text:
            continue
        if any(token in text for token in patterns):
            selected.append(text)
        if len(selected) >= limit:
            break
    if selected:
        return selected
    chunks = [line.strip() for line in content.splitlines() if line.strip()]
    return chunks[: min(limit, len(chunks))]


def extract_month_signals(content: str) -> List[str]:
    month_hits = re.findall(r"(1[0-2]|[1-9])月", content)
    unique = []
    for m in month_hits:
        token = f"{int(m)}月"
        if token not in unique:
            unique.append(token)
    return unique[:8]


def season_to_months(season: str) -> List[str]:
    mapping = {
        "spring": ["3月", "4月", "5月"],
        "summer": ["6月", "7月", "8月"],
        "autumn": ["9月", "10月", "11月"],
        "winter": ["12月", "1月", "2月"],
    }
    return mapping.get((season or "").strip().lower(), [])


def infer_budget_level(text: str) -> str:
    t = (text or "").lower()
    if any(k in t for k in ["免费", "低价", "便宜", "性价比"]):
        return "low"
    if any(k in t for k in ["高价", "贵", "票价较高", "消费高", "溢价"]):
        return "high"
    return "medium"


def infer_transport_mode(text: str) -> str:
    t = text or ""
    if "地铁" in t:
        return "metro"
    if "公交" in t:
        return "bus"
    if "打车" in t or "出租车" in t:
        return "taxi"
    if "步行" in t:
        return "walk"
    return "mixed"


def infer_crowd_level(text: str) -> str:
    t = text or ""
    if "极高" in t or "人流量极大" in t or "排队" in t:
        return "high"
    if "较少" in t or "低" in t:
        return "low"
    return "medium"


def infer_best_time(text: str) -> str:
    t = text or ""
    if "夜景" in t or "日落" in t or "亮灯" in t:
        return "傍晚至夜间"
    if "上午" in t:
        return "工作日上午"
    return "白天错峰时段"


def extract_pitfalls(text: str, limit: int = 3) -> List[str]:
    lines = [ln.strip("- ").strip() for ln in (text or "").splitlines() if ln.strip()]
    result = []
    for ln in lines:
        if any(k in ln for k in ["避雷", "避坑", "注意", "不要", "排队", "拥挤"]):
            result.append(ln[:60])
        if len(result) >= limit:
            break
    if not result:
        return ["避开高峰排队时段", "注意景区临时公告", "热门点位提前到达"]
    return result


def extract_spot_names(content: str, limit: int = 10) -> List[str]:
    spot_names: List[str] = []
    for line in content.splitlines():
        text = line.strip().lstrip("#").strip()
        if not text:
            continue
        if "——" in text:
            name = text.split("——", 1)[0].strip(" -：:")
            if 1 < len(name) <= 30 and name not in spot_names:
                spot_names.append(name)
        elif text.startswith("###"):
            name = text.lstrip("#").strip().split(" ")[0].strip("：:")
            if 1 < len(name) <= 30 and name not in spot_names:
                spot_names.append(name)
        if len(spot_names) >= limit:
            break
    return spot_names


def extract_concepts(content: str, limit: int = 6) -> List[str]:
    concept_rules = {
        "亲子出行": ["亲子", "儿童", "小朋友", "家庭"],
        "夜景路线": ["夜景", "亮灯", "日落", "晚上"],
        "交通换乘": ["地铁", "换乘", "公交", "打车", "交通"],
        "预约策略": ["预约", "购票", "抢票", "官方渠道"],
        "预算分层": ["预算", "人均", "省钱", "花费", "门票"],
        "避坑指南": ["避雷", "避坑", "注意事项", "陷阱", "不要"],
        "历史人文": ["历史", "博物馆", "纪念馆", "人文", "故居"],
        "自然生态": ["公园", "植物园", "森林", "湿地", "自然"],
        "游玩时段": ["上午", "下午", "最佳时间", "时段", "工作日"],
    }
    hits: List[str] = []
    text = content.lower()
    for concept, keywords in concept_rules.items():
        if any(k.lower() in text for k in keywords):
            hits.append(concept)
        if len(hits) >= limit:
            break
    return hits
