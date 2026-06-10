# -*- coding: utf-8 -*-
"""单次运行脚本的共享基础模块 —— Django 初始化 + 中文字体 + 数据加载 + JSON 保存。"""
import json
import math
import os
import sys
from pathlib import Path

# 确保项目根目录在 Python 路径中
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

# 确保终端中文输出不乱码
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
if sys.stderr.encoding != 'utf-8':
    try:
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mydemo.settings')
django.setup()

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

# ---- 中文字体配置 ----
_FONT_PRIORITY = ["Microsoft YaHei", "SimHei", "STXihei", "SimSun"]
_available_cjk_fonts = [n for n in _FONT_PRIORITY if any(f.name == n for f in fm.fontManager.ttflist)]
if _available_cjk_fonts:
    plt.rcParams["font.sans-serif"] = _available_cjk_fonts + list(plt.rcParams.get("font.sans-serif", []))
plt.rcParams["axes.unicode_minus"] = False

# ---- 输出路径 ----
OUTPUT_DIR = ROOT / "diagrams" / "output"
DATA_DIR = ROOT / "diagrams" / "data"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ---- 常用导入（供各脚本直接 from _base import *） ----
from home.models import TravelInfo
from home.data_utils import _safe_float, _parse_price, _parse_distance_km, _normalize_coord_pair
from home.nsga2_trip_planner import ScenicSpot, run_nsga2


def load_spots(city="上海", limit=200):
    """从数据库加载真实景点数据。"""
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


def _clean(obj):
    """递归把 nan/inf 替换成 None。"""
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean(v) for v in obj]
    return obj


def save_json(name, data):
    path = DATA_DIR / f"{name}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(_clean(data), f, ensure_ascii=False, indent=2)
    print(f"   JSON 已保存 -> {path}")


COLORS = {"nsga2": "#43A047", "greedy": "#1E88E5", "random": "#FB8C00",
           "economy": "#43A047", "balanced": "#1E88E5", "experience": "#E53935"}
