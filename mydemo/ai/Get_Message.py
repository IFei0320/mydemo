# Please install OpenAI SDK first: `pip3 install openai`
import json
import re

import pandas as pd
from openai import OpenAI


_SEASON_CN = {
    "spring": "春季",
    "summer": "夏季",
    "autumn": "秋季",
    "winter": "冬季",
}


class Get_DeepSeek:
    def __init__(self,model:str="deepseek-v4-flash"):
        self.model = model
        self.client = OpenAI(
            api_key='sk-d2e0034a6f264140a8017b1e98359312',
            base_url="https://api.deepseek.com")
        self.system_prompt = """
        你是一个专业的导游，包括中国以及国外，你需要根据用户给出的信息来为用户制定一个完整的旅游路线，具体要求如下：
        1. 需要根据用户给出的城市、季节、预算以及行程天数给出对应的旅游路线；
        2. 提供的旅游路线应该是固定的格式包括：景点名称、具体游玩时间、景点特点、经纬度、预计花费，表格格式如下：
        | 景点名称 | 游玩时间 | 景点特点 | 经度 | 纬度 | 预计花费 |
        3. 只需要返回表格内容即可，不要额外的文字说明；
        4. 切记返回的内容要合理，也要有逻辑可循；
        5. 经纬度只需返回数字即可，不用单位，确保经纬度准确；
        6. 游玩时间格式是：第X天-时间段（例如：第一天-上午、第二天-下午）；
        7. 预计花费请给出具体金额或"免费"；
        8. 表格使用Markdown格式，用|分隔；
        9. 确保返回的数据能够被正确解析为DataFrame；
        10. 景点数量应该与行程天数相匹配；
        11. 一定要确保经度和纬度的准确性，并且经度和纬度要具体一点；
        """

    _overview_system_prompt = """
你是资深旅行顾问。用户在做攻略前需要「目的地速览」，不是具体每天的游玩排程。
要求：
1) 用中文，语气务实；
2) 说明该城市/目的地大致有哪些类型的去处（历史、自然、亲子、商圈等），偏概括，不要罗列成日程表；
3) 结合用户给出的季节、天数与预算，写「行前注意什么」：交通、预约、穿衣、错峰、消费与常见坑；
4) 不要输出 Markdown 表格，不要输出景点经纬度，不要按「第几天上午下午」排行程；
5) 只输出一个 JSON 对象（不要用 markdown 代码围栏），严格符合下列键（缺失则给空数组或空字符串）：
{"city_summary":"","what_to_see":[],"watchouts":[],"regions":[]}
其中 regions 为对象数组，每项含 title（片区或主题名）、blurb（一两句提示）。
"""

    @staticmethod
    def _strip_code_fence(text: str) -> str:
        t = (text or "").strip()
        if t.startswith("```"):
            lines = t.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            t = "\n".join(lines).strip()
        return t

    def get_city_travel_overview(
        self, city: str, season: str, budget: str, days: str
    ) -> dict:
        """目的地概览与注意事项，返回 JSON 结构。"""
        raw = ""
        try:
            season_cn = _SEASON_CN.get(str(season).strip(), str(season))
            user_msg = (
                f"目的地：{city}；季节：{season_cn}；大致行程长度：{days} 天；预算：{budget}。\n"
                "请只返回 JSON，键为 city_summary、what_to_see、watchouts、regions。"
            )
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": self._overview_system_prompt},
                    {"role": "user", "content": user_msg},
                ],
                stream=False,
                max_tokens=1400,
                extra_body={"thinking": {"type": "disabled"}},
            )
            raw = response.choices[0].message.content or ""
            stripped = self._strip_code_fence(raw)
            data = json.loads(stripped)
            overview = {
                "city_summary": str(data.get("city_summary") or "").strip(),
                "what_to_see": data.get("what_to_see") or [],
                "watchouts": data.get("watchouts") or [],
                "regions": data.get("regions") or [],
            }
            if not isinstance(overview["what_to_see"], list):
                overview["what_to_see"] = []
            if not isinstance(overview["watchouts"], list):
                overview["watchouts"] = []
            if not isinstance(overview["regions"], list):
                overview["regions"] = []
            overview["what_to_see"] = [str(x).strip() for x in overview["what_to_see"] if str(x).strip()]
            overview["watchouts"] = [str(x).strip() for x in overview["watchouts"] if str(x).strip()]
            clean_regions = []
            for r in overview["regions"]:
                if isinstance(r, dict):
                    title = str(r.get("title") or "").strip()
                    blurb = str(r.get("blurb") or r.get("tips") or "").strip()
                    if title or blurb:
                        clean_regions.append({"title": title, "blurb": blurb})
            overview["regions"] = clean_regions
            return {"code": 200, "overview": overview, "raw": raw}
        except json.JSONDecodeError as e:
            fallback = {
                "city_summary": (raw or "")[:800],
                "what_to_see": [],
                "watchouts": [],
                "regions": [],
                "parse_note": f"模型输出未能解析为 JSON，已展示节选原文。技术信息：{e}",
            }
            return {"code": 200, "overview": fallback, "raw": raw}
        except Exception as e:
            return {"code": 500, "message": str(e), "raw": raw}

    def _get_travel_plan(self, city: str, season: str, budget: str, days: str) -> dict:
        raw_result = ""

        try:
            raw_result = self._get_ai_response(city, season, budget, days)

            # 解析DataFrame
            df = self._parse_table_to_dataframe(raw_result)

            # 转换英文字段名
            processed_data = self._process_data(df)
            return {
                "code": 200,
                "data": processed_data,
                "raw": raw_result
            }


        except Exception as e:
            return {
                "code": 500,
                "message": str(e),
                "raw": raw_result
            }
    def _get_ai_response(self, city: str, season: str, budget: str, days: str) -> str:
        """调用AI接口获取原始响应"""
        content = f"""
        我想去城市是{city}，我去的季节是{season}，有{days}天的时间，一共的预算是{budget}。
        请为我制定一个{days}天的旅游路线。
        """

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": content},
        ]
        response = self.client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            stream=False,
            max_tokens=1024,
            extra_body={"thinking": {"type": "disabled"}}
             )
        return response.choices[0].message.content

    def _parse_table_to_dataframe(self, table_text: str) -> pd.DataFrame:
        """将AI返回的表格文本解析为DataFrame"""
        # 清理文本，移除多余的空格和换行
        cleaned_text = re.sub(r'\n+', '\n', table_text.strip())
        lines = [line.strip() for line in cleaned_text.split('\n') if line.strip()]

        # 找到表格部分
        table_start = -1
        for i, line in enumerate(lines):
            if '|' in line and ('景点名称' in line or '景点' in line):
                table_start = i
                break

        if table_start == -1:
            raise ValueError("未找到有效表格数据")

        # 提取表头
        header_line = lines[table_start]
        headers = [cell.strip() for cell in header_line.split('|') if cell.strip()]

        # 移除表头中的空格和特殊字符
        headers = [re.sub(r'[\s\u3000]', '', header) for header in headers]

        # 提取数据行
        data = []
        for line in lines[table_start + 1:]:
            if '---' in line or not line.strip():
                continue
            if '|' not in line:
                continue

            row = [cell.strip() for cell in line.split('|') if cell.strip()]
            if len(row) == len(headers):
                data.append(row)
            elif len(row) > len(headers):
                # 如果列数多于表头，取前len(headers)列
                data.append(row[:len(headers)])
            else:
                # 如果列数少于表头，用空值填充
                row.extend([''] * (len(headers) - len(row)))
                data.append(row)

        if not data:
            raise ValueError("未找到有效数据行")

        return pd.DataFrame(data, columns=headers)

    def _process_data(self, df: pd.DataFrame) -> list:
        """处理数据并转换为英文字段名"""
        print("原始DataFrame:")
        print(df)
        print("列名:", df.columns.tolist())

        # 修复字段映射逻辑 - 使用精确匹配
        field_mapping = {}
        for col in df.columns:
            col_clean = re.sub(r'[\s\u3000]', '', col)
            print(f"处理列: {col} -> {col_clean}")

            # 使用精确匹配而不是部分匹配
            if col_clean == '景点名称':
                field_mapping[col] = 'name'
            elif col_clean == '游玩时间':
                field_mapping[col] = 'visit_time'
            elif col_clean == '景点特点':
                field_mapping[col] = 'features'
            elif col_clean == '经度':
                field_mapping[col] = 'longitude'
            elif col_clean == '纬度':
                field_mapping[col] = 'latitude'
            elif col_clean == '预计花费':
                field_mapping[col] = 'estimated_cost'

        print("字段映射:", field_mapping)

        # 重命名字段
        df.rename(columns=field_mapping, inplace=True)

        # 确保所有必要的字段都存在
        required_fields = ['name', 'visit_time', 'features', 'estimated_cost', 'longitude', 'latitude']
        for field in required_fields:
            if field not in df.columns:
                df[field] = ''

        # 处理经纬度数据
        for index, row in df.iterrows():
            # 处理经度
            if pd.notna(row.get('longitude')) and row['longitude'] != '':
                try:
                    lon_str = str(row['longitude']).strip()
                    # 移除可能的度符号等
                    lon_str = re.sub(r'[^\d.-]', '', lon_str)
                    df.at[index, 'longitude'] = float(lon_str) if lon_str else None
                except (ValueError, TypeError):
                    df.at[index, 'longitude'] = None

            # 处理纬度
            if pd.notna(row.get('latitude')) and row['latitude'] != '':
                try:
                    lat_str = str(row['latitude']).strip()
                    lat_str = re.sub(r'[^\d.-]', '', lat_str)
                    df.at[index, 'latitude'] = float(lat_str) if lat_str else None
                except (ValueError, TypeError):
                    df.at[index, 'latitude'] = None

        # 处理其他字段，确保数据类型正确
        for field in ['name', 'visit_time', 'features', 'estimated_cost']:
            if field in df.columns:
                df[field] = df[field].astype(str).replace('nan', '').replace('None', '')

        print("处理后的DataFrame:")
        print(df)
        print("最终数据:", df.to_dict(orient='records'))

        return df.to_dict(orient='records')