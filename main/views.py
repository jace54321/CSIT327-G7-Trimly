import re
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from .models import Barber, Customer, Reservation, ServiceType, Schedule, WeeklyAvailability
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
from django.db.models import Q, F, ExpressionWrapper, DateTimeField, DurationField
from django.template.loader import render_to_string
import pytz
# Email sending utility
from .emails import send_appointment_confirmation_email, send_appointment_cancellation_email

#----ADMIN IMPORTS---------
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Q, Sum, Count, Avg
from .models import Reservation, Barber, Customer, ServiceType
from django.core.paginator import Paginator


# Landing page
def landing_view(request):
    """Renders the landing page"""
    services = ServiceType.objects.all()
    context = {"user": request.user, "services": services}
    if request.user.is_authenticated:
        context["is_logged_in"] = True
    return render(request, "landing.html", context)


# Auth page
def auth_view(request):
    """Render the merged auth page"""
    show_register = request.GET.get('mode') == 'register'
    return render(request, "auth.html", {'show_register': show_register})


# Registration
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
            context = {
                "show_register": True,
                "username": username,
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
                "phone_number": phone_number,
                "role": role,
            }
            return render(request, "auth.html", context)

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

            login(request, user)
            messages.success(request, "Registration successful! Welcome!")
            return redirect(redirect_url)

        except IntegrityError:
            messages.error(request, "Registration unsuccessful! Please try again.")
            context = {
                "show_register": True,
                "username": username,
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
                "phone_number": phone_number,
                "role": role,
            }
            return render(request, "auth.html", context)

    return render(request, "auth.html", {"show_register": True})


# Login
def login_view(request):
    if request.method == "POST":
        email_or_username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()
        
        username = email_or_username
        if "@" in email_or_username:
            try:
                user_obj = User.objects.get(email=email_or_username)
                username = user_obj.username
            except User.DoesNotExist:
                pass

        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            if hasattr(user, "barber_profile"):
                return redirect("barber_dashboard")
            elif hasattr(user, "customer_profile"):
                return redirect("customer_dashboard")
            elif user.is_staff or user.is_superuser:
                return redirect("admin_dashboard")
            else:
                return redirect("landing")
        
        messages.error(request, 'Invalid Credentials. Please try again.')
        return redirect('auth')
    
    return redirect('auth')


# Helper: Get available slots (bugFix/time-slots: barber time-slots not reflecting on customer dashboard)
def _get_barber_slots_for_date(barber, date_obj, duration_minutes):
    """
    Get available time slots for a barber on a specific date.
    Uses WeeklyAvailability (rules) + Schedule (exceptions).
    """
    start_time = None
    end_time = None
    slot_duration = 30

    # Check for positive override first
    positive_override = Schedule.objects.filter(
        barber=barber,
        date=date_obj,
        is_available=True
    ).first()
    
    if positive_override:
        start_time = positive_override.start_time
        end_time = positive_override.end_time
        slot_duration = positive_override.slot_duration
    else:
        # Fall back to weekly availability
        day_of_week = date_obj.weekday()
        rule = WeeklyAvailability.objects.filter(
            barber=barber,
            day_of_week=day_of_week,
            is_available=True
        ).first()
        
        if not rule:
            return []
        
        start_time = rule.start_time
        end_time = rule.end_time

    if not start_time or not end_time:
        return []

    # Generate potential slots
    potential_slots = []
    dummy_date = datetime(2000, 1, 1)
    current_dt = datetime.combine(dummy_date, start_time)
    end_dt = datetime.combine(dummy_date, end_time)
    last_possible_start = end_dt - timedelta(minutes=duration_minutes)

    while current_dt <= last_possible_start:
        potential_slots.append(current_dt.time())
        current_dt += timedelta(minutes=slot_duration)

    if not potential_slots:
        return []

    # Get blockers - FIXED timezone handling
    # Use timezone.make_aware instead of localize
    day_start = timezone.make_aware(datetime.combine(date_obj, datetime.min.time()))
    day_end = timezone.make_aware(datetime.combine(date_obj, datetime.max.time()))

    # Booked reservations
    booked = Reservation.objects.filter(
        barber=barber,
        status__in=['pending', 'confirmed', 'in_progress'],
        appointment_datetime__gte=day_start,
        appointment_datetime__lt=day_end
    )
    
    # Negative overrides
    blockers = Schedule.objects.filter(
        barber=barber,
        date=date_obj,
        is_available=False
    )

    # Filter slots
    available_slots = []
    for slot_time in potential_slots:
        slot_start = datetime.combine(dummy_date, slot_time)
        slot_end = slot_start + timedelta(minutes=duration_minutes)
        is_clear = True
        
        # Check reservations
        for res in booked:
            res_start = res.appointment_datetime.astimezone(timezone.get_current_timezone()).time()
            res_end = (res.appointment_datetime + timedelta(minutes=res.duration)).astimezone(timezone.get_current_timezone()).time()
            
            if (slot_time < res_end) and (slot_end.time() > res_start):
                is_clear = False
                break
        
        if not is_clear:
            continue
        
        # Check blockers
        for blocker in blockers:
            if (slot_time < blocker.end_time) and (slot_end.time() > blocker.start_time):
                is_clear = False
                break
        
        if is_clear:
            available_slots.append(slot_time)

    return available_slots



# API: Get slots
@login_required(login_url='auth')
def get_available_slots_api(request, barber_id, date_str):
    """API to fetch available time slots"""
    try:
        barber = get_object_or_404(Barber, id=barber_id)
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        duration = int(request.GET.get('duration', 30))

        # DEBUG: Print to console
        print(f"🔍 DEBUG: Barber ID {barber_id}, Date {date_str}, Duration {duration}")
        print(f"🔍 Day of week: {date_obj.weekday()} (0=Mon, 1=Tue, ...)")
        
        # Check if barber has weekly availability
        day_of_week = date_obj.weekday()
        rule = WeeklyAvailability.objects.filter(
            barber=barber,
            day_of_week=day_of_week
        ).first()
        
        print(f"🔍 WeeklyAvailability rule: {rule}")
        if rule:
            print(f"🔍 Available: {rule.is_available}, Hours: {rule.start_time} - {rule.end_time}")

        slots = _get_barber_slots_for_date(barber, date_obj, duration)
        print(f"🔍 Generated slots: {slots}")
        
        formatted = [t.strftime('%I:%M %p') for t in slots]
        
        return JsonResponse({"success": True, "slots": formatted})

    except ValueError:
        return JsonResponse({"success": False, "error": "Invalid date"}, status=400)
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=500)



# Customer dashboard
@login_required(login_url='auth')
def customer_dashboard(request):
    try:
        customer = request.user.customer_profile
        now = timezone.now()
        
        # FIXED: Include only active upcoming bookings
        upcoming_bookings = Reservation.objects.filter(
            customer=customer,
            appointment_datetime__gte=now,
            status__in=['pending', 'confirmed']  # Removed 'rescheduled'
        ).select_related('barber__user', 'service_type').order_by('appointment_datetime')
        
        # FIXED: Past bookings include old dates OR finished/rejected statuses
        past_bookings = Reservation.objects.filter(
            customer=customer
        ).filter(
            Q(appointment_datetime__lt=now) |  # Past dates
            Q(status__in=['cancelled', 'rejected', 'completed', 'no_show'])  # Or finished statuses
        ).exclude(
            # Don't show future appointments that are still pending/confirmed
            appointment_datetime__gte=now,
            status__in=['pending', 'confirmed']
        ).select_related('barber__user', 'service_type').order_by('-appointment_datetime')[:10]
        
        services = ServiceType.objects.filter(is_active=True).order_by('name')
        barbers = Barber.objects.filter(is_active=True, is_available_for_booking=True).select_related('user')
        
        selected_booking = None
        reschedule_booking = None
        rating_booking = None
        
        view_id = request.GET.get('view')
        if view_id:
            try:
                selected_booking = Reservation.objects.select_related(
                    'barber__user', 'service_type'
                ).get(id=view_id, customer=customer)
            except Reservation.DoesNotExist:
                messages.error(request, "Booking not found.")
        
        reschedule_id = request.GET.get('reschedule')
        if reschedule_id:
            try:
                reschedule_booking = Reservation.objects.select_related(
                    'barber__user', 'service_type'
                ).get(id=reschedule_id, customer=customer)
                
                if not reschedule_booking.can_be_cancelled():
                    messages.error(request, "Cannot reschedule within 24 hours.")
                    return redirect('customer_dashboard')
            except Reservation.DoesNotExist:
                messages.error(request, "Booking not found.")
                return redirect('customer_dashboard')
        
        rate_id = request.GET.get('rate')
        if rate_id:
            try:
                rating_booking = Reservation.objects.select_related(
                    'barber__user', 'service_type'
                ).get(id=rate_id, customer=customer)
                
                if rating_booking.status != 'completed':
                    messages.error(request, "Can only rate completed appointments.")
                    rating_booking = None
                elif rating_booking.rating is not None:
                    messages.error(request, "Already rated.")
                    rating_booking = None
            except Reservation.DoesNotExist:
                messages.error(request, "Booking not found.")
                return redirect('customer_dashboard')
        
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
            'rating_booking': rating_booking,
            'show_booking_form': show_booking_form,
        }
        
        return render(request, "customer_dashboard.html", context)
    except Customer.DoesNotExist:
        messages.error(request, "Customer profile not found.")
        return redirect("auth")


# Create booking (WITH EMAIL CONFIRMATION INTEGRATED)
@login_required(login_url='auth') 
def create_booking_view(request):
    """Create new booking"""
    if request.method != 'POST':
        return redirect('customer_dashboard')
    
    book_form_url = f"{reverse('customer_dashboard')}?action=book"
    
    try:
        customer = request.user.customer_profile
        
        service_id = request.POST.get('service_id')
        barber_id = request.POST.get('barber_id')
        appointment_date_str = request.POST.get('appointment_date')
        appointment_time_str = request.POST.get('appointment_time')
        notes = request.POST.get('notes', '').strip()
        
        if not all([service_id, barber_id, appointment_date_str, appointment_time_str]):
            messages.error(request, 'All fields required.')
            return redirect(book_form_url)
        
        service = get_object_or_404(ServiceType, id=service_id, is_active=True)
        barber = get_object_or_404(Barber, id=barber_id, is_active=True)
        
        try:
            appointment_date = datetime.strptime(appointment_date_str, '%Y-%m-%d').date()
            appointment_time = datetime.strptime(appointment_time_str, '%H:%M').time()
            appointment_datetime = timezone.make_aware(datetime.combine(appointment_date, appointment_time))
        except ValueError:
            messages.error(request, 'Invalid date/time format.')
            return redirect(book_form_url)

        if appointment_datetime < timezone.now():
            messages.error(request, 'Cannot book in the past.')
            return redirect(book_form_url)
        
        # Validate slot
        available_slots = _get_barber_slots_for_date(barber, appointment_date, service.duration)
        
        if appointment_time not in available_slots:
            messages.error(request, 'Time slot not available.')
            return redirect(book_form_url)
        
        # Create the reservation
        reservation = Reservation.objects.create(
            customer=customer,
            barber=barber,
            service_type=service,
            appointment_datetime=appointment_datetime,
            duration=service.duration,
            price=service.price,
            service_description=notes,
            status='pending'
        )
        
        # ✅ SEND CONFIRMATION EMAIL
        try:
            email_sent = send_appointment_confirmation_email(
                appointment=reservation,
                recipient_email=request.user.email
            )
            
            if email_sent:
                messages.success(request, 
                    f'Booking confirmed! Confirmation email sent to {request.user.email}. '
                    f'{service.name} with {barber.get_full_name()} '
                    f'on {appointment_datetime.strftime("%B %d, %Y at %I:%M %p")}.')
            else:
                messages.success(request, 
                    f'Booking confirmed! {service.name} with {barber.get_full_name()} '
                    f'on {appointment_datetime.strftime("%B %d, %Y at %I:%M %p")}. '
                    f'(Email notification failed)')
        except Exception as e:
            print(f"Email error: {e}")
            messages.success(request, 
                f'Booking confirmed! {service.name} with {barber.get_full_name()} '
                f'on {appointment_datetime.strftime("%B %d, %Y at %I:%M %p")}.')
        
        return redirect('customer_dashboard')
    
    except Customer.DoesNotExist:
        messages.error(request, 'Customer profile not found.')
        return redirect('auth')
    except Exception as e:
        messages.error(request, f'Error: {str(e)}')
        return redirect(book_form_url)


# Toggle availability
@login_required
@csrf_exempt
def toggle_availability(request):
    """Toggle barber availability"""
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


# Cancel booking (WITH EMAIL CANCELLATION INTEGRATED)
@login_required(login_url='auth')
def cancel_booking_view(request, booking_id):
    if request.method != 'POST':
        return redirect('customer_dashboard')
    
    try:
        customer = request.user.customer_profile
        booking = get_object_or_404(Reservation, id=booking_id, customer=customer)
        
        if not booking.can_be_cancelled():
            messages.error(request, 'Cannot cancel within 24 hours.')
            return redirect('customer_dashboard')
        
        # Store booking details before cancellation
        service_name = booking.service_type.name
        appointment_datetime = booking.appointment_datetime
        
        # Cancel the booking
        success = booking.cancel(cancelled_by=request.user, reason='Customer cancelled')
        
        if success:
            # ✅ SEND CANCELLATION EMAIL
            try:
                email_sent = send_appointment_cancellation_email(
                    appointment=booking,
                    recipient_email=request.user.email
                )
                
                if email_sent:
                    messages.success(request, 
                        f'Booking cancelled for {service_name}. '
                        f'Cancellation confirmation sent to {request.user.email}.')
                else:
                    messages.success(request, 
                        f'Booking cancelled for {service_name}. '
                        f'(Email notification failed)')
            except Exception as e:
                print(f"Cancellation email error: {e}")
                messages.success(request, f'Booking cancelled for {service_name}.')
        else:
            messages.error(request, 'Unable to cancel.')
    
    except Customer.DoesNotExist:
        messages.error(request, 'Customer profile not found.')
    except Exception as e:
        messages.error(request, f'Error: {str(e)}')
    
    return redirect('customer_dashboard')


# Reschedule booking
@login_required(login_url='auth')
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
        
        if not booking.can_be_cancelled():
            messages.error(request, 'Cannot reschedule within 24 hours.')
            return redirect('customer_dashboard')
        
        new_date_str = request.POST.get('new_date')
        new_time_str = request.POST.get('new_time')
        
        if not new_date_str or not new_time_str:
            messages.error(request, 'Date and time required.')
            return redirect(f"{reverse('customer_dashboard')}?reschedule={booking_id}")
        
        try:
            new_date = datetime.strptime(new_date_str, '%Y-%m-%d').date()
            new_time = datetime.strptime(new_time_str, '%H:%M').time()
            new_datetime = timezone.make_aware(datetime.combine(new_date, new_time))
            
            if new_datetime < timezone.now():
                messages.error(request, 'Cannot reschedule to past.')
                return redirect(f"{reverse('customer_dashboard')}?reschedule={booking_id}")
            
            # Validate slot
            available_slots = _get_barber_slots_for_date(booking.barber, new_date, booking.duration)
            if new_time not in available_slots:
                messages.error(request, 'Time slot not available.')
                return redirect(f"{reverse('customer_dashboard')}?reschedule={booking_id}")
            
            old_datetime = booking.appointment_datetime
            booking.appointment_datetime = new_datetime
            # FIXED: Keep status as confirmed/pending instead of 'rescheduled'
            # Status stays the same - no change needed
            booking.save()
            
            messages.success(request,
                f'Rescheduled from {old_datetime.strftime("%B %d at %I:%M %p")} '
                f'to {new_datetime.strftime("%B %d at %I:%M %p")}.')
        except ValueError:
            messages.error(request, 'Invalid date/time.')
            return redirect(f"{reverse('customer_dashboard')}?reschedule={booking_id}")
    except Customer.DoesNotExist:
        messages.error(request, 'Customer profile not found.')
    except Exception as e:
        messages.error(request, f'Error: {str(e)}')
    
    return redirect('customer_dashboard')

# Submit rating
@login_required(login_url='auth')
def submit_rating_view(request, booking_id):
    """Submit rating"""
    if request.method != 'POST':
        return redirect('customer_dashboard')

    try:
        customer = request.user.customer_profile
        booking = get_object_or_404(
            Reservation.objects.select_related('barber'),
            id=booking_id,
            customer=customer
        )

        if booking.status != 'completed':
            messages.error(request, "Can only rate completed appointments.")
            return redirect('customer_dashboard')
        
        if booking.rating is not None:
            messages.error(request, "Already rated.")
            return redirect('customer_dashboard')

        rating = request.POST.get('rating')
        feedback = request.POST.get('feedback', '').strip()

        if not rating:
            messages.error(request, "Select rating.")
            return redirect(f"{reverse('customer_dashboard')}?rate={booking_id}")

        booking.rating = int(rating)
        booking.feedback = feedback
        booking.save()

        messages.success(request, "Rating submitted!")
        return redirect('customer_dashboard')

    except Customer.DoesNotExist:
        messages.error(request, 'Customer profile not found.')
    except Exception as e:
        messages.error(request, f'Error: {str(e)}')
    
    return redirect('customer_dashboard')


def _get_barber_dashboard_data(barber):
    """Get barber dashboard data"""
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    
    all_reservations = Reservation.objects.filter(
        barber=barber
    ).select_related('customer__user', 'service_type').order_by('appointment_datetime')
    
    # Today's appointments
    today_appointments = all_reservations.filter(
        appointment_datetime__gte=today_start,
        appointment_datetime__lt=today_end,
        status__in=['pending', 'confirmed', 'in_progress', 'completed', 'no_show']
    ).order_by('appointment_datetime')
    
    # FIXED: Upcoming appointments - only show pending and confirmed
    upcoming_appointments = all_reservations.filter(
        appointment_datetime__gte=today_end,
        status__in=['pending', 'confirmed']  # Removed 'rescheduled'
    ).order_by('appointment_datetime')
    
    # Stats
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
    
    stats_completed_count = all_reservations.filter(status='completed').count()
    
    return {
        'barber': barber,
        'today_appointments': today_appointments,
        'upcoming_appointments': upcoming_appointments,
        'stats_today_count': stats_today_count,
        'stats_week_count': stats_week_count,
        'stats_completed_count': stats_completed_count,
    }



# Barber dashboard
@login_required(login_url='auth')
def barber_dashboard(request):
    try:
        barber = get_object_or_404(Barber, user=request.user)
    except Barber.DoesNotExist:
        messages.error(request, "Barber profile not found.")
        return redirect("auth")

    context = _get_barber_dashboard_data(barber)
    return render(request, "barber_dashboard.html", context)


# Barber dashboard API
@login_required
def barber_dashboard_api(request):
    """API for dashboard updates"""
    try:
        barber = get_object_or_404(Barber, user=request.user)
    except Barber.DoesNotExist:
        return JsonResponse({"success": False, "error": "Not found"}, status=404)

    context = _get_barber_dashboard_data(barber)
    
    html_stats = render_to_string("_barber_stats.html", context, request=request)
    html_today_schedule = render_to_string("_barber_today_schedule.html", context, request=request)
    html_upcoming_table = render_to_string("_barber_upcoming_table.html", context, request=request)

    return JsonResponse({
        "success": True,
        "html_stats": html_stats,
        "html_today_schedule": html_today_schedule,
        "html_upcoming_table": html_upcoming_table,
    })


# Update booking status
@login_required(login_url='auth')
def update_booking_status(request, booking_id):
    """Update booking status"""
    if request.method != 'POST':
        return redirect('barber_dashboard')

    try:
        barber = request.user.barber_profile
    except Barber.DoesNotExist:
        messages.error(request, "Not authorized.")
        return redirect('auth')

    booking = get_object_or_404(Reservation, id=booking_id)

    if booking.barber != barber:
        messages.error(request, "Can only manage own appointments.")
        return redirect('barber_dashboard')

    new_status = request.POST.get('status')
    allowed = ['confirmed', 'cancelled', 'completed', 'no_show']
    
    if new_status not in allowed:
        messages.error(request, "Invalid status.")
        return redirect('barber_dashboard')

    booking.status = new_status
    
    if new_status == 'cancelled':
        booking.cancellation_reason = "Cancelled by barber."
        booking.cancelled_at = timezone.now()
        booking.cancelled_by = request.user
        messages.success(request, f"Booking #{booking.id} cancelled.")
    elif new_status == 'confirmed':
        messages.success(request, f"Booking #{booking.id} confirmed.")
    elif new_status == 'completed':
        messages.success(request, f"Booking #{booking.id} completed.")
    elif new_status == 'no_show':
        messages.success(request, f"Booking #{booking.id} marked no-show.")

    booking.save()
    return redirect('barber_dashboard')

# reject view for rejecting bookings
@login_required(login_url='auth')
def barber_reject_booking(request, booking_id):
    """Barber rejects/cancels an appointment"""
    if request.method != 'POST':
        return redirect('barber_dashboard')
    
    try:
        barber = request.user.barber_profile
        booking = get_object_or_404(Reservation, id=booking_id)
        
        if booking.barber != barber:
            messages.error(request, 'Can only manage own appointments.')
            return redirect('barber_dashboard')
        
        reason = request.POST.get('reason', 'Rejected by barber')
        
        booking.status = 'rejected'
        booking.cancellation_reason = reason
        booking.cancelled_at = timezone.now()
        booking.cancelled_by = request.user
        booking.save()
        
        messages.success(request, f'Booking #{booking.id} has been rejected.')
        
    except Barber.DoesNotExist:
        messages.error(request, 'Not authorized.')
    except Exception as e:
        messages.error(request, f'Error: {str(e)}')
    
    return redirect('barber_dashboard')

# Barber schedule
@login_required(login_url='auth')
def barber_schedule_view(request):
    """Manage date overrides"""
    try:
        barber = request.user.barber_profile
    except Barber.DoesNotExist:
        messages.error(request, "Barber profile not found.")
        return redirect('auth')

    if request.method == "POST":
        action = request.POST.get('action')
        
        try:
            if action == 'create':
                date_str = request.POST.get('date')
                start_time_str = request.POST.get('start_time')
                end_time_str = request.POST.get('end_time')
                override_type = request.POST.get('override_type')
                is_available = (override_type == 'available')

                if not all([date_str, start_time_str, end_time_str, override_type]):
                    messages.error(request, "All fields required.")
                    return redirect('barber_schedule')

                date = datetime.strptime(date_str, '%Y-%m-%d').date()
                start_time = datetime.strptime(start_time_str, '%H:%M').time()
                end_time = datetime.strptime(end_time_str, '%H:%M').time()

                if start_time >= end_time:
                    messages.error(request, "End must be after start.")
                    return redirect('barber_schedule')
                
                if date < timezone.now().date():
                    messages.error(request, "Cannot create for past date.")
                    return redirect('barber_schedule')

                overlapping = Schedule.objects.filter(
                    barber=barber,
                    date=date,
                    start_time__lt=end_time,
                    end_time__gt=start_time
                ).exists()

                if overlapping:
                    messages.error(request, "Override already exists.")
                else:
                    Schedule.objects.create(
                        barber=barber,
                        date=date,
                        start_time=start_time,
                        end_time=end_time,
                        is_available=is_available
                    )
                    
                    if is_available:
                        messages.success(request, f"Availability added for {date_str}.")
                    else:
                        messages.success(request, f"Time blocked on {date_str}.")
            
            elif action == 'delete':
                schedule_id = request.POST.get('schedule_id')
                schedule = get_object_or_404(Schedule, id=schedule_id, barber=barber)
                
                if schedule.is_available:
                    bookings = Reservation.objects.filter(
                        barber=barber,
                        appointment_datetime__date=schedule.date,
                        appointment_datetime__time__gte=schedule.start_time,
                        appointment_datetime__time__lt=schedule.end_time,
                        status__in=['pending', 'confirmed']
                    ).exists()

                    if bookings:
                        messages.error(request, "Cannot delete - has bookings.")
                        return redirect('barber_schedule')

                schedule.delete()
                messages.success(request, "Override deleted.")
        
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
        
        return redirect('barber_schedule')

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


# Weekly availability
@login_required(login_url='auth')
def manage_weekly_availability(request):
    """Manage weekly template"""
    try:
        barber = request.user.barber_profile
    except Barber.DoesNotExist:
        messages.error(request, "Barber profile not found.")
        return redirect('auth')

    if request.method == "POST":
        try:
            for i in range(7):
                avail = get_object_or_404(WeeklyAvailability, barber=barber, day_of_week=i)
                
                is_available = request.POST.get(f'is_available_{i}') == 'on'
                avail.is_available = is_available
                
                if is_available:
                    start_time_str = request.POST.get(f'start_time_{i}')
                    end_time_str = request.POST.get(f'end_time_{i}')
                    
                    if not start_time_str or not end_time_str:
                        raise ValidationError(f"Missing times for {avail.get_day_of_week_display()}.")

                    start_time = datetime.strptime(start_time_str, '%H:%M').time()
                    end_time = datetime.strptime(end_time_str, '%H:%M').time()

                    if start_time >= end_time:
                         raise ValidationError(f"End must be after start for {avail.get_day_of_week_display()}.")

                    avail.start_time = start_time
                    avail.end_time = end_time
                else:
                    avail.start_time = None
                    avail.end_time = None
                
                avail.save()
            
            messages.success(request, "Weekly availability updated.")
        
        except ValidationError as e:
            messages.error(request, e.message)
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
        
        return redirect('manage_weekly_availability')

    days_data = []
    for i in range(7):
        obj, created = WeeklyAvailability.objects.get_or_create(
            barber=barber, 
            day_of_week=i,
            defaults={'is_available': False, 'start_time': None, 'end_time': None}
        )
        days_data.append(obj)

    context = {
        'barber': barber,
        'days': days_data
    }
    return render(request, "manage_weekly_availability.html", context)


# Quick actions
@login_required(login_url='auth')
def quick_actions_view(request):
    """Quick actions redirect"""
    if 'update-schedule' in request.POST:
        return redirect('barber_schedule')
    messages.info(request, "Not implemented.")
    return redirect('barber_dashboard')


# Logout
def logout_view(request):
    logout(request)
    return redirect("auth")


# Phone validator
def validate_phone_number(phone_number):
    if not phone_number:
        raise ValidationError("Phone number required.")
    
    clean_phone = re.sub(r'[\s\-]', '', phone_number)
    
    if not re.match(r'^09[0-9]{9}$', clean_phone):
        raise ValidationError("Phone must be 09XXXXXXXXX format.")
    
    return clean_phone





#-------------------------
#--ADMIN FUNCTIONALITIES--
#-------------------------

@login_required(login_url='auth')
@staff_member_required(login_url='landing')
def admin_dashboard_view(request):
    
    # --- Get Main Stats ---
    total_bookings = Reservation.objects.count()
    total_customers = Customer.objects.count()
    total_barbers = Barber.objects.count()
    total_revenue_data = Reservation.objects.filter(status='completed').aggregate(
        total_revenue=Sum('price')
    )
    total_revenue = total_revenue_data.get('total_revenue') or 0.00
    
    # --- Get Barbers (for management & filters) ---
    all_barbers = Barber.objects.all().select_related('user').order_by('user__first_name')
    all_services = ServiceType.objects.all().order_by('name')

    # ==================================================
    # BOOKING FILTERING & PAGINATION
    # ==================================================
    bookings_list = Reservation.objects.all().select_related(
        'customer__user', 'barber__user', 'service_type'
    ).order_by('-appointment_datetime')

    filter_barber = request.GET.get('barber', '')
    filter_status = request.GET.get('status', '')
    filter_start_date = request.GET.get('start_date', '')
    filter_end_date = request.GET.get('end_date', '')

   # Apply filters
    if filter_barber:
        bookings_list = bookings_list.filter(barber_id=filter_barber)
    if filter_status:
        bookings_list = bookings_list.filter(status=filter_status)
    
    
    # Only try to convert dates if the strings are not empty
    try:
        if filter_start_date:
            start_date_obj = datetime.strptime(filter_start_date, '%Y-%m-%d').date()
            bookings_list = bookings_list.filter(appointment_datetime__gte=start_date_obj)
            
        if filter_end_date:
            end_date_obj = datetime.strptime(filter_end_date, '%Y-%m-%d').date()
            end_date_inclusive = end_date_obj + timedelta(days=1) 
            bookings_list = bookings_list.filter(appointment_datetime__lt=end_date_inclusive)
    except ValueError:
        messages.error(request, "Invalid date format. Please use YYYY-MM-DD.")
    

    paginator = Paginator(bookings_list, 10) # 10 bookings per page
    page_number = request.GET.get('page') # Uses 'page' query param
    bookings_page = paginator.get_page(page_number)
    
    status_choices = Reservation.STATUS_CHOICES
    
    # ==================================================
    # CUSTOMER FILTERING & PAGINATION
    # ==================================================
    customer_list = Customer.objects.all().select_related('user').order_by('user__first_name')
    
    filter_customer_name = request.GET.get('customer_name', '')
    
    if filter_customer_name:
        # Filter by first name, last name, or username
        customer_list = customer_list.filter(
            Q(user__first_name__icontains=filter_customer_name) |
            Q(user__last_name__icontains=filter_customer_name) |
            Q(user__username__icontains=filter_customer_name)
        )

    customer_paginator = Paginator(customer_list, 10) # 10 customers per page
    customer_page_number = request.GET.get('c_page') # Uses 'c_page' query param
    customers_page = customer_paginator.get_page(customer_page_number)
    
    # Pass current filter values back to the template
    filter_params = {
        'barber': filter_barber,
        'status': filter_status,
        'start_date': filter_start_date,
        'end_date': filter_end_date,
        'customer_name': filter_customer_name, # Added new filter
    }

    context = {
        'total_bookings': total_bookings,
        'total_customers': total_customers,
        'total_barbers': total_barbers,
        'total_revenue': total_revenue,
        
        'bookings_page': bookings_page,
        'all_barbers': all_barbers,
        'status_choices': status_choices,
        
        'customers_page': customers_page,

        'all_services': all_services,

        'filter_params': filter_params,
    }
    return render(request, "admin_dashboard.html", context)

# -------------------------------
# ADMIN DASHBOARD - CRUD VIEWS
# -------------------------------

# -------------------------------
# CUSTOMER CRUD VIEW
# -------------------------------

@staff_member_required(login_url='landing')
def admin_create_customer_view(request):
    if request.method == "POST":
        username = request.POST.get("username").strip()
        email = request.POST.get("email").strip()
        first_name = request.POST.get("first_name").strip()
        last_name = request.POST.get("last_name").strip()
        phone_number = request.POST.get("phone_number").strip()
        password = request.POST.get("password")

        try:
            # Validations
            if not all([username, email, first_name, last_name, phone_number, password]):
                messages.error(request, "All fields are required.")
                return redirect('admin_dashboard')

            if User.objects.filter(username=username).exists():
                messages.error(request, "Username already taken.")
                return redirect('admin_dashboard')
            
            if User.objects.filter(email=email).exists():
                messages.error(request, "Email already in use.")
                return redirect('admin_dashboard')

            clean_phone = validate_phone_number(phone_number)
            if Customer.objects.filter(phone_number=clean_phone).exists():
                messages.error(request, "Phone number already in use.")
                return redirect('admin_dashboard')

            validate_password(password) # Check password strength

            # Create User
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name
            )
            # Create Customer Profile
            Customer.objects.create(user=user, phone_number=clean_phone)
            messages.success(request, f"Customer '{username}' created successfully.")

        except ValidationError as e:
            messages.error(request, f"Validation Error: {'. '.join(e.messages)}")
        except Exception as e:
            messages.error(request, f"An error occurred: {str(e)}")
    
    return redirect('admin_dashboard')


@staff_member_required(login_url='landing')
def admin_edit_customer_view(request, user_id):
    if request.method == "POST":
        try:
            user = get_object_or_404(User, id=user_id)
            customer = get_object_or_404(Customer, user=user)
            
            email = request.POST.get("email").strip()
            first_name = request.POST.get("first_name").strip()
            last_name = request.POST.get("last_name").strip()
            phone_number = request.POST.get("phone_number").strip()
            
            # Validation
            if not all([email, first_name, last_name, phone_number]):
                messages.error(request, "All fields are required.")
                return redirect('admin_dashboard')

            # Check if email is being changed to one that already exists
            if email != user.email and User.objects.filter(email=email).exists():
                messages.error(request, "Email already in use.")
                return redirect('admin_dashboard')
            
            clean_phone = validate_phone_number(phone_number)
            # Check if phone is being changed to one that already exists
            if clean_phone != customer.phone_number and Customer.objects.filter(phone_number=clean_phone).exists():
                messages.error(request, "Phone number already in use.")
                return redirect('admin_dashboard')

            # Update User
            user.email = email
            user.first_name = first_name
            user.last_name = last_name
            user.save()
            
            # Update Customer Profile
            customer.phone_number = clean_phone
            customer.save()
            
            messages.success(request, f"Customer '{user.username}' updated successfully.")

        except ValidationError as e:
            messages.error(request, f"Validation Error: {'. '.join(e.messages)}")
        except Exception as e:
            messages.error(request, f"An error occurred: {str(e)}")
            
    return redirect('admin_dashboard')


@staff_member_required(login_url='landing')
def admin_delete_customer_view(request, user_id):
    if request.method == "POST":
        try:
            user = get_object_or_404(User, id=user_id)
            username = user.username
            
            # Deleting the User will cascade and delete the Customer profile
            user.delete()
            messages.success(request, f"Customer '{username}' has been deleted.")
        
        except Exception as e:
            messages.error(request, f"An error occurred: {str(e)}")
            
    return redirect('admin_dashboard')



# -------------------------------
# BARBER CRUD VIEW
# -------------------------------

@staff_member_required(login_url='landing')
def admin_create_barber_view(request):
    if request.method == "POST":
        username = request.POST.get("username").strip()
        email = request.POST.get("email").strip()
        first_name = request.POST.get("first_name").strip()
        last_name = request.POST.get("last_name").strip()
        phone_number = request.POST.get("phone_number").strip()
        password = request.POST.get("password")

        try:
            # Validations
            if not all([username, email, first_name, last_name, phone_number, password]):
                messages.error(request, "All fields are required.")
                return redirect('admin_dashboard')

            if User.objects.filter(username=username).exists():
                messages.error(request, "Username already taken.")
                return redirect('admin_dashboard')
            
            if User.objects.filter(email=email).exists():
                messages.error(request, "Email already in use.")
                return redirect('admin_dashboard')

            clean_phone = validate_phone_number(phone_number)
            if Barber.objects.filter(phone_number=clean_phone).exists():
                messages.error(request, "Phone number already in use.")
                return redirect('admin_dashboard')

            validate_password(password) # Check password strength

            # Create User
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name
            )
            # Create Barber Profile
            Barber.objects.create(user=user, phone_number=clean_phone)
            messages.success(request, f"Barber '{username}' created successfully.")

        except ValidationError as e:
            messages.error(request, f"Validation Error: {'. '.join(e.messages)}")
        except Exception as e:
            messages.error(request, f"An error occurred: {str(e)}")
    
    return redirect('admin_dashboard')


@staff_member_required(login_url='landing')
def admin_edit_barber_view(request, user_id):
    if request.method == "POST":
        try:
            user = get_object_or_404(User, id=user_id)
            barber = get_object_or_404(Barber, user=user)
            
            email = request.POST.get("email").strip()
            first_name = request.POST.get("first_name").strip()
            last_name = request.POST.get("last_name").strip()
            phone_number = request.POST.get("phone_number").strip()
            
            # Validation
            if not all([email, first_name, last_name, phone_number]):
                messages.error(request, "All fields are required.")
                return redirect('admin_dashboard')

            if email != user.email and User.objects.filter(email=email).exists():
                messages.error(request, "Email already in use.")
                return redirect('admin_dashboard')
            
            clean_phone = validate_phone_number(phone_number)
            if clean_phone != barber.phone_number and Barber.objects.filter(phone_number=clean_phone).exists():
                messages.error(request, "Phone number already in use.")
                return redirect('admin_dashboard')

            # Update User
            user.email = email
            user.first_name = first_name
            user.last_name = last_name
            user.save()
            
            # Update Barber Profile
            barber.phone_number = clean_phone
            barber.save()
            
            messages.success(request, f"Barber '{user.username}' updated successfully.")

        except ValidationError as e:
            messages.error(request, f"Validation Error: {'. '.join(e.messages)}")
        except Exception as e:
            messages.error(request, f"An error occurred: {str(e)}")
            
    return redirect('admin_dashboard')


@staff_member_required(login_url='landing')
def admin_delete_barber_view(request, user_id):
    if request.method == "POST":
        try:
            user = get_object_or_404(User, id=user_id)
            username = user.username
            
            # Deleting the User will cascade and delete the Barber profile
            user.delete()
            messages.success(request, f"Barber '{username}' has been deleted.")
        
        except Exception as e:
            messages.error(request, f"An error occurred: {str(e)}")
            
    return redirect('admin_dashboard')


# -------------------------------
# SERVICE CRUD VIEW
# -------------------------------

@staff_member_required(login_url='landing')
def admin_create_service_view(request):
    if request.method == "POST":
        try:
            name = request.POST.get("name").strip()
            price = request.POST.get("price")
            duration = request.POST.get("duration")
            description = request.POST.get("description", "").strip()

            if not all([name, price, duration]):
                messages.error(request, "Name, Price, and Duration are required.")
                return redirect('admin_dashboard')

            ServiceType.objects.create(
                name=name,
                price=price,
                duration=duration,
                description=description
            )
            messages.success(request, f"Service '{name}' created successfully.")

        except Exception as e:
            messages.error(request, f"An error occurred: {str(e)}")
    
    return redirect('admin_dashboard')


@staff_member_required(login_url='landing')
def admin_edit_service_view(request, service_id):
    if request.method == "POST":
        try:
            service = get_object_or_404(ServiceType, id=service_id)
            
            name = request.POST.get("name").strip()
            price = request.POST.get("price")
            duration = request.POST.get("duration")
            description = request.POST.get("description", "").strip()

            if not all([name, price, duration]):
                messages.error(request, "Name, Price, and Duration are required.")
                return redirect('admin_dashboard')

            service.name = name
            service.price = price
            service.duration = duration
            service.description = description
            service.save()
            
            messages.success(request, f"Service '{name}' updated successfully.")

        except Exception as e:
            messages.error(request, f"An error occurred: {str(e)}")
            
    return redirect('admin_dashboard')


@staff_member_required(login_url='landing')
def admin_delete_service_view(request, service_id):
    if request.method == "POST":
        try:
            service = get_object_or_404(ServiceType, id=service_id)
            name = service.name
            
            # Check if service is tied to any bookings
            if service.reservations.exists():
                messages.error(request, f"Cannot delete '{name}' as it is tied to existing bookings. You can disable it by editing it instead.")
                return redirect('admin_dashboard')
                
            service.delete()
            messages.success(request, f"Service '{name}' has been deleted.")
        
        except Exception as e:
            messages.error(request, f"An error occurred: {str(e)}")
            
    return redirect('admin_dashboard')

@staff_member_required(login_url='landing')
def admin_update_booking_status(request, booking_id):
    """
    Allow Admin to update the status of any booking.
    """
    if request.method != 'POST':
        return redirect('admin_dashboard')

    try:
        booking = get_object_or_404(Reservation, id=booking_id)
        new_status = request.POST.get('status')

        # Define all allowed transitions
        allowed_statuses = [choice[0] for choice in Reservation.STATUS_CHOICES]
        
        if new_status not in allowed_statuses:
            messages.error(request, "Invalid status.")
            return redirect('admin_dashboard')

        # Update status
        booking.status = new_status
        
        if new_status == 'cancelled':
            booking.cancellation_reason = "Cancelled by Admin."
            booking.cancelled_at = timezone.now()
            booking.cancelled_by = request.user
            messages.success(request, f"Booking #{booking.id} has been cancelled.")
            
        elif new_status == 'confirmed':
            messages.success(request, f"Booking #{booking.id} has been confirmed.")

        elif new_status == 'completed':
            messages.success(request, f"Booking #{booking.id} has been marked as completed.")
        
        else:
            messages.success(request, f"Booking #{booking.id} status updated to '{new_status}'.")

        booking.save()
    
    except Exception as e:
        messages.error(request, f"An error occurred: {str(e)}")
    
    return redirect('admin_dashboard')

@staff_member_required(login_url='landing')
def admin_reset_password_view(request, user_id):
    """
    Allow Admin to reset a user's password.
    """
    if request.method != 'POST':
        return redirect('admin_dashboard')

    try:
        user = get_object_or_404(User, id=user_id)
        new_password = request.POST.get("new_password")
        confirm_password = request.POST.get("confirm_password")

        if not all([new_password, confirm_password]):
            messages.error(request, "Both password fields are required.")
            return redirect('admin_dashboard')

        if new_password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return redirect('admin_dashboard')
        
        # Use Django's built-in password validator
        validate_password(new_password, user=user)
        
        # Set and hash the new password
        user.set_password(new_password)
        user.save()
        
        messages.success(request, f"Password for '{user.username}' has been reset successfully.")

    except ValidationError as e:
        # e.messages is a list, so join them
        messages.error(request, f"Validation Error: {'. '.join(e.messages)}")
    except Exception as e:
        messages.error(request, f"An error occurred: {str(e)}")
            
    return redirect('admin_dashboard')
