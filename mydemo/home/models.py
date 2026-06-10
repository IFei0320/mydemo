
from django.db import models


class TravelInfo(models.Model):
    unique_id = models.BigIntegerField(null=True, verbose_name='唯一标识')
    area = models.CharField(max_length=255, null=True, verbose_name='所在区域')
    name = models.CharField(max_length=255, null=True, verbose_name='景点名称')
    review_count = models.IntegerField(null=True, verbose_name='评论数量')
    rating = models.CharField(max_length=50, null=True, verbose_name='评分')
    is_ad = models.BooleanField(default=False, null=True, verbose_name='是否为广告')
    is_recommended = models.BooleanField(default=False, null=True, verbose_name='是否被推荐')
    city = models.CharField(max_length=50, null=True, verbose_name='城市名称')
    image_url = models.CharField(max_length=500, null=True, verbose_name='图片链接')
    distance_from_center = models.CharField(max_length=255, null=True, verbose_name='与市中心距离')
    tags = models.CharField(max_length=255, null=True, verbose_name='标签')
    detail_link = models.CharField(max_length=500, null=True, verbose_name='详情页链接')
    market_price = models.CharField(max_length=255, null=True, verbose_name='市场票价')
    discount_price = models.CharField(max_length=255, null=True, verbose_name='优惠价格')
    discount_description = models.CharField(max_length=255, null=True, verbose_name='优惠描述')
    actual_price = models.CharField(max_length=255, null=True, verbose_name='实际票价')
    price_type = models.CharField(max_length=255, null=True, verbose_name='价格类型')
    price_type_description = models.CharField(max_length=100, null=True, verbose_name='价格类型描述')
    is_free = models.BooleanField(default=False, null=True, verbose_name='是否免费')
    longitude = models.FloatField(null=True, verbose_name='经度')
    latitude = models.FloatField(null=True, verbose_name='纬度')
    popularity_score = models.CharField(max_length=255, null=True, verbose_name='热度评分')
    province = models.CharField(max_length=100, null=True, verbose_name='省份')

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = '旅游信息管理'
        db_table = 'home_travelinfo'


class Part1(models.Model):
    """评分分布统计表"""
    score = models.FloatField(null=True, verbose_name='评分')
    value = models.IntegerField(null=True, verbose_name='数量')

    class Meta:
        db_table = 'part1'
        managed = False


class Part2(models.Model):
    """热门景点 Top10 表"""
    name = models.CharField(max_length=255, null=True, verbose_name='景点名称')
    value = models.IntegerField(null=True, verbose_name='评论数量')

    class Meta:
        db_table = 'part2'
        managed = False


class Part3(models.Model):
    """价格区间分布表"""
    name = models.CharField(max_length=50, null=True, verbose_name='价格区间')
    value = models.IntegerField(null=True, verbose_name='景点数量')

    class Meta:
        db_table = 'part3'
        managed = False


class Part4(models.Model):
    """区域分布统计表"""
    name = models.CharField(max_length=255, null=True, verbose_name='区域名称')
    value = models.IntegerField(null=True, verbose_name='景点数量')

    class Meta:
        db_table = 'part4'
        managed = False


class Part5(models.Model):
    """热词统计表"""
    name = models.CharField(max_length=255, null=True, verbose_name='词语')
    value = models.IntegerField(null=True, verbose_name='出现次数')

    class Meta:
        db_table = 'part5'
        managed = False


class Part6(models.Model):
    """各省份景点数量表"""
    name = models.CharField(max_length=100, null=True, verbose_name='省份')
    value = models.IntegerField(null=True, verbose_name='景点数量')

    class Meta:
        db_table = 'part6'
        managed = False


class Part7(models.Model):
    """城市热门排名表"""
    city = models.CharField(max_length=50, null=True, verbose_name='城市名称')
    name = models.CharField(max_length=255, null=True, verbose_name='景点名称')
    value = models.FloatField(null=True, verbose_name='热度评分')

    class Meta:
        db_table = 'part7'
        managed = False


class Part8(models.Model):
    """省份平均评分表"""
    name = models.CharField(max_length=100, null=True, verbose_name='省份')
    travel_num = models.IntegerField(null=True, verbose_name='景点数量')
    avg_score = models.FloatField(null=True, verbose_name='平均评分')

    class Meta:
        db_table = 'part8'
        managed = False