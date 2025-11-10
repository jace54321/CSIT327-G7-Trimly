from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import datetime, timedelta


class ServiceType(models.Model):
    """
    Service type model for managing service prices centrally
    Owner can modify prices and add new services here
    """
    name = models.CharField(max_length=50, unique=True, help_text="Service name (e.g., Haircut)")
    price = models.DecimalField(max_digits=6, decimal_places=2, help_text="Price for this service")
    duration = models.PositiveIntegerField(default=30, help_text="Default duration in minutes")
    description = models.TextField(blank=True, help_text="Service description")
    is_active = models.BooleanField(default=True, help_text="Is this service available for booking")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Service Type"
        verbose_name_plural = "Service Types"
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} - ₱{self.price}"


class Barber(models.Model):
    """
    Barber model for individual barber system
    OneToOne with User provides: username, email, password, first_name, last_name
    """
    # OneToOne relationship with Django User model (REQUIRED)
    # This gives access to username, email, password, first_name, last_name
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='barber_profile')
    
    # Professional information
    experience_years = models.IntegerField(default=0, help_text="Years of experience")
    bio = models.TextField(blank=True, help_text="Professional biography and specialties")
    
    # Contact information
    phone_number = models.CharField(
        max_length=15,
        validators=[RegexValidator(regex=r'^\+?1?\d{9,15}$', 
                   message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed.")],
        blank=True,
        null=True,
        help_text="Contact phone number"
    )
    profile_picture = models.ImageField(upload_to='barber_profiles/', null=True, blank=True)

    # Status and availability
    is_active = models.BooleanField(default=True)
    is_available_for_booking = models.BooleanField(default=True)
    
    # Ratings (calculated from customer feedback)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    total_ratings = models.PositiveIntegerField(default=0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Barber"
        verbose_name_plural = "Barbers"
    
    def __str__(self):
        return f"Barber: {self.user.username}"
    
    def get_full_name(self):
        """Get full name from related User model"""
        return f"{self.user.first_name} {self.user.last_name}".strip() or self.user.username
    
    def update_rating(self):
        """Update average rating based on completed reservations"""
        completed_reservations = self.reservations.filter(
            status='completed',
            rating__isnull=False
        )
        if completed_reservations.exists():
            avg_rating = completed_reservations.aggregate(
                avg_rating=models.Avg('rating')
            )['avg_rating']
            self.average_rating = round(avg_rating, 2)
            self.total_ratings = completed_reservations.count()
            self.save()


class Customer(models.Model):
    """
    Customer model extending Django's built-in User model
    OneToOne with User provides: username, email, password, first_name, last_name
    """
    # OneToOne relationship with Django User model (REQUIRED)
    # This gives access to username, email, password, first_name, last_name
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='customer_profile')
    
    # Contact information
    phone_number = models.CharField(
        max_length=15,
        validators=[RegexValidator(regex=r'^\+?1?\d{9,15}$', 
                   message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed.")],
        blank=True,
        null=True,
        help_text="Contact phone number"
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Customer"
        verbose_name_plural = "Customers"
        ordering = ['user__first_name', 'user__last_name']
    
    def __str__(self):
        return f"Customer: {self.user.username}"
    
    def get_full_name(self):
        """Get full name from related User model"""
        return f"{self.user.first_name} {self.user.last_name}".strip() or self.user.username
    
    def get_total_appointments(self):
        """Get total number of reservations for this customer"""
        return self.reservations.count()


class Schedule(models.Model):
    """
    Schedule model for defining barber availability
    """
    # ForeignKey to Barber (REQUIRED)
    # One barber can have many schedules, but each schedule belongs to one barber
    barber = models.ForeignKey(Barber, on_delete=models.CASCADE, related_name='schedules')
    
    # Date and time information
    date = models.DateField(help_text="Date for this schedule")
    start_time = models.TimeField(help_text="Start time for availability")
    end_time = models.TimeField(help_text="End time for availability")
    
    # Schedule details
    SCHEDULE_TYPE_CHOICES = [
        ('regular', 'Regular Hours'),
        ('extended', 'Extended Hours'),
        ('special', 'Special Event'),
        ('break', 'Break Time'),
        ('unavailable', 'Unavailable'),
    ]
    schedule_type = models.CharField(max_length=20, choices=SCHEDULE_TYPE_CHOICES, 
                                   default='regular')
    
    # Availability settings
    slot_duration = models.PositiveIntegerField(default=30, 
                                              help_text="Duration of each appointment slot in minutes")
    max_appointments = models.PositiveIntegerField(default=None, null=True, blank=True,
                                                 help_text="Maximum appointments for this time slot")
    
    # Status
    is_available = models.BooleanField(default=True)
    notes = models.TextField(blank=True, help_text="Special notes for this schedule")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Schedule"
        verbose_name_plural = "Schedules"
        unique_together = ['barber', 'date', 'start_time', 'end_time']
        ordering = ['date', 'start_time']
    
    def __str__(self):
        return f"{self.barber.get_full_name()} - {self.date} ({self.start_time}-{self.end_time})"
    
    def clean(self):
        """Validate schedule data"""
        # Validate that end_time is after start_time
        if self.start_time >= self.end_time:
            raise ValidationError("End time must be after start time.")
        
        # Validate that the date is not in the past
        if self.date < timezone.now().date():
            raise ValidationError("Cannot create schedule for past dates.")
    
    def get_available_slots(self):
        """Return list of available time slots for this schedule"""
        if not self.is_available:
            return []
        
        slots = []
        current_time = datetime.combine(self.date, self.start_time)
        end_datetime = datetime.combine(self.date, self.end_time)
        
        while current_time < end_datetime:
            slot_end = current_time + timedelta(minutes=self.slot_duration)
            if slot_end <= end_datetime:
                # Check if this slot is already booked
                existing_reservation = Reservation.objects.filter(
                    barber=self.barber,
                    appointment_datetime=current_time,
                    status__in=['confirmed', 'in_progress']
                ).exists()
                
                if not existing_reservation:
                    slots.append(current_time.time())
            
            current_time += timedelta(minutes=self.slot_duration)
        
        return slots


class Reservation(models.Model):
    """
    Reservation model for booking appointments
    This is the main booking model that connects everything together
    """
    # ForeignKey relationships (ALL REQUIRED for a booking system)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='reservations',
                                help_text="Customer making the reservation")
    barber = models.ForeignKey(Barber, on_delete=models.CASCADE, related_name='reservations',
                              help_text="Barber providing the service")
    service_type = models.ForeignKey(ServiceType, on_delete=models.CASCADE, related_name='reservations',
                                   help_text="Type of service requested")
    
    # Appointment details
    appointment_datetime = models.DateTimeField(help_text="Date and time of the appointment")
    duration = models.PositiveIntegerField(default=30, help_text="Duration in minutes")
    service_description = models.TextField(blank=True, help_text="Specific requirements or notes")
    
    # Pricing (automatically set from service type)
    price = models.DecimalField(max_digits=6, decimal_places=2, 
                               help_text="Price for this reservation")
    
    # Status tracking
    STATUS_CHOICES = [
        ('pending', 'Pending Confirmation'),
        ('confirmed', 'Confirmed'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('no_show', 'No Show'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Cancellation details
    cancellation_reason = models.TextField(blank=True, null=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='cancelled_reservations',
                                   help_text="Who cancelled this reservation")
    
    # Feedback and rating
    rating = models.PositiveIntegerField(null=True, blank=True, 
                                       help_text="Rating from 1-5")
    feedback = models.TextField(blank=True, help_text="Customer feedback")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Notifications
    confirmation_sent = models.BooleanField(default=False)
    reminder_sent = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = "Reservation"
        verbose_name_plural = "Reservations"
        ordering = ['-appointment_datetime']
        indexes = [
            models.Index(fields=['appointment_datetime']),
            models.Index(fields=['status']),
            models.Index(fields=['barber', 'appointment_datetime']),
        ]
    
    def __str__(self):
        return f"{self.customer.get_full_name()} - {self.barber.get_full_name()} on {self.appointment_datetime}"
    
    def clean(self):
        """Validate reservation data"""
        # Validate that appointment is not in the past
        if self.appointment_datetime < timezone.now():
            raise ValidationError("Cannot make reservation for past date/time.")
        
        # Validate that barber is available at this time
        appointment_date = self.appointment_datetime.date()
        appointment_time = self.appointment_datetime.time()
        
        barber_schedules = Schedule.objects.filter(
            barber=self.barber,
            date=appointment_date,
            start_time__lte=appointment_time,
            end_time__gt=appointment_time,
            is_available=True
        )
        
        if not barber_schedules.exists():
            raise ValidationError("Barber is not available at the selected time.")
        
        # Check for conflicting reservations
        conflicting_reservations = Reservation.objects.filter(
            barber=self.barber,
            appointment_datetime=self.appointment_datetime,
            status__in=['confirmed', 'in_progress']
        ).exclude(pk=self.pk)
        
        if conflicting_reservations.exists():
            raise ValidationError("This time slot is already booked.")
    
    def save(self, *args, **kwargs):
        """Override save to set price and duration from service type"""
        # Set price and duration from service type if not already set
        if not self.price and self.service_type:
            self.price = self.service_type.price
        
        if self.duration == 30 and self.service_type:  # If still default duration
            self.duration = self.service_type.duration
        
        super().save(*args, **kwargs)
        
        # Update barber's rating if this reservation is completed and rated
        if self.status == 'completed' and self.rating:
            self.barber.update_rating()
    
    def can_be_cancelled(self):
        """Check if reservation can be cancelled (e.g., not within 24 hours)"""
        cancellation_deadline = self.appointment_datetime - timedelta(hours=24)
        return timezone.now() < cancellation_deadline
    
    def cancel(self, cancelled_by=None, reason=""):
        """Cancel the reservation"""
        if self.can_be_cancelled():
            self.status = 'cancelled'
            self.cancelled_at = timezone.now()
            self.cancelled_by = cancelled_by
            self.cancellation_reason = reason
            self.save()
            return True
        return False
    
    def get_end_time(self):
        """Get the end time of the appointment"""
        return self.appointment_datetime + timedelta(minutes=self.duration)
