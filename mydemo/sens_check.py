import json
import math
import os
import sys
from pathlib import Path

os.environ['DJANGO_SETTINGS_MODULE'] = 'mydemo.settings'
sys.path.insert(0, r'd:\ass\mydemo')
import django; django.setup()

from home.tests_algorithms.benchmark_utils import (
    db_spots, collect_population_sensitivity,
    collect_generations_sensitivity, collect_budget_sensitivity
)
import random; random.seed(42)

DATA_DIR = Path(__file__).resolve().parent / "diagrams" / "data"


def _clean(obj):
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
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / f"{name}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(_clean(data), f, ensure_ascii=False, indent=2)
    print(f"   [data] 已保存 {path.name}")


spots = db_spots()
budget = 280

print("=== 种群大小敏感性 ===")
pop_results = collect_population_sensitivity(
    pop_sizes=[10, 20, 30, 40, 60, 80, 100],
    spots=spots, budget=budget, days=3, per_day=3, generations=50, runs=6
)
for r in pop_results:
    print(f"pop={r['pop_size']:3d}: HV={r['avg_hv']:.4f}, runtime={r['avg_runtime']:.2f}s")
save_json("sens_population", pop_results)

print()
print("=== 代数敏感性 ===")
gen_results = collect_generations_sensitivity(
    spots, gen_steps=[5, 10, 20, 30, 40, 50, 70, 100],
    budget=budget, days=3, per_day=3, runs=6
)
for r in gen_results:
    print(f"gen={r['generations']:3d}: HV={r['avg_hv']:.4f}, feasible={r['feasible_rate']*100:.0f}%, runtime={r['avg_runtime']:.2f}s")
save_json("sens_generations", gen_results)

print()
print("=== 预算敏感性 ===")
budget_list = [130, 160, 180, 200, 220, 240, 260, 280, 320, 380, 450, 616]
bgt_results = collect_budget_sensitivity(
    budget_list, spots=spots, days=3, per_day=3, pop_size=30, generations=30, runs=6
)
for r in bgt_results:
    cost = r['avg_best_cost']
    cost_str = f"{cost:.1f}" if not math.isnan(cost) else "nan"
    print(f"budget={r['budget']:4d}: feasible={r['feasible_rate']*100:.0f}%, pareto={r['avg_pareto_count']:.1f}, cost={cost_str}")
save_json("sens_budget", bgt_results)
