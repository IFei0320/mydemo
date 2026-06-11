"""NSGA-II 智能路线规划系统 —— 配置常量"""

# ── NSGA-II 算法参数 ──────────────────────────────────────────────
SPOTS_PER_DAY = 3        # 每天景点数量（上午/中午/下午）
POPULATION_SIZE = 40      # 种群规模
GENERATIONS = 30          # 进化代数
MUTATION_RATE = 0.2       # 变异概率
PLAN_CACHE_TTL = 600      # 方案缓存有效期（秒）
RECENT_PLAN_LIMIT = 12    # 最近方案记录上限
BUDGET_TARGET_RATIO = 0.75  # 均衡型方案的目标预算利用率
SPEND_GAP_PENALTY_WEIGHT = 0.15  # choose_solution 中预算偏离惩罚权重
INFEASIBLE_PENALTY = 1e9  # 不可行解的目标惩罚值

# ── 体验目标融合权重 ──────────────────────────────────────────────
EXPERIENCE_RATING_WEIGHT = 0.6  # 综合体验中评分的权重
EXPERIENCE_HOTNESS_WEIGHT = 0.4  # 综合体验中热度的权重

# ── AI 调用参数 ────────────────────────────────────────────────────
AI_MODEL = "deepseek-v4-flash"
AI_MAX_TOKENS = 3200
AI_BASE_URL = "https://api.deepseek.com"  # LLM API 默认 Base URL

# ── 城市消费档位参数 ──────────────────────────────────────────────
TIER_PARAMS = {
    "H": {"meal": 35, "hotel": 250, "transport": 30},
    "M": {"meal": 25, "hotel": 150, "transport": 20},
    "L": {"meal": 15, "hotel": 80,  "transport": 15},
}
TIER_LABELS = {"H": "高消费", "M": "中等消费", "L": "低消费"}
MEALS_PER_DAY = 2.5  # 每日正餐顿数（用于生活成本估算）

# ── 预算可行性阈值 ──────────────────────────────────────────────────
FEASIBILITY_RATIO_TIGHT = 0.6  # insufficient / tight 分界
FEASIBILITY_RATIO_SUFFICIENT = 1.0  # tight / sufficient 分界

# ── 可行性标签 ────────────────────────────────────────────────────
FEASIBILITY_MAP = {
    "insufficient": {"label": "预算不足", "css_class": "badge-red"},
    "tight":        {"label": "预算偏紧", "css_class": "badge-orange"},
    "sufficient":   {"label": "预算充裕", "css_class": "badge-green"},
}

# ── 方案风格标签 ──────────────────────────────────────────────────
STYLE_LABELS = {
    "economy":    "省钱型：花费最低，预算压力最小",
    "balanced":   "均衡型：成本、路程与体验更平衡",
    "experience": "体验型：评分与热度表现更高",
}

# ── 用户偏好默认值 ──────────────────────────────────────────────────
DEFAULT_SENSITIVITY = 50  # 价格/距离/热度/评分偏好默认值
VALID_SEASONS = {"spring", "summer", "autumn", "winter"}

# ── 地图配色 ──────────────────────────────────────────────────────
MAP_DAY_COLORS = ["#ff4d4f", "#1890ff", "#52c41a", "#faad14", "#722ed1", "#13c2c2"]

# ── Top3 卡片渐变色 ────────────────────────────────────────────────
TOP3_CARD_GRADIENTS = [
    {"header": "linear-gradient(135deg, #8b7fd4, #6b5b95)", "text": "#8b7fd4", "btn": "#8b7fd4"},
    {"header": "linear-gradient(135deg, #5dbea3, #3d9970)", "text": "#5dbea3", "btn": "#5dbea3"},
    {"header": "linear-gradient(135deg, #6bb3d9, #2980b9)", "text": "#6bb3d9", "btn": "#6bb3d9"},
]
