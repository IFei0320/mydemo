"""简化E-R图：只画实体、联系、主键"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import matplotlib.font_manager as fm

_fonts = [f.name for f in fm.fontManager.ttflist if any(
    k in f.name for k in ["Microsoft YaHei", "SimHei", "STXihei"])]
if _fonts:
    plt.rcParams["font.sans-serif"] = _fonts + list(plt.rcParams.get("font.sans-serif", []))
plt.rcParams["axes.unicode_minus"] = False

fig, ax = plt.subplots(figsize=(12, 6))
ax.set_xlim(0, 12)
ax.set_ylim(0, 6)
ax.axis("off")
ax.set_facecolor("white")
BLK = "#000000"

def rect(x, y, w, h):
    ax.add_patch(FancyBboxPatch((x - w/2, y - h/2), w, h,
        boxstyle="square,pad=0.0", facecolor="white", edgecolor=BLK, linewidth=1.5, zorder=5))

def diamond(cx, cy, w, h):
    dx, dy = w/2, h/2
    ax.add_patch(mpatches.Polygon([
        (cx, cy + dy), (cx + dx, cy), (cx, cy - dy), (cx - dx, cy)
    ], facecolor="white", edgecolor=BLK, linewidth=1.5, zorder=5))

def line(x1, y1, x2, y2):
    ax.plot([x1, x2], [y1, y2], color=BLK, linewidth=1.2, zorder=1)

def txt(x, y, s, size=10, bold=False):
    ax.text(x, y, s, fontsize=size, fontweight="bold" if bold else "normal",
            color=BLK, ha="center", va="center", zorder=6)

# ---- 用户实体 ----
UX, UY = 2.5, 3.5
rect(UX, UY, 3.6, 1.8)
txt(UX, UY + 0.4, "用户 (User)", size=11, bold=True)
txt(UX, UY - 0.35, "id, username, password, uemail,", size=7.5)
txt(UX, UY - 0.75, "uaddress, uphone, avatar, created_at", size=7.5)

# ---- 景点实体 ----
SX, SY = 9.5, 3.5
rect(SX, SY, 3.6, 1.8)
txt(SX, SY + 0.4, "景点 (Scenic Spot)", size=11, bold=True)
txt(SX, SY - 0.35, "id, name, province, city, area,", size=7.5)
txt(SX, SY - 0.75, "longitude, latitude, rating, actual_price, ...", size=7.5)

# ---- 旅行规划 联系 ----
PX, PY = 6.0, 3.5
diamond(PX, PY, 1.8, 1.0)
txt(PX, PY, "旅行规划", size=10, bold=True)

# ---- 连线 ----
line(UX + 1.8, UY, PX - 0.9, PY + 0.1)
line(PX + 0.9, PY - 0.1, SX - 1.8, SY)

# ---- 基数标注 ----
txt(4.2, 4.0, "1", size=9, bold=True)
txt(5.6, 4.0, "N", size=9, bold=True)
txt(7.0, 4.0, "M", size=9, bold=True)
txt(8.2, 4.0, "N", size=9, bold=True)

# ---- 标题 ----
txt(6, 5.5, "图4-X  旅游路线规划系统全局 E-R 图", size=13, bold=True)

fig.savefig("mydemo/diagrams/output/fig4-X_ER_diagram.svg", format="svg",
            bbox_inches="tight", facecolor="white")
plt.close(fig)
print("OK")
