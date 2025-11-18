from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
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
    path('bookings/<int:booking_id>/reject/', views.barber_reject_booking, name='reject_booking'),


    #-------ADMIN URL-------
    path('admin-dashboard/', views.admin_dashboard_view, name='admin_dashboard'),
    path('admin-dashboard/customer/create/', views.admin_create_customer_view, name='admin_create_customer'),
    path('admin-dashboard/customer/edit/<int:user_id>/', views.admin_edit_customer_view, name='admin_edit_customer'),
    path('admin-dashboard/customer/delete/<int:user_id>/', views.admin_delete_customer_view, name='admin_delete_customer'),
    path('admin-dashboard/barber/create/', views.admin_create_barber_view, name='admin_create_barber'),
    path('admin-dashboard/barber/edit/<int:user_id>/', views.admin_edit_barber_view, name='admin_edit_barber'),
    path('admin-dashboard/barber/delete/<int:user_id>/', views.admin_delete_barber_view, name='admin_delete_barber'),
    path('admin-dashboard/service/create/', views.admin_create_service_view, name='admin_create_service'),
    path('admin-dashboard/service/edit/<int:service_id>/', views.admin_edit_service_view, name='admin_edit_service'),
    path('admin-dashboard/service/delete/<int:service_id>/', views.admin_delete_service_view, name='admin_delete_service'),
    path('admin-dashboard/booking/update/<int:booking_id>/', views.admin_update_booking_status, name='admin_update_booking_status'),
    path('admin-dashboard/user/reset-password/<int:user_id>/', views.admin_reset_password_view, name='admin_reset_password'),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)


