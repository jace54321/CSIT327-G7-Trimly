from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import ServiceType, Customer, Barber, Schedule, Reservation


class CustomerInline(admin.StackedInline):
    """Inline admin for Customer profile"""
    model = Customer
    can_delete = False
    verbose_name_plural = 'Customer Profile'
    fields = ('phone_number', 'is_active')


class BarberInline(admin.StackedInline):
    """Inline admin for Barber profile"""
    model = Barber
    can_delete = False
    verbose_name_plural = 'Barber Profile'
    fields = ('experience_years', 'bio', 'phone_number', 'profile_picture', 
              'is_active', 'is_available_for_booking')


# Extend the default User admin
class UserAdmin(BaseUserAdmin):
    def get_inlines(self, request, obj):
        """Show different inlines based on user type"""
        inlines = []
        if obj:
            try:
                if hasattr(obj, 'customer_profile'):
                    inlines.append(CustomerInline)
                elif hasattr(obj, 'barber_profile'):
                    inlines.append(BarberInline)
            except:
                pass
        return inlines


# Re-register User with custom admin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)


@admin.register(ServiceType)
class ServiceTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'duration', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name',)
        }),
        ('Pricing & Duration', {
            'fields': ('price', 'duration')
        }),
        ('Description', {
            'fields': ('description',)
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    actions = ['make_active', 'make_inactive']
    
    def make_active(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} services marked as active.')
    make_active.short_description = "Mark selected services as active"
    
    def make_inactive(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} services marked as inactive.')
    make_inactive.short_description = "Mark selected services as inactive"


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('get_full_name', 'get_username', 'get_email', 'phone_number', 
                    'get_total_appointments', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('user__first_name', 'user__last_name', 'user__username',
                     'user__email', 'phone_number')
    readonly_fields = ('created_at', 'updated_at', 'get_total_appointments')
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('User Information', {
            'fields': ('user',)
        }),
        ('Contact Information', {
            'fields': ('phone_number',)
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Statistics', {
            'fields': ('get_total_appointments',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_full_name(self, obj):
        return obj.get_full_name()
    get_full_name.short_description = 'Full Name'
    get_full_name.admin_order_field = 'user__first_name'
    
    def get_username(self, obj):
        return obj.user.username
    get_username.short_description = 'Username'
    get_username.admin_order_field = 'user__username'
    
    def get_email(self, obj):
        return obj.user.email
    get_email.short_description = 'Email'
    get_email.admin_order_field = 'user__email'


@admin.register(Barber)
class BarberAdmin(admin.ModelAdmin):
    list_display = ('get_full_name', 'get_username', 'get_email', 'experience_years', 
                    'average_rating', 'is_active', 'is_available_for_booking')
    list_filter = ('is_active', 'is_available_for_booking', 'experience_years')
    search_fields = ('user__first_name', 'user__last_name', 'user__username',
                     'user__email', 'phone_number', 'bio')
    readonly_fields = ('created_at', 'updated_at', 'average_rating', 'total_ratings')
    
    fieldsets = (
        ('User Information', {
            'fields': ('user',)
        }),
        ('Professional Information', {
            'fields': ('experience_years', 'bio')
        }),
        ('Contact Information', {
            'fields': ('phone_number', 'profile_picture')
        }),
        ('Status', {
            'fields': ('is_active', 'is_available_for_booking')
        }),
        ('Ratings', {
            'fields': ('average_rating', 'total_ratings'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_full_name(self, obj):
        return obj.get_full_name()
    get_full_name.short_description = 'Full Name'
    get_full_name.admin_order_field = 'user__first_name'
    
    def get_username(self, obj):
        return obj.user.username
    get_username.short_description = 'Username'
    get_username.admin_order_field = 'user__username'
    
    def get_email(self, obj):
        return obj.user.email
    get_email.short_description = 'Email'
    get_email.admin_order_field = 'user__email'
    
    actions = ['make_available', 'make_unavailable']
    
    def make_available(self, request, queryset):
        updated = queryset.update(is_available_for_booking=True)
        self.message_user(request, f'{updated} barbers marked as available for booking.')
    make_available.short_description = "Mark selected barbers as available"
    
    def make_unavailable(self, request, queryset):
        updated = queryset.update(is_available_for_booking=False)
        self.message_user(request, f'{updated} barbers marked as unavailable for booking.')
    make_unavailable.short_description = "Mark selected barbers as unavailable"


@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display = ('barber', 'date', 'start_time', 'end_time', 'schedule_type',
                    'slot_duration', 'is_available')
    list_filter = ('schedule_type', 'is_available', 'date', 'barber')
    search_fields = ('barber__user__first_name', 'barber__user__last_name', 
                     'barber__user__username', 'notes')
    date_hierarchy = 'date'
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Barber & Date', {
            'fields': ('barber', 'date')
        }),
        ('Time Information', {
            'fields': ('start_time', 'end_time', 'schedule_type')
        }),
        ('Slot Configuration', {
            'fields': ('slot_duration', 'max_appointments')
        }),
        ('Status & Notes', {
            'fields': ('is_available', 'notes')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    actions = ['duplicate_schedule', 'make_available', 'make_unavailable']
    
    def duplicate_schedule(self, request, queryset):
        """Duplicate selected schedules for next week"""
        from datetime import timedelta
        count = 0
        for schedule in queryset:
            new_schedule = Schedule(
                barber=schedule.barber,
                date=schedule.date + timedelta(days=7),
                start_time=schedule.start_time,
                end_time=schedule.end_time,
                schedule_type=schedule.schedule_type,
                slot_duration=schedule.slot_duration,
                max_appointments=schedule.max_appointments,
                is_available=schedule.is_available,
                notes=schedule.notes
            )
            new_schedule.save()
            count += 1
        
        self.message_user(request, f'{count} schedules duplicated for next week.')
    duplicate_schedule.short_description = "Duplicate selected schedules for next week"
    
    def make_available(self, request, queryset):
        updated = queryset.update(is_available=True)
        self.message_user(request, f'{updated} schedules marked as available.')
    make_available.short_description = "Mark selected schedules as available"
    
    def make_unavailable(self, request, queryset):
        updated = queryset.update(is_available=False)
        self.message_user(request, f'{updated} schedules marked as unavailable.')
    make_unavailable.short_description = "Mark selected schedules as unavailable"


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ('id', 'get_customer_name', 'get_barber_name', 'appointment_datetime', 
                    'service_type', 'booking_source', 'status', 'price')
    list_filter = ('status', 'booking_source', 'service_type', 'appointment_datetime', 'barber')
    search_fields = ('customer__user__first_name', 'customer__user__last_name',
                     'customer__user__username', 'barber__user__first_name', 
                     'barber__user__last_name', 'barber__user__username',
                     'service_description')
    date_hierarchy = 'appointment_datetime'
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Reservation Details', {
            'fields': ('customer', 'barber', 'service_type', 'appointment_datetime', 'duration')
        }),
        ('Service Information', {
            'fields': ('service_description', 'price')
        }),
        ('Booking Information', {
            'fields': ('booking_source',)
        }),
        ('Status', {
            'fields': ('status',)
        }),
        ('Cancellation Details', {
            'fields': ('cancellation_reason', 'cancelled_at', 'cancelled_by'),
            'classes': ('collapse',)
        }),
        ('Feedback', {
            'fields': ('rating', 'feedback'),
            'classes': ('collapse',)
        }),
        ('Notifications', {
            'fields': ('confirmation_sent', 'reminder_sent'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_customer_name(self, obj):
        return obj.customer.get_full_name()
    get_customer_name.short_description = 'Customer'
    get_customer_name.admin_order_field = 'customer__user__first_name'
    
    def get_barber_name(self, obj):
        return obj.barber.get_full_name()
    get_barber_name.short_description = 'Barber'
    get_barber_name.admin_order_field = 'barber__user__first_name'
    
    actions = ['confirm_reservations', 'mark_completed', 'send_reminders']
    
    def confirm_reservations(self, request, queryset):
        updated = queryset.filter(status='pending').update(status='confirmed')
        self.message_user(request, f'{updated} reservations confirmed.')
    confirm_reservations.short_description = "Confirm selected reservations"
    
    def mark_completed(self, request, queryset):
        updated = queryset.filter(status='confirmed').update(status='completed')
        self.message_user(request, f'{updated} reservations marked as completed.')
    mark_completed.short_description = "Mark selected reservations as completed"
    
    def send_reminders(self, request, queryset):
        count = 0
        for reservation in queryset:
            if not reservation.reminder_sent and reservation.status == 'confirmed':
                # Here you would implement your reminder sending logic
                # For now, we just mark as reminder sent
                reservation.reminder_sent = True
                reservation.save()
                count += 1
        
        self.message_user(request, f'Reminders sent for {count} reservations.')
    send_reminders.short_description = "Send reminders for selected reservations"


# Customize admin site header
admin.site.site_header = "Haircut Booking System Administration"
admin.site.site_title = "Booking Admin"
admin.site.index_title = "Welcome to Haircut Booking Administration"
