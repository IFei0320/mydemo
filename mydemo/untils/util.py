

import pymysql

def get_db():
    """获取数据库连接和游标"""
    conn = pymysql.connect(
        host='127.0.0.1',
        user='root',
        password='123456',
        database='dy_analysis',
        charset='utf8mb4'
    )
    cursor = conn.cursor()
    return conn, cursor

# 查询示例
def query(sql):
    conn, cursor = get_db()
    try:
        cursor.execute(sql)
        result = cursor.fetchall()
        return result
    finally:
        cursor.close()
        conn.close()

# 插入/更新/删除示例
def execute(sql):
    conn, cursor = get_db()
    try:
        cursor.execute(sql)
        conn.commit()
    finally:
        cursor.close()
        conn.close()


