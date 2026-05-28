from home.nsga2_trip_planner import ScenicSpot


class DummyQuerySet:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, city__icontains):
        keyword = city__icontains.replace("市", "")
        matched = [
            row
            for row in self.rows
            if keyword in str(getattr(row, "city", "")).replace("市", "")
        ]
        return DummyQuerySet(matched)

    def __iter__(self):
        return iter(self.rows)

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, item):
        return self.rows[item]


class DummyRow:
    def __init__(
        self,
        name,
        city,
        area,
        tags,
        rating,
        popularity_score,
        review_count,
        actual_price,
        longitude,
        latitude,
        distance_from_center,
    ):
        self.name = name
        self.city = city
        self.area = area
        self.tags = tags
        self.rating = rating
        self.popularity_score = popularity_score
        self.review_count = review_count
        self.actual_price = actual_price
        self.longitude = longitude
        self.latitude = latitude
        self.distance_from_center = distance_from_center


def candidate_rows():
    return [
        DummyRow("外滩", "上海市", "黄浦区", "夜景 江景", 4.8, 9.5, 10000, "免费", 121.4903, 31.2417, "3.2km"),
        DummyRow("东方明珠", "上海", "浦东新区", "地标 夜景", 4.7, 9.2, 8000, "199元", 121.4998, 31.2397, "5km"),
        DummyRow("异常点", "上海", "未知", "测试", 4.0, 5.0, 100, "10元", 0, 0, "1km"),
    ]


def route_spots():
    return [
        ScenicSpot("A", "上海", "黄浦", "夜景", 4.8, 9.0, 1000, 50, 121.47, 31.23, 2.0),
        ScenicSpot("B", "上海", "浦东", "地标", 4.6, 8.0, 800, 80, 121.50, 31.24, 3.0),
        ScenicSpot("C", "上海", "徐汇", "公园", 4.4, 7.5, 600, 0, 121.43, 31.20, 1.5),
    ]


def comparison_spots():
    return [
        ScenicSpot("外滩", "上海", "黄浦", "夜景", 4.8, 9.2, 1000, 0, 121.4903, 31.2417, 2.0),
        ScenicSpot("东方明珠", "上海", "浦东", "地标", 4.9, 9.6, 900, 199, 121.4998, 31.2397, 4.0),
        ScenicSpot("豫园", "上海", "黄浦", "古典", 4.7, 8.7, 850, 40, 121.4925, 31.2273, 2.5),
        ScenicSpot("上海博物馆", "上海", "黄浦", "人文", 4.9, 8.5, 780, 0, 121.4753, 31.2304, 1.8),
        ScenicSpot("田子坊", "上海", "黄浦", "街区", 4.6, 8.1, 650, 0, 121.4662, 31.2094, 3.2),
        ScenicSpot("南京路", "上海", "黄浦", "商圈", 4.5, 8.8, 720, 0, 121.4805, 31.2363, 1.6),
        ScenicSpot("迪士尼", "上海", "浦东", "乐园", 4.9, 9.8, 1500, 435, 121.6670, 31.1434, 18.0),
        ScenicSpot("上海中心", "上海", "浦东", "观景", 4.8, 9.0, 700, 180, 121.5076, 31.2336, 5.1),
    ]
