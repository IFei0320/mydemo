from django.contrib import admin
from django.utils.html import format_html

from user.models import UserInfo


class UserInfoAdmin(admin.ModelAdmin):
    list_display = ('username', 'uemail', 'uphone', 'uaddress', 'created_at', 'show_avatar')

    list_display_links = ('username','uemail')

    list_filter = ( 'created_at',)

    search_fields = ('username', 'uemail', 'uphone')

    list_per_page = 10

    ordering = ('-created_at',)

    fieldsets = (
        ('基本信息', {
            'fields': ('username', 'email', 'avatar'),
            'description': '用户的核心基本信息'
        }),
        ('联系信息', {
            'fields': ('phone', 'address', 'postcode'),
            'classes': ('collapse',),
            'description': '用户的联系方式'
        }),
        ('其他信息', {
            'fields': ('created_at',),
            'classes': ('collapse',),
        }),
    )

    def show_avatar(self, obj):
        if obj.avatar:
            return format_html(
                '<img src="{}" style="max-height:50px;max-width:50px;border-radius:50%;" />',
                obj.avatar.url if hasattr(obj.avatar, 'url') else obj.avatar
            )
        return format_html('<span style="color:gray;">无头像</span>')

    show_avatar.short_description = '头像'
    show_avatar.admin_order_field = 'avatar'


admin.site.register(UserInfo, UserInfoAdmin)
