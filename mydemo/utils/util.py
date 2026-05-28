import os
import pymysql
from dotenv import load_dotenv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

def get_db():
    """获取数据库连接和游标"""
    conn = pymysql.connect(
        host=os.getenv('DB_HOST', '127.0.0.1'),
        user=os.getenv('DB_USER', 'root'),
        password=os.getenv('DB_PASSWORD', '123456'),
        database=os.getenv('DB_NAME', 'dy_analysis'),
        charset='utf8mb4'
    )
    cursor = conn.cursor()
    return conn, cursor

# 查询示例
def query(sql, params=None):
    conn, cursor = get_db()
    try:
        cursor.execute(sql, params or ())
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
