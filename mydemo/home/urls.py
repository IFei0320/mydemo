from django.contrib import admin
from django.urls import path

from home import views, views_dida, views_nsga2, views_wiki
app_name ='home'
urlpatterns = [

    path('',views.index),
    path( 'index',views.index,name='index'),
    path('travel_list',views.travel_list,name='travel_list'),
    path('get_ai_travelRoute',views.get_ai_travelRoute,name='get_ai_travelRoute'),
    path('ai_nsga2_route', views_nsga2.ai_nsga2_route_page, name='ai_nsga2_route'),
    path('api/generate_ai_nsga2_route', views_nsga2.generate_ai_nsga2_route, name='generate_ai_nsga2_route'),
    path('api/select_ai_nsga2_plan', views_nsga2.select_ai_nsga2_plan, name='select_ai_nsga2_plan'),
    path('api/export_to_dida_checklist', views_dida.export_to_dida_checklist, name='export_to_dida_checklist'),
    path('wiki_mvp', views_wiki.wiki_mvp_page, name='wiki_mvp'),
    path('api/wiki/ingest', views_wiki.wiki_ingest, name='wiki_ingest'),
    path('api/wiki/query', views_wiki.wiki_query, name='wiki_query'),
    path('api/wiki/lint', views_wiki.wiki_lint, name='wiki_lint'),

    ]
