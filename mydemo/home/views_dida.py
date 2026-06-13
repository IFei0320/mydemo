import json
import os
import re
from datetime import datetime, timedelta
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError

from django.http import JsonResponse
from django.views.decorators.http import require_POST

from utils.decorators import login_required_custom
from dotenv import load_dotenv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

DIDA_FIXED_ACCESS_TOKEN = os.getenv('DIDA_ACCESS_TOKEN', '')
DIDA_FIXED_PROJECT_INPUT = os.getenv('DIDA_PROJECT_NAME', '旅游规划')


def _parse_day_slot(visit_time: str):
    """从 visit_time 字符串中解析出"第几天"和"上/中/下午"。

    输入样例：
        "第1天上午"  →  (1, "上午")
        "第2天下午"  →  (2, "下午")
        "第3天中午"  →  (3, "中午")
        "自由活动"   →  (1, "下午")    — 未匹配时默认第1天下午

    返回：
        (day_no, slot)  — day_no 从 1 开始，slot 为 "上午" / "中午" / "下午"。
    """
    text = str(visit_time or "")
    day_match = re.search(r"第(\d+)天", text)
    day_no = int(day_match.group(1)) if day_match else 1
    if "上午" in text:
        slot = "上午"
    elif "中午" in text:
        slot = "中午"
    else:
        slot = "下午"
    return day_no, slot


def _format_dida_datetime(dt_obj: datetime) -> str:
    """将 datetime 对象格式化为滴答清单 API 所需的 ISO 格式。

    输出样例：
        "2026-06-14T09:00:00+0800"

    参数：
        dt_obj: Python datetime 对象。

    返回：
        固定 +0800 时区的日期时间字符串。
    """
    return dt_obj.strftime("%Y-%m-%dT%H:%M:%S+0800")


def _resolve_dida_project_id(access_token: str, project_input: str) -> str:
    """解析滴答清单的项目 ID。

    参数：
        access_token: 滴答开放 API 的 access token。
        project_input: 用户输入，可以是 projectId（长度 >= 20）或项目名称。

    数据流：
        project_input 长度 >= 20 → 直接视为 projectId 返回
        project_input 是项目名  → 调滴答 API 列出所有项目，按 name 匹配

    返回：
        匹配到的 projectId 字符串；无匹配返回空字符串。
    """
    if not project_input:
        return ""
    candidate = project_input.strip()
    if len(candidate) >= 20:
        return candidate

    req = urlrequest.Request(
        "https://api.dida365.com/open/v1/project",
        headers={"Authorization": f"Bearer {access_token}"},
        method="GET",
    )
    with urlrequest.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8") or "[]")
        if isinstance(data, list):
            for item in data:
                if str(item.get("name", "")).strip() == candidate:
                    return str(item.get("id", "")).strip()
    return ""


@require_POST
@login_required_custom
def export_to_dida_checklist(request):
    """将 AI 生成的旅行路线导出到滴答清单。

    数据流：
        前端 POST（路线 + 知识卡片 + 出发时间）
            ↓
        解析出发日期，按 route 逐项生成滴答任务
        每个景点 → 一个滴答任务（含时段、坐标、知识卡片避坑信息）
            ↓
        调滴答开放 API（POST /open/v1/task）
            ↓
        返回创建成功/失败的任务列表

    依赖环境变量：
        DIDA_ACCESS_TOKEN  — 滴答开放 API 的 access token
        DIDA_PROJECT_NAME  — 目标项目名称（或 projectId）

    请求体格式：
        {
            "departure_time": "2026-06-14",      // 出发日期
            "city": "上海",
            "style": "economy",
            "route": [{                          // 日行程
                "visit_time": "第1天上午",
                "name": "外滩",
                "features": "...",
                "estimated_cost": "免费",
                "latitude": "31.2400",
                "longitude": "121.4900"
            }],
            "knowledge_cards": [...]              // 对应景点的知识卡片
        }

    返回：
        成功：  {"code": 200, "message": "已创建 N 个景点任务", "data": {...}}
        失败：  {"code": 400/500, "message": "...", "data": {...}}
    """
    try:
        data = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"code": 400, "message": "无效的 json 数据", "data": None})

    access_token = DIDA_FIXED_ACCESS_TOKEN
    project_input = DIDA_FIXED_PROJECT_INPUT
    departure_time = str(data.get("departure_time", "")).strip()
    city = str(data.get("city", "")).strip()
    style = str(data.get("style", "")).strip()
    route = data.get("route", []) or []
    knowledge_cards = data.get("knowledge_cards", []) or []

    if not departure_time:
        return JsonResponse({"code": 400, "message": "departure_time 不能为空", "data": None})
    if not route:
        return JsonResponse({"code": 400, "message": "当前无可导出的行程数据", "data": None})

    try:
        base_dt = datetime.fromisoformat(departure_time)
    except ValueError:
        return JsonResponse({"code": 400, "message": "出发时间格式不正确", "data": None})

    slot_hour = {"上午": 9, "中午": 13, "下午": 16}
    try:
        project_id = _resolve_dida_project_id(access_token, project_input)
    except Exception:
        project_id = ""
    if not project_id:
        return JsonResponse({"code": 400, "message": "无法识别 projectId/项目名称，请检查是否有该清单", "data": None})

    knowledge_index = []
    for card in knowledge_cards:
        knowledge_index.append(
            {
                "spot_name": str(card.get("spot_name", "")).strip(),
                "best_time": str(card.get("best_time", "")).strip(),
                "booking_tip": str(card.get("booking_tip", "")).strip(),
                "transport_tip": str(card.get("transport_tip", "")).strip(),
                "pitfalls": card.get("pitfalls", []) or [],
            }
        )

    def _match_knowledge(spot_name: str):
        """从 knowledge_index 中模糊匹配景点名称。

        匹配策略：双向包含（"外滩" in "上海外滩" 或 "上海外滩" in "外滩"）。

        参数：
            spot_name: 路线中的景点名（如 "上海外滩"）。

        返回：
            匹配到的知识卡片 dict，或 None。
        """
        name = (spot_name or "").strip().lower()
        for item in knowledge_index:
            k = item["spot_name"].lower()
            if k and (k in name or name in k):
                return item
        return None

    created_tasks = []
    failed_tasks = []
    for row in route:
        day_no, slot = _parse_day_slot(row.get("visit_time", ""))
        start_dt = (base_dt + timedelta(days=day_no - 1)).replace(
            hour=slot_hour.get(slot, 9), minute=0, second=0, microsecond=0
        )
        due_dt = start_dt + timedelta(hours=2)
        spot_name = str(row.get("name", "")).strip()
        knowledge = _match_knowledge(spot_name)
        pitfalls = []
        if knowledge:
            pitfalls = knowledge.get("pitfalls", [])[:3]

        desc_lines = [
            f"行程时段：{row.get('visit_time', '')}",
            f"景点特点：{row.get('features', '')}",
            f"预计花费：{row.get('estimated_cost', '免费')}",
            f"坐标：{row.get('latitude', '')}, {row.get('longitude', '')}",
            "",
            "贴心提醒：",
            f"- 最佳游玩时段：{(knowledge or {}).get('best_time', '建议按实时天气灵活调整')}",
            f"- 预约提示：{(knowledge or {}).get('booking_tip', '建议提前查看官方公告')}",
            f"- 交通建议：{(knowledge or {}).get('transport_tip', '建议地铁优先，打车补充')}",
            f"- 避坑建议：{'；'.join(pitfalls) if pitfalls else '避开高峰时段，注意随身物品'}",
            "",
            "出发前检查：证件/电量/网络/交通路线，建议提前15分钟出发。",
        ]
        detail_text = "\n".join(desc_lines)

        dida_payload = {
            "title": f"{row.get('visit_time', '')}｜{spot_name}",
            "projectId": project_id,
            "content": detail_text,
            "desc": detail_text,
            "isAllDay": False,
            "startDate": _format_dida_datetime(start_dt),
            "dueDate": _format_dida_datetime(due_dt),
            "timeZone": "Asia/Shanghai",
            "priority": 3,
            "tags": ["旅行计划", "AI路线", f"第{day_no}天"],
        }

        req = urlrequest.Request(
            "https://api.dida365.com/open/v1/task",
            data=json.dumps(dida_payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}",
            },
            method="POST",
        )
        try:
            with urlrequest.urlopen(req, timeout=20) as resp:
                resp_text = resp.read().decode("utf-8")
                resp_json = json.loads(resp_text) if resp_text else {}
                created_tasks.append(
                    {
                        "task_id": resp_json.get("id", ""),
                        "title": dida_payload["title"],
                        "content_preview": dida_payload["content"][:80],
                    }
                )
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            failed_tasks.append({"title": dida_payload["title"], "error": f"{exc.code} {body}"})
        except URLError as exc:
            failed_tasks.append({"title": dida_payload["title"], "error": str(exc.reason)})

    if not created_tasks:
        return JsonResponse(
            {
                "code": 500,
                "message": "滴答任务创建失败",
                "data": {"failed_tasks": failed_tasks[:3]},
            }
        )
    return JsonResponse(
        {
            "code": 200,
            "message": f"已创建 {len(created_tasks)} 个景点任务（每个地点一个任务）",
            "data": {
                "project_id": project_id,
                "created_count": len(created_tasks),
                "failed_count": len(failed_tasks),
                "created_tasks": created_tasks[:5],
                "failed_tasks": failed_tasks[:3],
            },
        }
    )
