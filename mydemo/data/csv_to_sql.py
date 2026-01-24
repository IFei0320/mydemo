import pymysql
import pandas as pd

# 建立数据库连接
conn = pymysql.connect(
    host='127.0.0.1',
    user='root',
    password='123456',
    database='dy_analysis',
)
cursor = conn.cursor()

# SQL插入语句
sql = """
INSERT INTO home_travelinfo (
    unique_id, area, name, review_count, rating, is_ad, is_recommended, 
    city, image_url, distance_from_center, tags, detail_link, market_price, 
    discount_price, discount_description, actual_price, price_type, 
    price_type_description, is_free, longitude, latitude, popularity_score, province
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""

# 读取CSV文件并进行数据清洗
df = pd.read_csv('data_pro.csv')

# 跳过前两行表头，从实际数据开始
df = df.iloc[2:].reset_index(drop=True)

# 确保第一列(unique_id)是整数类型
df.iloc[:, 0] = pd.to_numeric(df.iloc[:, 0], errors='coerce')
df = df.dropna(subset=[df.columns[0]])  # 移除无法转换的行
df.iloc[:, 0] = df.iloc[:, 0].astype(int)  # 转换为整数

# 填充缺失值
df = df.fillna('暂无')

# 批量插入数据
for index, row in df.iterrows():
    cursor.execute(sql, tuple(row))

# 提交事务并关闭连接
conn.commit()
cursor.close()
conn.close()
