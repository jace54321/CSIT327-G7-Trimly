import re
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from .models import Barber, Customer, Reservation, ServiceType
from django.contrib import messages
from django.db import IntegrityError
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator
from django.utils import timezone
from datetime import datetime, timedelta
from django.shortcuts import render, redirect

# -------------------------------
# View to display the landing page
# -------------------------------
def landing_view(request):
    # Bypass redirect if explicitly requested
    if request.GET.get("show") == "landing":
        return render(request, "landing.html")

    if request.user.is_authenticated:
        if hasattr(request.user, "barber_profile"):
            return redirect("barber_dashboard")
        if hasattr(request.user, "customer_profile"):
            return redirect("customer_dashboard")
    return render(request, "landing.html")

# -------------------------------
# Handles user registration
# -------------------------------
def registration_view(request):
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        phone_number = request.POST.get("phone_number", "").strip()
        password = request.POST.get("password", "")
        confirm_password = request.POST.get("confirm-password", "")
        role = request.POST.get("role", "")

        errors = []

        if not all([username, email, first_name, last_name, phone_number, password, confirm_password, role]):
            errors.append("All fields are required.")

        if phone_number:
            try:
                clean_phone = validate_phone_number(phone_number)
            except ValidationError as e:
                errors.extend(e.messages)

        if password != confirm_password:
            errors.append("Passwords do not match.")

        if email:
            try:
                EmailValidator(message="Enter a valid email address.")(email)
            except ValidationError:
                errors.append("Enter a valid email address.")

        if User.objects.filter(username=username).exists():
            errors.append("Username already taken.")
        if User.objects.filter(email=email).exists():
            errors.append("Email already registered.")

        if phone_number:
            try:
                clean_phone = validate_phone_number(phone_number)
                if (Customer.objects.filter(phone_number=clean_phone).exists() or
                    Barber.objects.filter(phone_number=clean_phone).exists()):
                    errors.append("Phone number already registered.")
            except ValidationError:
                pass

        if password:
            try:
                validate_password(password)
            except ValidationError as e:
                errors.extend(e.messages)

        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'registration.html')

        try:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name
            )
            
            clean_phone = validate_phone_number(phone_number)
            
            if role == "barber":
                Barber.objects.create(user=user, phone_number=clean_phone)
            elif role == "customer":
                Customer.objects.create(user=user, phone_number=clean_phone)
            
            messages.success(request, "Registration successful! You can now log in.")
            return redirect("login")
        
        except IntegrityError:
            messages.error(request, "Registration unsuccessful! Please try again.")
            return render(request, 'registration.html')
    
    return render(request, 'registration.html')

# -------------------------------
# Handles user login
# -------------------------------
def login_view(request):
    if request.method == "POST":
        email_or_username = request.POST.get("email")
        password = request.POST.get("password")
        
        user_exists = False
        try:
            user_obj = User.objects.get(email=email_or_username)
            username = user_obj.username
            user_exists = True
        except User.DoesNotExist:
            if User.objects.filter(username=email_or_username).exists():
                user_exists = True
                username = email_or_username
            else:
                username = None
        
        if not user_exists:
            return render(request, "login.html", {"user_not_found": True})
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            if hasattr(user, "barber_profile"):
                return redirect("barber_dashboard")
            elif hasattr(user, "customer_profile"):
                return redirect("customer_dashboard")
        
        return render(request, "login.html", {"wrong_password": True})
    
    return render(request, "login.html")

# -------------------------------
# Customer dashboard (Python-only)
# -------------------------------
@login_required(login_url='login')
def customer_dashboard(request):
    try:
        customer = request.user.customer_profile
        now = timezone.now()
        
        # Get upcoming bookings
        upcoming_bookings = Reservation.objects.filter(
            customer=customer,
            appointment_datetime__gte=now,
            status__in=['pending', 'confirmed', 'rescheduled']
        ).select_related('barber__user', 'service_type').order_by('appointment_datetime')
        
        # Get past bookings
        past_bookings = Reservation.objects.filter(
            customer=customer,
            appointment_datetime__lt=now,
        ).select_related('barber__user', 'service_type').order_by('-appointment_datetime')[:10]
        
        # Get active services
        services = ServiceType.objects.filter(is_active=True).order_by('name')
        
        # Get available barbers
        barbers = Barber.objects.filter(is_active=True, is_available_for_booking=True).select_related('user')
        
        # Handle query parameters for detail view and reschedule
        selected_booking = None
        reschedule_booking = None
        
        # View booking detail
        view_id = request.GET.get('view')
        if view_id:
            try:
                selected_booking = Reservation.objects.select_related(
                    'barber__user', 'service_type'
                ).get(id=view_id, customer=customer)
            except Reservation.DoesNotExist:
                messages.error(request, "Booking not found.")
        
        # Reschedule mode
        reschedule_id = request.GET.get('reschedule')
        if reschedule_id:
            try:
                reschedule_booking = Reservation.objects.select_related(
                    'barber__user', 'service_type'
                ).get(id=reschedule_id, customer=customer)
                
                if not reschedule_booking.can_be_cancelled():
                    messages.error(request, "Cannot reschedule booking within 24 hours of appointment time.")
                    return redirect('customer_dashboard')
                    
            except Reservation.DoesNotExist:
                messages.error(request, "Booking not found.")
                return redirect('customer_dashboard')
        
        context = {
            'customer': customer,
            'upcoming_bookings': upcoming_bookings,
            'past_bookings': past_bookings,
            'services': services,
            'barbers': barbers,
            'now': now,
            'today': timezone.now().date(),
            'selected_booking': selected_booking,
            'reschedule_booking': reschedule_booking,
        }
        
         # NEW: Check if showing booking form
        show_booking_form = request.GET.get('action') == 'book'
        
        context = {
            'customer': customer,
            'upcoming_bookings': upcoming_bookings,
            'past_bookings': past_bookings,
            'services': services,
            'barbers': barbers,
            'now': now,
            'today': timezone.now().date(),
            'selected_booking': selected_booking,
            'reschedule_booking': reschedule_booking,
            'show_booking_form': show_booking_form,  # NEW
        }
        
        return render(request, "customer_dashboard.html", context)
    
    except Customer.DoesNotExist:
        messages.error(request, "Customer profile not found. Please contact support.")
        return redirect("login")

        
@login_required(login_url='login')
def create_booking_view(request):
    """Create a new booking"""
    if request.method != 'POST':
        return redirect('customer_dashboard')
    
    try:
        customer = request.user.customer_profile
        
        # Get form data
        service_id = request.POST.get('service_id')
        barber_id = request.POST.get('barber_id')
        appointment_date_str = request.POST.get('appointment_date')
        appointment_time_str = request.POST.get('appointment_time')
        notes = request.POST.get('notes', '').strip()
        
        # Validate required fields
        if not all([service_id, barber_id, appointment_date_str, appointment_time_str]):
            messages.error(request, 'All fields are required.')
            return redirect('customer_dashboard', '?action=book')
        
        # Get service and barber
        service = get_object_or_404(ServiceType, id=service_id, is_active=True)
        barber = get_object_or_404(Barber, id=barber_id, is_active=True, is_available_for_booking=True)
        
        # Parse datetime
        try:
            appointment_date = datetime.strptime(appointment_date_str, '%Y-%m-%d').date()
            appointment_time = datetime.strptime(appointment_time_str, '%H:%M').time()
            appointment_datetime = timezone.make_aware(datetime.combine(appointment_date, appointment_time))
        except ValueError:
            messages.error(request, 'Invalid date or time format.')
            return redirect('customer_dashboard', '?action=book')
        
        # Validate appointment is in the future
        if appointment_datetime < timezone.now():
            messages.error(request, 'Cannot book appointments in the past.')
            return redirect('customer_dashboard', '?action=book')
        
        # Validate business hours (9 AM - 6 PM)
        if appointment_time.hour < 9 or appointment_time.hour >= 18:
            messages.error(request, 'Please select a time between 9:00 AM and 6:00 PM.')
            return redirect('customer_dashboard', '?action=book')
        
        # Create reservation
        reservation = Reservation.objects.create(
            customer=customer,
            barber=barber,
            service_type=service,
            appointment_datetime=appointment_datetime,
            duration=service.duration,
            price=service.price,
            service_description=notes,
            status='confirmed'
        )
        
        messages.success(request, 
            f'Booking confirmed! Your {service.name} appointment with {barber.get_full_name()} '
            f'is scheduled for {appointment_datetime.strftime("%B %d, %Y at %I:%M %p")}.')
        
        return redirect('customer_dashboard')
    
    except Customer.DoesNotExist:
        messages.error(request, 'Customer profile not found.')
        return redirect('login')
    except Exception as e:
        messages.error(request, f'An error occurred: {str(e)}')
        return redirect('customer_dashboard', '?action=book')

# -------------------------------
# Cancel booking (POST only)
# -------------------------------
@login_required(login_url='login')
def cancel_booking_view(request, booking_id):
    if request.method != 'POST':
        return redirect('customer_dashboard')
    
    try:
        customer = request.user.customer_profile
        booking = get_object_or_404(
            Reservation,
            id=booking_id,
            customer=customer
        )
        
        # Check if booking can be cancelled
        if not booking.can_be_cancelled():
            messages.error(request, 'Cannot cancel booking within 24 hours of appointment time.')
            return redirect('customer_dashboard')
        
        # Cancel the booking
        success = booking.cancel(
            cancelled_by=request.user, 
            reason='Customer requested cancellation'
        )
        
        if success:
            messages.success(request, f'Booking for {booking.service_type.name} on {booking.appointment_datetime.strftime("%B %d, %Y")} has been cancelled.')
        else:
            messages.error(request, 'Unable to cancel booking. Please contact support.')
    
    except Customer.DoesNotExist:
        messages.error(request, 'Customer profile not found.')
    except Exception as e:
        messages.error(request, f'An error occurred: {str(e)}')
    
    return redirect('customer_dashboard')

# -------------------------------
# Reschedule booking (POST only)
# -------------------------------
@login_required(login_url='login')
def reschedule_booking_view(request, booking_id):
    if request.method != 'POST':
        return redirect('customer_dashboard')
    
    try:
        customer = request.user.customer_profile
        booking = get_object_or_404(
            Reservation.objects.select_related('barber__user', 'service_type'),
            id=booking_id,
            customer=customer
        )
        
        # Check if can be rescheduled
        if not booking.can_be_cancelled():
            messages.error(request, 'Cannot reschedule booking within 24 hours of appointment time.')
            return redirect('customer_dashboard')
        
        # Get new date and time from POST
        new_date_str = request.POST.get('new_date')
        new_time_str = request.POST.get('new_time')
        
        if not new_date_str or not new_time_str:
            messages.error(request, 'Date and time are required.')
            return redirect('customer_dashboard', f'?reschedule={booking_id}')
        
        try:
            # Parse datetime
            new_date = datetime.strptime(new_date_str, '%Y-%m-%d').date()
            new_time = datetime.strptime(new_time_str, '%H:%M').time()
            new_datetime = timezone.make_aware(datetime.combine(new_date, new_time))
            
            # Validate that new datetime is in the future
            if new_datetime < timezone.now():
                messages.error(request, 'Cannot reschedule to a past date/time.')
                return redirect('customer_dashboard', f'?reschedule={booking_id}')
            
            # Validate business hours (9 AM - 6 PM)
            if new_time.hour < 9 or new_time.hour >= 18:
                messages.error(request, 'Please select a time between 9:00 AM and 6:00 PM.')
                return redirect('customer_dashboard', f'?reschedule={booking_id}')
            
            # Update booking
            old_datetime = booking.appointment_datetime
            booking.appointment_datetime = new_datetime
            booking.status = 'rescheduled'
            booking.save()
            
            messages.success(request, 
                f'Booking rescheduled from {old_datetime.strftime("%B %d, %Y at %I:%M %p")} '
                f'to {new_datetime.strftime("%B %d, %Y at %I:%M %p")}.')
        
        except ValueError:
            messages.error(request, 'Invalid date or time format.')
            return redirect('customer_dashboard', f'?reschedule={booking_id}')
    
    except Customer.DoesNotExist:
        messages.error(request, 'Customer profile not found.')
    except Exception as e:
        messages.error(request, f'An error occurred: {str(e)}')
    
    return redirect('customer_dashboard')

# -------------------------------
# Barber dashboard
# -------------------------------
@login_required(login_url='login')
def barber_dashboard(request):
    return render(request, "barber_dashboard.html")

# -------------------------------
# Logout
# -------------------------------
def logout_view(request):
    logout(request)
    return redirect("login")

# -------------------------------
# Phone number validator
# -------------------------------
def validate_phone_number(phone_number):
    if not phone_number:
        raise ValidationError("Phone number is required.")
    
    clean_phone = re.sub(r'[\s\-]', '', phone_number)
    
    if not re.match(r'^09[0-9]{9}$', clean_phone):
        raise ValidationError(
            "Phone number must start with 09 and contain exactly 11 digits (e.g., 09123456789)."
        )
    
    return clean_phone
