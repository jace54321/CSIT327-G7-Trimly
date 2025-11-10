from django.contrib import admin
from django.urls import path
from main import views
from django.shortcuts import redirect

urlpatterns = [
    path("admin/", admin.site.urls),
    
    # Landing & Auth (From main branch)
    path("", views.landing_view, name="landing"),
    path('auth/', views.auth_view, name='auth'),  # Single page for both
    path("login/", views.login_view, name="login"),
    path("register/", views.registration_view, name="register"),
    path("logout/", views.logout_view, name="logout"),
    
    # Customer Dashboard (From main branch)
    path("dashboard/customer/", views.customer_dashboard, name="customer_dashboard"),

    # Barber Dashboard & API URLs (Merged from both branches)
    path("dashboard/barber/", views.barber_dashboard, name="barber_dashboard"),
    path('dashboard/barber/toggle-availability/', views.toggle_availability, name='toggle_availability'),
    path('dashboard/barber/api/', views.barber_dashboard_api, name='barber_dashboard_api'),
    path('dashboard/barber/schedule/', views.barber_schedule_view, name='barber_schedule'),
    path('dashboard/barber/quick-actions/', views.quick_actions_view, name='quick_actions'),
    
    # Booking actions (From your branch)
    path("bookings/create/", views.create_booking_view, name="create_booking"),
    path("bookings/<int:booking_id>/cancel/", views.cancel_booking_view, name="cancel_booking"),
    path("bookings/<int:booking_id>/reschedule/", views.reschedule_booking_view, name="reschedule_booking"),
    path("bookings/<int:booking_id>/update-status/", views.update_booking_status, name="update_booking_status"),
    path("bookings/<int:booking_id>/rate/", views.submit_rating_view, name="submit_rating"),
]