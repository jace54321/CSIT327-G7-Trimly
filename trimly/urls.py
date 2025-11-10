from django.contrib import admin
from django.urls import path
from main import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path("admin/", admin.site.urls),
    
    # Landing & Auth
    path("", views.landing_view, name="landing"),
    path('auth/', views.auth_view, name='auth'),
    path("login/", views.login_view, name="login"),
    path("register/", views.registration_view, name="register"),
    path("logout/", views.logout_view, name="logout"),

    # Password Reset - All Django Built-in
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(
            template_name="registration/password_reset_form.html",
            email_template_name="registration/password_reset_email.html",  # <-- custom email body template
            subject_template_name="registration/password_reset_subject.txt",  # <-- custom subject template
            html_email_template_name="registration/password_reset_email.html",  # optional for HTML emails, same as above if styled
        ),
        name="password_reset",
    ),

    
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='registration/password_reset_done.html'
    ), name='password_reset_done'),
    
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='registration/password_reset_confirm.html'
    ), name='password_reset_confirm'),
    
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(
        template_name='registration/password_reset_complete.html'
    ), name='password_reset_complete'),
    
    # Customer & Barber Dashboards
    path("dashboard/customer/", views.customer_dashboard, name="customer_dashboard"),
    path("dashboard/barber/", views.barber_dashboard, name="barber_dashboard"),
    path('dashboard/barber/toggle-availability/', views.toggle_availability, name='toggle_availability'),
    path('dashboard/barber/api/', views.barber_dashboard_api, name='barber_dashboard_api'),
    path('dashboard/barber/schedule/', views.barber_schedule_view, name='barber_schedule'),
    path('dashboard/barber/availability/', views.manage_weekly_availability, name='manage_weekly_availability'),
    path('dashboard/barber/quick-actions/', views.quick_actions_view, name='quick_actions'),
    
    # Booking actions
    path("bookings/create/", views.create_booking_view, name="create_booking"),
    path("bookings/<int:booking_id>/cancel/", views.cancel_booking_view, name="cancel_booking"),
    path("bookings/<int:booking_id>/reschedule/", views.reschedule_booking_view, name="reschedule_booking"),
    path("bookings/<int:booking_id>/update-status/", views.update_booking_status, name="update_booking_status"),
    path("bookings/<int:booking_id>/rate/", views.submit_rating_view, name="submit_rating"),
    path('api/get-slots/<int:barber_id>/<str:date_str>/', views.get_available_slots_api, name='get_available_slots_api'),
]
