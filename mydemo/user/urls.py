from django.contrib import admin
from django.urls import path
from user import views

app_name = 'user'
urlpatterns = [

    path('',views.login),
    path('login',views.login,name='login'),
    path('register',views.register,name='register')

    ]