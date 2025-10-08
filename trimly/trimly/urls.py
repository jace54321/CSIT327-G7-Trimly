from django.contrib import admin
from django.urls import path
from main import views
from django.shortcuts import redirect

urlpatterns = [
    path("admin/", admin.site.urls),

    # Landing page as start page
    path("", views.landing_view, name="landing"),

    # Auth + dashboards
    path("login/", views.login_view, name="login"),
    path("register/", views.registration_view, name="register"),
    path("dashboard/barber/", views.barber_dashboard, name="barber_dashboard"),
    path("dashboard/customer/", views.customer_dashboard, name="customer_dashboard"),
    path("logout/", views.logout_view, name="logout"),
]
