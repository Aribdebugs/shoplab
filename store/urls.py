from django.urls import path

from . import views

app_name = "store"   # namespace, so templates can use 'store:product_list'

urlpatterns = [
    path("", views.product_list, name="product_list"),
    path("product/<slug:slug>/", views.product_detail, name="product_detail"),
]
