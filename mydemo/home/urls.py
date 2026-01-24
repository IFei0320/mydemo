from django.contrib import admin
from django.urls import path
from home import views

app_name ='home'
urlpatterns = [

    path('',views.index),
    path( 'index',views.index,name='index'),
    path('travel_list',views.travel_list,name='travel_list')

    ]