"""清洗 TravelInfo 原始数据，写入 CleanedAttraction 表"""
from django.core.management.base import BaseCommand
from home.data_utils import (
    _normalize_coord_pair,
    _parse_distance_km,
    _parse_price,
    _safe_float,
)
from home.models import CleanedAttraction, TravelInfo


class Command(BaseCommand):
    help = '从 TravelInfo 元数据清洗并填充 CleanedAttraction 表'

    def handle(self, **options):
        total = TravelInfo.objects.count()
        CleanedAttraction.objects.all().delete()
        created = 0
        skipped = 0

        for row in TravelInfo.objects.iterator(chunk_size=500):
            lon, lat = _normalize_coord_pair(row.longitude, row.latitude)
            is_valid = lon != 0.0 or lat != 0.0

            if not row.name or not row.city:
                skipped += 1
                continue

            CleanedAttraction.objects.create(
                source=row,
                name=row.name.strip(),
                city=(row.city or '').strip(),
                area=(row.area or ''),
                tags=(row.tags or ''),
                rating=_safe_float(row.rating, 0.0),
                hotness=_safe_float(row.popularity_score, 0.0),
                review_count=int(_safe_float(row.review_count, 0)),
                cost=_parse_price(row.actual_price),
                longitude=lon,
                latitude=lat,
                center_distance_km=_parse_distance_km(row.distance_from_center),
                is_coord_valid=is_valid,
            )
            created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'清洗完成：{created} 条写入 CleanedAttraction，{skipped} 条跳过（缺名称/城市）'
            )
        )
