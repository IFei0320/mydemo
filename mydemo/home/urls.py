from django.contrib import admin
from django.urls import path
from home import views

app_name ='home'
urlpatterns = [

    path('',views.index),
    path( 'index',views.index,name='index'),
    path('travel_list',views.travel_list,name='travel_list'),
    path('get_ai_travelRoute',views.get_ai_travelRoute,name='get_ai_travelRoute'),
    path('ai_nsga2_route', views.ai_nsga2_route_page, name='ai_nsga2_route'),
    path('api/generate_ai_nsga2_route', views.generate_ai_nsga2_route, name='generate_ai_nsga2_route'),
    path('api/select_ai_nsga2_plan', views.select_ai_nsga2_plan, name='select_ai_nsga2_plan'),
    path('api/export_to_dida_checklist', views.export_to_dida_checklist, name='export_to_dida_checklist'),

    ]