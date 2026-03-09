# Please install OpenAI SDK first: `pip3 install openai`
# Please install OpenAI SDK first: `pip3 install openai`
import os
import re

import pandas as pd
from openai import OpenAI
# ... existing code ...



class Get_DeepSeek:
    def __init__(self,model:str="deepseek-chat"):
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
            max_tokens=1024
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




