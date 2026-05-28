"""
Chen风格数据库E-R图 —— 纯 PIL 手绘
实体矩形左列竖排 · 关系菱形居中 · 属性椭圆环绕 · 黑白直线
"""
from PIL import Image, ImageDraw, ImageFont
import os

OUT = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(OUT, exist_ok=True)

# ── 画布 ──
W, H = 1400, 900
img = Image.new("RGB", (W, H), "white")
draw = ImageDraw.Draw(img)

# ── 字体 ──
FONT_PATH = "C:/Windows/Fonts/simhei.ttf"
font10 = ImageFont.truetype(FONT_PATH, 20)
font9  = ImageFont.truetype(FONT_PATH, 18)
font8  = ImageFont.truetype(FONT_PATH, 16)

# ── 工具函数 ──
def text_size(text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]

def draw_rect(cx, cy, text, font, w=120, h=40):
    """实体矩形"""
    x0, y0 = cx - w//2, cy - h//2
    x1, y1 = cx + w//2, cy + h//2
    draw.rectangle([x0, y0, x1, y1], outline="black", fill="white", width=2)
    tw, th = text_size(text, font)
    draw.text((cx - tw//2, cy - th//2), text, fill="black", font=font)
    return x0, y0, x1, y1, cx, cy

def draw_diamond(cx, cy, text, font, w=90, h=55):
    """关系菱形"""
    hw, hh = w // 2, h // 2
    pts = [(cx, cy - hh), (cx + hw, cy), (cx, cy + hh), (cx - hw, cy)]
    draw.polygon(pts, outline="black", fill="white", width=2)
    lines = text.split("\n")
    line_h = font.size + 2
    total_h = len(lines) * line_h
    start_y = cy - total_h // 2
    for i, line in enumerate(lines):
        tw, th = text_size(line, font)
        draw.text((cx - tw//2, start_y + i * line_h), line, fill="black", font=font)
    return cx - hw, cy - hh, cx + hw, cy + hh, cx, cy

def draw_ellipse(cx, cy, text, font, w=80, h=32):
    """属性椭圆"""
    x0, y0 = cx - w//2, cy - h//2
    x1, y1 = cx + w//2, cy + h//2
    draw.ellipse([x0, y0, x1, y1], outline="black", fill="white", width=1)
    tw, th = text_size(text, font)
    draw.text((cx - tw//2, cy - th//2), text, fill="black", font=font)
    return x0, y0, x1, y1, cx, cy

def line_between(x1, y1, x2, y2, width=1):
    draw.line([(x1, y1), (x2, y2)], fill="black", width=width)

def label_at(x, y, text, font, offset_x=0, offset_y=0):
    tw, th = text_size(text, font)
    draw.text((x + offset_x - tw//2, y + offset_y - th//2), text, fill="black", font=font)

# ── 布局 ======================================================
# 实体左列 (x=200), 垂直居中
EX = 200
EY1 = 280  # 用户
EY2 = 620  # 景点

# 菱形中间列 (x=500)
DX = 500

# 属性列
AX = 450  # 属性左侧 (在实体和菱形之间, 放实体侧)

# ── 1. 实体 ──
draw_rect(EX, EY1, "用户", font10, 120, 45)
draw_rect(EX, EY2, "景点", font10, 120, 45)

# ── 2. 关系菱形 ──
DY = (EY1 + EY2) // 2  # 两个实体中间
draw_diamond(DX, DY, "生成\n行程", font9, 90, 60)

# ── 3. 连线 实体→菱形 (带基数) ──
line_between(EX + 60, EY1, DX - 45, DY - 10, width=2)  # 用户右上 → 菱形左上
label_at(EX + 100, EY1 + 25, "1", font9, offset_x=-10, offset_y=5)

line_between(EX + 60, EY2, DX - 45, DY + 10, width=2)  # 景点右上 → 菱形左下
label_at(EX + 100, EY2 - 25, "n", font9, offset_x=-10, offset_y=-5)

# ── 4. 用户属性 (椭圆, 放在用户左侧) ──
ux = EX - 180  # 属性 X 中心
uy_start = EY1 - 150
draw_ellipse(ux, uy_start,      "用户ID",   font8, 85, 35)
draw_ellipse(ux, uy_start + 50, "用户名",   font8, 85, 35)
draw_ellipse(ux, uy_start + 100,"密码",     font8, 85, 35)
draw_ellipse(ux, uy_start + 150,"手机号",   font8, 85, 35)

# 线: 属性→实体
line_between(ux + 42, uy_start,       EX - 60, EY1 - 15)
line_between(ux + 42, uy_start + 50,  EX - 60, EY1 - 5)
line_between(ux + 42, uy_start + 100, EX - 60, EY1 + 5)
line_between(ux + 42, uy_start + 150, EX - 60, EY1 + 15)

# ── 5. 景点属性 (椭圆, 放在景点右侧) ──
sx = EX + 250  # 景点属性放右侧
sy_start = EY2 - 90
draw_ellipse(sx, sy_start,       "景点ID",  font8, 85, 35)
draw_ellipse(sx, sy_start + 48,  "景点名称", font8, 85, 35)
draw_ellipse(sx, sy_start + 96,  "城市",    font8, 85, 35)
draw_ellipse(sx, sy_start + 144, "评分",    font8, 85, 35)
draw_ellipse(sx, sy_start + 192, "门票价格", font8, 85, 35)

# 线: 实体→属性
line_between(EX + 60, EY2 - 12, sx - 42, sy_start)
line_between(EX + 60, EY2 - 3,  sx - 42, sy_start + 48)
line_between(EX + 60, EY2 + 6,  sx - 42, sy_start + 96)
line_between(EX + 60, EY2 + 15, sx - 42, sy_start + 144)
line_between(EX + 60, EY2 + 24, sx - 42, sy_start + 192)

# ── 6. 知识卡片 (虚线框, 右下角) ──
kcx, kcy = 800, 720
draw.rectangle([kcx-100, kcy-25, kcx+100, kcy+25], outline="black", fill="white", width=1)
draw.text((kcx-80, kcy-14), "知识卡片 (JSON)", fill="black", font=font8)
draw.text((kcx-95, kcy+6), "wiki/cards/ 不入库", fill="gray", font=font8)

# 虚线: 景点 → 知识卡片
for i in range(0, 30, 4):
    x = EX + 60 + i
    y = EY2 + 40 + i * 0.3
    draw.point((x, int(y)), fill="black")

line_between(EX + 60, EY2 + 40, kcx, kcy - 25, width=1)
# 改为短虚线
# draw line from 景点 bottom to 知识卡片 top
draw.line([(EX + 60, EY2 + 22), (EX + 60, EY2 + 80), (kcx, EY2 + 80), (kcx, kcy - 25)],
          fill="black", width=1)

# 标注
label_at(EX + 60 + 20, EY2 + 50, "景点名称\n字符串匹配", font8, offset_x=60)

# ── 7. 标题 ──
draw.text((W//2 - 100, 20), "图4-3 数据库E-R图", fill="black", font=font10)

# ========== 保存 ==========
out_path = os.path.join(OUT, "fig4-3_db_er.png")
img.save(out_path, dpi=(300, 300))
print(f"OK → {out_path}  ({img.size[0]}x{img.size[1]})")
