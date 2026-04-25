import pymysql
import pandas as pd

import jieba
from collections import Counter

# 建立数据库连接
conn = pymysql.connect(
    host='127.0.0.1',
    user='root',
    password='123456',
    database='dy_analysis',
)
cursor = conn.cursor()

df = pd.read_csv('data_pro.csv')


def part1():
    data = df.copy()
    data = data[data['评分'] != 0.0]
    score_counts = data['评分'].value_counts()
    print(score_counts)

    # 清空表
    truncate_sql = "truncate table part1"
    cursor.execute(truncate_sql)
    conn.commit()

    sql = "insert into part1(score, value) values(%s, %s)"

    # 将分析结果写入表
    for index, row in score_counts.items():
        cursor.execute(sql, (index, row))
    conn.commit()


def part2():
    top_10 = df.nlargest(10, '评论数量')[['景点名称', '评论数量']]

    # 清空表
    truncate_sql = "truncate table part2"
    cursor.execute(truncate_sql)
    conn.commit()

    sql = "insert into part2(name, value) values(%s, %s)"

    # 将分析结果写入表
    for index, row in top_10.iterrows():
        cursor.execute(sql, (row['景点名称'], row['评论数量']))
    conn.commit()


def part3():
    df['实际票价'] = df['实际票价'].astype(str)
    df['实际票价'] = df['实际票价'].replace('免费', '0')

    # 将类型转换为float
    df['实际票价'] = df['实际票价'].astype(float)

    # 定义价格区间
    bins = [0, 1, 50, 100, 200, 500, 1000, float('inf')]
    labels = ['0', '1-50', '50-100', '100-200', '200-500', '500-1000', '1000+']
    price_dis = pd.cut(df['实际票价'], bins=bins, labels=labels, right=False)
    price_counts = price_dis.value_counts().sort_index()

    truncate_sql = "truncate table part3"
    cursor.execute(truncate_sql)
    conn.commit()

    sql = "insert into part3(name, value) values(%s, %s)"

    # 将分析结果写入表
    for index, row in price_counts.items():
        cursor.execute(sql, (index, row))
    conn.commit()


def part4():
    data = df.copy()
    area_counts = data['所在区域'].value_counts()
    print(area_counts)

    # 清空表
    truncate_sql = "truncate table part4"
    cursor.execute(truncate_sql)
    conn.commit()

    sql = "insert into part4(name, value) values(%s, %s)"

    # 将分析结果写入表
    for index, row in area_counts.items():
        cursor.execute(sql, (index, row))
    conn.commit()


def load_stopwords():
    stopwords = set([
        "的", "是", "在", "和", "也", "就", "从", "到",
        "还", "如", "会", "所", "或", "而", "很",
        "没有", "因为", "所以", "我们", "你们", "他们",
        "但", "如果", "你", "我", "他", "它"
    ])
    return stopwords


def part5():
    # 合并标签和景点名称文本
    all_texts = df['标签'].fillna("").tolist() + df['景点名称'].fillna("").tolist()
    print(all_texts)

    # 加载停用词
    stopwords = load_stopwords()
    words = []

    for text in all_texts:
        seg_list = jieba.lcut(text)
        # 过滤停用词
        words.extend(word for word in seg_list if word not in stopwords and word.strip() != "")

    word_count = Counter(words)
    word_count_df = pd.DataFrame(list(word_count.items()), columns=['词语', '出现次数'])
    # 清空表
    truncate_sql = "truncate table part5"
    cursor.execute(truncate_sql)
    conn.commit()
    sql = "insert into part5 (name, value) values(%s, %s)"
    # 将分析结果写入表
    for index, row in word_count_df.iterrows():
        cursor.execute(sql, (row['词语'], row['出现次数']))
    conn.commit()


# 各省份景点数量
def part6():
    pro_count = df['省份'].value_counts()

    # 清空表
    truncate_sql = "truncate table part6"
    cursor.execute(truncate_sql)
    conn.commit()

    sql = "insert into part6(name, value) values(%s, %s)"

    # 将分析结果写入表
    for index, row in pro_count.items():
        cursor.execute(sql, (index, row))
    conn.commit()


# def part7():
#     city_travel_rank = df.sort_values('热度评分', ascending=False).groupby('城市名称').head(10)
#     rank_data = city_travel_rank[['城市名称', '景点名称', '热度评分']]
#     print(rank_data)
#
#     # 清空表
#     truncate_sql = "truncate table part7"
#     cursor.execute(truncate_sql)
#     conn.commit()
#
#     sql = "insert into part7(city, name, value) values(%s, %s, %s)"
#
#     # 将分析结果写入表
#     for index, row in rank_data.iterrows():
#         cursor.execute(sql, (row['城市名称'], row['景点名称'], row['热度评分']))
#     conn.commit()


def part7():
    city_travel_rank = df.sort_values('热度评分', ascending=False).groupby('城市名称').head(10)
    rank_data = city_travel_rank[['城市名称', '景点名称', '热度评分']]
    print(rank_data)

    # 清空表
    truncate_sql = "truncate table part7"
    cursor.execute(truncate_sql)
    conn.commit()

    sql = "insert into part7(city, name, value) values(%s, %s, %s)"

    # 将分析结果写入表
    for index, row in rank_data.iterrows():
        if pd.notna(row['城市名称']) and pd.notna(row['景点名称']) and pd.notna(row['热度评分']):
            cursor.execute(sql, (row['城市名称'], row['景点名称'], row['热度评分']))
    conn.commit()




def part8():
    data = df.copy()
    data = data[data['评分'] != 0.0]
    data['评分'] = data['评分'].astype(float)

    # 按照省份分组计算平均分
    pro_ratings = data.groupby('省份')['评分'].agg(['count', 'mean']).reset_index()
    pro_ratings.columns = ['省份', '景点数量', '平均评分']
    pro_ratings['平均评分'] = pro_ratings['平均评分'].round(2)
    print(pro_ratings)

    # 清空表
    truncate_sql = "truncate table part8"
    cursor.execute(truncate_sql)
    conn.commit()

    sql = "insert into part8(name, travel_num, avg_score) values(%s, %s, %s)"

    # 将分析结果写入表
    for index, row in pro_ratings.iterrows():
        cursor.execute(sql, (row['省份'], row['景点数量'], row['平均评分']))
    conn.commit()

if __name__ == '__main__':
    part1()  # 确保这里缩进正确（4个空格）
    part2()
    part3()
    part4()
    part5()
    part6()
    part7()
    part8()