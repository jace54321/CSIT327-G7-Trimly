from django.contrib import admin
from django.urls import path
from main import views
from django.shortcuts import redirect

urlpatterns = [
    path("admin/", admin.site.urls),
    
    # Landing & Auth
    path("", views.landing_view, name="landing"),
    path("login/", views.login_view, name="login"),
    path("register/", views.registration_view, name="register"),
    path("logout/", views.logout_view, name="logout"),
    
    # Dashboards
    path("dashboard/barber/", views.barber_dashboard, name="barber_dashboard"),
    path("dashboard/customer/", views.customer_dashboard, name="customer_dashboard"),
    path("logout/", views.logout_view, name="logout"),
     path('dashboard/barber/toggle-availability/', views.toggle_availability, name='toggle_availability'),
    
    # Booking actions (POST only)
    path("bookings/<int:booking_id>/cancel/", views.cancel_booking_view, name="cancel_booking"),
    path("bookings/<int:booking_id>/reschedule/", views.reschedule_booking_view, name="reschedule_booking"),

       # NEW: Booking creation
    path("bookings/create/", views.create_booking_view, name="create_booking"),
]
