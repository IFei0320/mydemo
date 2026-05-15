
from django.contrib import admin
from .models import TravelInfo



class TravelInfoAdmin(admin.ModelAdmin):
    # 列表中显示的字段
    list_display = (
        'name',
        'city',
        'province',
        'rating',
        'review_count',
        'actual_price',
        'is_free',
        'popularity_score'
    )

    # 可以点击进入编辑页面的字段
    list_display_links = ('name', 'city')

    # 可筛选的字段
    list_filter = (
        'province',
        'city',
        'is_free',
        'is_ad',
        'is_recommended'
    )

    # 可搜索的字段
    search_fields = (
        'name',
        'city',
        'province',
        'tags'
    )

    # 分页设置（每页显示多少条记录）
    list_per_page = 50

    # 按某些字段排序（默认排序）
    ordering = ('-review_count',)

    # 编辑页面的字段分组布局
    fieldsets = (
        ('基本信息', {
            'fields': ('name', 'city', 'province', 'area', 'tags')
        }),
        ('评分与热度', {
            'fields': ('rating', 'review_count', 'popularity_score', 'is_recommended')
        }),
        ('价格信息', {
            'fields': ('market_price', 'discount_price', 'actual_price', 'is_free')
        }),
        ('位置信息', {
            'fields': ('longitude', 'latitude', 'distance_from_center')
        }),
        ('其他信息', {
            'fields': ('is_ad', 'image_url', 'detail_link')
        }),
    )

# 注册模型和对应的Admin类
admin.site.register(TravelInfo, TravelInfoAdmin)
from django.contrib import admin

# Register your models here.
