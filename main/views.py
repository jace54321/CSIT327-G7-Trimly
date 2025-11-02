import re
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from .models import Barber, Customer, Reservation, ServiceType, Schedule 
from django.contrib import messages
from django.db import IntegrityError
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from django.utils import timezone
from django.urls import reverse
from datetime import datetime, timedelta
from django.db.models import F, ExpressionWrapper, DateTimeField, DurationField
from django.db.models import Q
from django.template.loader import render_to_string


# -------------------------------
# View to display the landing page
# -------------------------------
def landing_view(request):
    """
    Renders the landing page.
    """
    context = {"user": request.user}
    if request.user.is_authenticated:
        context["is_logged_in"] = True
    return render(request, "landing.html", context)


# -------------------------------
# Merged auth page view (Login/Register)
# -------------------------------
def auth_view(request):
    """Render the merged auth page with context for showing correct form"""
    # Check if we should show register form based on URL parameter
    show_register = request.GET.get('mode') == 'register'
    
    return render(request, "auth.html", {
        'show_register': show_register
    })


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

        # Validation
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

        # If there are errors -> stay on register form with entered data
        if errors:
            for error in errors:
                messages.error(request, error)

            context = {
                "show_register": True,  # 👈 Important for staying on the Sign Up tab
                "username": username,
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
                "phone_number": phone_number,
                "role": role,
            }
            return render(request, "auth.html", context)

        # If everything is valid -> create user
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
                redirect_url = "barber_dashboard"
            elif role == "customer":
                Customer.objects.create(user=user, phone_number=clean_phone)
                redirect_url = "customer_dashboard"
            else:
                redirect_url = "landing"

            # Automatically log in the user
            login(request, user)

            messages.success(request, "Registration successful! Welcome!")
            return redirect(redirect_url)

        except IntegrityError:
            messages.error(request, "Registration unsuccessful! Please try again.")
            context = {
                "show_register": True,  # 👈 stay on Sign Up even on error
                "username": username,
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
                "phone_number": phone_number,
                "role": role,
            }
            return render(request, "auth.html", context)

    # If GET request, show register form
    return render(request, "auth.html", {"show_register": True})


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
            messages.error(request, 'User not found. Please check your email or username.')
            return redirect('auth')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            if hasattr(user, "barber_profile"):
                return redirect("barber_dashboard")
            elif hasattr(user, "customer_profile"):
                return redirect("customer_dashboard")
            else:
                return redirect("landing")
        
        messages.error(request, 'Invalid password. Please try again.')
        return redirect('auth')
    
    # GET request - redirect to auth page
    return redirect('auth')


# -------------------------------
# Customer dashboard
# -------------------------------
@login_required(login_url='auth') # Using new 'auth' login URL
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
        rating_booking = None # <-- MERGED: Added from your branch
        
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
        
        # --- MERGED: Added this block from your branch ---
        # Rating mode
        rate_id = request.GET.get('rate')
        if rate_id:
            try:
                rating_booking = Reservation.objects.select_related(
                    'barber__user', 'service_type'
                ).get(id=rate_id, customer=customer)
                
                if rating_booking.status != 'completed':
                    messages.error(request, "You can only rate completed appointments.")
                    rating_booking = None
                elif rating_booking.rating is not None:
                     messages.error(request, "You have already rated this appointment.")
                     rating_booking = None
                     
            except Reservation.DoesNotExist:
                messages.error(request, "Booking not found.")
                return redirect('customer_dashboard')
        # --- End of MERGED block ---

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
            'rating_booking': rating_booking, # <-- MERGED: Added from your branch
            'show_booking_form': show_booking_form,
        }
        
        return render(request, "customer_dashboard.html", context)
    
    except Customer.DoesNotExist:
        messages.error(request, "Customer profile not found. Please contact support.")
        return redirect("auth") # Using new 'auth' login URL


# -------------------------------
# Create new booking
# -------------------------------
@login_required(login_url='auth') # Using new 'auth' login URL
def create_booking_view(request):
    """Create a new booking"""
    if request.method != 'POST':
        return redirect('customer_dashboard')
    
    # Add a redirect URL with the action parameter for error cases
    book_form_url = 'customer_dashboard'
    
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
            # MERGED: Using the better redirect from your branch
            return redirect(f"{reverse('customer_dashboard')}?action=book")
        
        # Get service and barber
        service = get_object_or_404(ServiceType, id=service_id, is_active=True)
        barber = get_object_or_404(Barber, id=barber_id, is_active=True)
        
        # Parse datetime
        try:
            appointment_date = datetime.strptime(appointment_date_str, '%Y-%m-%d').date()
            appointment_time = datetime.strptime(appointment_time_str, '%H:%M').time()
            appointment_datetime = timezone.make_aware(datetime.combine(appointment_date, appointment_time))
        except ValueError:
            messages.error(request, 'Invalid date or time format.')
            return redirect(f"{reverse('customer_dashboard')}?action=book")

        # --- MERGED: Using the advanced validation from your branch ---
        
        # Calculate appointment end time
        appointment_end_datetime = appointment_datetime + timedelta(minutes=service.duration)
        appointment_end_time = appointment_end_datetime.time()

        # Validate appointment is in the future
        if appointment_datetime < timezone.now():
            messages.error(request, 'Cannot book appointments in the past.')
            return redirect(f"{reverse('customer_dashboard')}?action=book")
        
        # VALIDATION 1: Check against Barber's Schedule
        is_available = Schedule.objects.filter(
            barber=barber,
            date=appointment_date,
            start_time__lte=appointment_time,      # Slot starts after or at schedule start
            end_time__gte=appointment_end_time,  # Slot ends before or at schedule end
            is_available=True
        ).exists()

        if not is_available:
            messages.error(request, f'The barber is not available at the selected time slot ({appointment_time_str} - {appointment_end_time.strftime("%H:%M")}).')
            return redirect(f"{reverse('customer_dashboard')}?action=book")

        # VALIDATION 2: Check for Conflicting Bookings
        conflicting_bookings = Reservation.objects.annotate(
            booking_end_time=ExpressionWrapper(
                F('appointment_datetime') + F('duration') * timedelta(minutes=1),
                output_field=DateTimeField()
            )
        ).filter(
            barber=barber,
            status__in=['pending', 'confirmed', 'in_progress'],
            appointment_datetime__lt=appointment_end_datetime,  # Existing booking starts before new one ends
            booking_end_time__gt=appointment_datetime         # Existing booking ends after new one starts
        )

        if conflicting_bookings.exists():
            messages.error(request, 'This time slot is already booked or overlaps with another appointment.')
            return redirect(f"{reverse('customer_dashboard')}?action=book")

        # --- End of MERGED validation ---
        
        # Create reservation
        reservation = Reservation.objects.create(
            customer=customer,
            barber=barber,
            service_type=service,
            appointment_datetime=appointment_datetime,
            duration=service.duration,
            price=service.price,
            service_description=notes,
            status='pending'  # Set to pending for barber approval
        )
        
        messages.success(request, 
            f'Booking request sent! Your {service.name} appointment with {barber.get_full_name()} '
            f'is scheduled for {appointment_datetime.strftime("%B %d, %Y at %I:%M %p")}.')
        
        return redirect('customer_dashboard')
    
    except Customer.DoesNotExist:
        messages.error(request, 'Customer profile not found.')
        return redirect('auth') # Using new 'auth' login URL
    except Exception as e:
        messages.error(request, f'An error occurred: {str(e)}')
        return redirect(f"{reverse('customer_dashboard')}?action=book")


# -------------------------------
# Toggle barber availability (AJAX)
# -------------------------------
@login_required
@csrf_exempt
def toggle_availability(request):
    """Toggle or set the barber's availability via AJAX"""
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            available = data.get('available', False)
            barber = Barber.objects.get(user=request.user)
            barber.is_available_for_booking = available
            barber.save()
            return JsonResponse({"success": True, "available": available})
        except Barber.DoesNotExist:
            return JsonResponse({"success": False, "error": "Barber not found"}, status=404)
    return JsonResponse({"success": False, "error": "Invalid request"}, status=400)


# -------------------------------
# Cancel booking (POST only)
# -------------------------------
@login_required(login_url='auth') # Using new 'auth' login URL
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
@login_required(login_url='auth') # Using new 'auth' login URL
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
            return redirect(f"{reverse('customer_dashboard')}?reschedule={booking_id}")
        
        try:
            # Parse datetime
            new_date = datetime.strptime(new_date_str, '%Y-%m-%d').date()
            new_time = datetime.strptime(new_time_str, '%H:%M').time()
            new_datetime = timezone.make_aware(datetime.combine(new_date, new_time))
            
            # Validate that new datetime is in the future
            if new_datetime < timezone.now():
                messages.error(request, 'Cannot reschedule to a past date/time.')
                return redirect(f"{reverse('customer_dashboard')}?reschedule={booking_id}")
            
            # MERGED: We will use the advanced validation from your branch,
            # so the simple "business hours" check is removed in favor of the
            # Schedule-based check which will be in create_booking_view
            
            # Update booking
            old_datetime = booking.appointment_datetime
            booking.appointment_datetime = new_datetime
            booking.status = 'rescheduled' # NOTE: You'll need to handle this status
            booking.save()
            
            messages.success(request, 
                f'Booking rescheduled from {old_datetime.strftime("%B %d, %Y at %I:%M %p")} '
                f'to {new_datetime.strftime("%B %d, %Y at %I:%M %p")}.')
        
        except ValueError:
            messages.error(request, 'Invalid date or time format.')
            return redirect(f"{reverse('customer_dashboard')}?reschedule={booking_id}")
    
    except Customer.DoesNotExist:
        messages.error(request, 'Customer profile not found.')
    except Exception as e:
        messages.error(request, f'An error occurred: {str(e)}')
    
    return redirect('customer_dashboard')


# -------------------------------
# --- MERGED: All functions below are from your branch ---
# -------------------------------

@login_required(login_url='auth') # Using new 'auth' login URL
def submit_rating_view(request, booking_id):
    """
    Handles submission of a rating for a completed booking.
    """
    if request.method != 'POST':
        return redirect('customer_dashboard')

    try:
        customer = request.user.customer_profile
        booking = get_object_or_404(
            Reservation.objects.select_related('barber'),
            id=booking_id,
            customer=customer
        )

        # Security checks
        if booking.status != 'completed':
            messages.error(request, "You can only rate completed appointments.")
            return redirect('customer_dashboard')
        
        if booking.rating is not None:
            messages.error(request, "You have already rated this appointment.")
            return redirect('customer_dashboard')

        # Get form data
        rating = request.POST.get('rating')
        feedback = request.POST.get('feedback', '').strip()

        if not rating:
            messages.error(request, "Please select a star rating.")
            
            # --- FIX ---
            # Manually build the redirect URL with the query string
            redirect_url = f"{reverse('customer_dashboard')}?rate={booking_id}"
            return redirect(redirect_url)
            # --- END FIX ---

        # Save the rating and feedback
        booking.rating = int(rating)
        booking.feedback = feedback
        booking.save() # This save() will trigger the update_rating() method

        messages.success(request, f"Thank you for your feedback! Rating submitted for booking #{booking.id}.")
        return redirect('customer_dashboard')

    except Customer.DoesNotExist:
        messages.error(request, 'Customer profile not found.')
    except Exception as e:
        messages.error(request, f'An error occurred: {str(e)}')
    
    return redirect('customer_dashboard')


# -------------------------------
# Barber dashboard
# -------------------------------

def _get_barber_dashboard_data(barber):
    """
    Helper function to get all context data for the barber dashboard.
    """
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    
    # Get all reservations for this barber
    all_reservations = Reservation.objects.filter(
        barber=barber
    ).select_related('customer__user', 'service_type').order_by('appointment_datetime')

    # --- Today's Schedule ---
    today_appointments = all_reservations.filter(
        appointment_datetime__gte=today_start,
        appointment_datetime__lt=today_end,
        status__in=['pending', 'confirmed', 'in_progress', 'completed', 'no_show'] # Added all statuses
    ).order_by('appointment_datetime')

    # --- Upcoming Appointments ---
    upcoming_appointments = all_reservations.filter(
        appointment_datetime__gte=today_end,
        status__in=['pending', 'confirmed']
    ).order_by('appointment_datetime')

    # --- Stats Cards ---
    stats_today_count = all_reservations.filter(
        appointment_datetime__gte=today_start,
        appointment_datetime__lt=today_end,
        status__in=['pending', 'confirmed', 'in_progress', 'completed']
    ).count()
    
    week_start = today_start - timedelta(days=now.weekday())
    week_end = week_start + timedelta(days=7)
    stats_week_count = all_reservations.filter(
        appointment_datetime__gte=week_start,
        appointment_datetime__lt=week_end,
        status__in=['pending', 'confirmed', 'in_progress', 'completed']
    ).count()

    stats_completed_count = all_reservations.filter(
        status='completed'
    ).count()

    return {
        'barber': barber,
        'today_appointments': today_appointments,
        'upcoming_appointments': upcoming_appointments,
        'stats_today_count': stats_today_count,
        'stats_week_count': stats_week_count,
        'stats_completed_count': stats_completed_count,
    }
    
@login_required(login_url='auth') # Using new 'auth' login URL
def barber_dashboard(request):
    try:
        barber = get_object_or_404(Barber, user=request.user)
    except Barber.DoesNotExist:
        messages.error(request, "Barber profile not found. Please contact support.")
        return redirect("auth") # Using new 'auth' login URL

    # Get all data from the helper function
    context = _get_barber_dashboard_data(barber)
    
    return render(request, "barber_dashboard.html", context)

@login_required
def barber_dashboard_api(request):
    """
    API endpoint to fetch updated dashboard components.
    """
    try:
        barber = get_object_or_404(Barber, user=request.user)
    except Barber.DoesNotExist:
        return JsonResponse({"success": False, "error": "Barber not found"}, status=404)

    # Get the latest data
    context = _get_barber_dashboard_data(barber)
    
    # Render the HTML snippets to strings
    html_stats = render_to_string("_barber_stats.html", context, request=request)
    html_today_schedule = render_to_string("_barber_today_schedule.html", context, request=request)
    html_upcoming_table = render_to_string("_barber_upcoming_table.html", context, request=request)

    return JsonResponse({
        "success": True,
        "html_stats": html_stats,
        "html_today_schedule": html_today_schedule,
        "html_upcoming_table": html_upcoming_table,
    })

@login_required(login_url='auth') # Using new 'auth' login URL
def update_booking_status(request, booking_id):
    """
    Allow barbers to update the status of a booking (confirm, cancel, complete).
    """
    if request.method != 'POST':
        return redirect('barber_dashboard')

    try:
        # Ensure the logged-in user is a barber
        barber = request.user.barber_profile
    except Barber.DoesNotExist:
        messages.error(request, "You are not authorized to perform this action.")
        return redirect('auth') # Using new 'auth' login URL

    booking = get_object_or_404(Reservation, id=booking_id)

    # *** SECURITY CHECK ***
    # Ensure the booking belongs to this barber
    if booking.barber != barber:
        messages.error(request, "You can only manage your own appointments.")
        return redirect('barber_dashboard')

    new_status = request.POST.get('status')
    
    # Define allowed transitions
    allowed_statuses = ['confirmed', 'cancelled', 'completed', 'no_show']
    
    if new_status not in allowed_statuses:
        messages.error(request, "Invalid status.")
        return redirect('barber_dashboard')

    # Update status
    booking.status = new_status
    
    # Add a cancellation reason if the barber cancels
    if new_status == 'cancelled':
        booking.cancellation_reason = "Cancelled by barber."
        booking.cancelled_at = timezone.now()
        booking.cancelled_by = request.user
        messages.success(request, f"Booking #{booking.id} has been cancelled.")
        
    elif new_status == 'confirmed':
        messages.success(request, f"Booking #{booking.id} has been confirmed.")

    elif new_status == 'completed':
        messages.success(request, f"Booking #{booking.id} has been marked as completed.")
        
    elif new_status == 'no_show':
        messages.success(request, f"Booking #{booking.id} has been marked as No Show.")

    booking.save()
    
    return redirect('barber_dashboard')

@login_required(login_url='auth') # Using new 'auth' login URL
def barber_schedule_view(request):
    """
    Manages a barber's weekly schedule.
    """
    try:
        barber = request.user.barber_profile
    except Barber.DoesNotExist:
        messages.error(request, "Barber profile not found.")
        return redirect('auth') # Using new 'auth' login URL

    if request.method == "POST":
        action = request.POST.get('action')
        
        try:
            if action == 'create':
                date_str = request.POST.get('date')
                start_time_str = request.POST.get('start_time')
                end_time_str = request.POST.get('end_time')

                if not all([date_str, start_time_str, end_time_str]):
                    messages.error(request, "All fields are required.")
                    return redirect('barber_schedule')

                date = datetime.strptime(date_str, '%Y-%m-%d').date()
                start_time = datetime.strptime(start_time_str, '%H:%M').time()
                end_time = datetime.strptime(end_time_str, '%H:%M').time()

                if start_time >= end_time:
                    messages.error(request, "End time must be after start time.")
                    return redirect('barber_schedule')
                
                if date < timezone.now().date():
                    messages.error(request, "Cannot create schedule for a past date.")
                    return redirect('barber_schedule')

                # Check for overlapping schedules
                overlapping = Schedule.objects.filter(
                    barber=barber,
                    date=date,
                    start_time__lt=end_time,
                    end_time__gt=start_time
                ).exists()

                if overlapping:
                    messages.error(request, f"A schedule already exists that overlaps with {start_time_str} - {end_time_str} on {date_str}.")
                else:
                    Schedule.objects.create(
                        barber=barber,
                        date=date,
                        start_time=start_time,
                        end_time=end_time,
                        is_available=True
                    )
                    messages.success(request, f"Availability added for {date_str}.")
            
            elif action == 'delete':
                schedule_id = request.POST.get('schedule_id')
                schedule_to_delete = get_object_or_404(Schedule, id=schedule_id, barber=barber)
                
                # Check for bookings within this schedule
                bookings_exist = Reservation.objects.filter(
                    barber=barber,
                    appointment_datetime__date=schedule_to_delete.date,
                    appointment_datetime__time__gte=schedule_to_delete.start_time,
                    appointment_datetime__time__lt=schedule_to_delete.end_time,
                    status__in=['pending', 'confirmed']
                ).exists()

                if bookings_exist:
                    messages.error(request, "Cannot delete schedule with active bookings. Please cancel or reschedule bookings first.")
                else:
                    schedule_to_delete.delete()
                    messages.success(request, "Schedule slot deleted.")
        
        except Exception as e:
            messages.error(request, f"An error occurred: {str(e)}")
        
        return redirect('barber_schedule')

    # GET request: Display schedules
    today = timezone.now().date()
    schedules = Schedule.objects.filter(
        barber=barber,
        date__gte=today
    ).order_by('date', 'start_time')

    context = {
        'barber': barber,
        'schedules': schedules,
        'today_str': today.strftime('%Y-%m-%d')
    }
    return render(request, "barber_schedule.html", context)


@login_required(login_url='auth') # Using new 'auth' login URL
def quick_actions_view(request):
    """
    Redirects from quick action buttons on barber_dashboard
    """
    if 'update-schedule' in request.POST:
        return redirect('barber_schedule')
        
    messages.info(request, "Action not yet implemented.")
    return redirect('barber_dashboard')


# -------------------------------
# Logout
# -------------------------------
def logout_view(request):
    logout(request)
    return redirect("auth") # Using new 'auth' login URL


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