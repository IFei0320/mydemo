from django.db import models

# Create your models here.
from django.db import models
from django.utils import timezone

class UserInfo(models.Model):
    username = models.CharField(max_length=20, verbose_name='用户名')
    password = models.CharField(max_length=40, verbose_name='密码')
    uemail = models.CharField(max_length=40, verbose_name='邮箱')
    uaddress = models.CharField(max_length=30, verbose_name='地址', default='')
    uyoubian = models.CharField(max_length=30, verbose_name='邮编', default='')
    uphone = models.CharField(max_length=11, verbose_name='手机号', default='')
    avatar = models.CharField(max_length=255, verbose_name='头像', default='')
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.username

    # 后台管理页面显示
    class Meta:
        verbose_name_plural = '用户管理'