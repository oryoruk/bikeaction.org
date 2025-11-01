from django.urls import path

from pages import views

urlpatterns = [
    path("", views.index, name="index"),
    path("brand/", views.brand, name="brand"),
    path("archive/safe-streets-ride/", views.safe_streets_ride),
    path("archive/safe-streets-ride/inner/", views.safe_streets_ride_inner),
]
