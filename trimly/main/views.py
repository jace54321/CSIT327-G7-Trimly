import re
from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from .models import Barber, Customer
from django.contrib import messages
from django.db import IntegrityError
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator
from django.http import JsonResponse
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from .models import Barber
import json

# -------------------------------
# View to display the landing page
# Redirects authenticated users to their respective dashboards
# -------------------------------
def landing_view(request):
    # If already logged in, redirect to the appropriate dashboard
    if request.user.is_authenticated:
        if hasattr(request.user, "barber"):
            return redirect("barber_dashboard")
        if hasattr(request.user, "customer"):
            return redirect("customer_dashboard")
    return render(request, "landing.html")


# -------------------------------
# Handles user registration for both barbers and customers
# Includes validation for email, password, and phone number
# -------------------------------
def registration_view(request):
    if request.method == "POST":
        # Retrieve form data
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        phone_number = request.POST.get("phone_number", "").strip()
        password = request.POST.get("password", "")
        confirm_password = request.POST.get("confirm-password", "")
        role = request.POST.get("role", "")

        errors = []  # List to collect all validation errors

        # Check required fields
        if not all([username, email, first_name, last_name, phone_number, password, confirm_password, role]):
            errors.append("All fields are required.")

        # Validate phone number format
        if phone_number:
            try:
                clean_phone = validate_phone_number(phone_number)
            except ValidationError as e:
                errors.extend(e.messages)

        # Confirm passwords match
        if password != confirm_password:
            errors.append("Passwords do not match.")

        # Validate email format
        if email:
            try:
                EmailValidator(message="Enter a valid email address.")(email)
            except ValidationError:
                errors.append("Enter a valid email address.")

        # Check if username or email already exists
        if User.objects.filter(username=username).exists():
            errors.append("Username already taken.")
        if User.objects.filter(email=email).exists():
            errors.append("Email already registered.")

        # Check if phone number already exists in Barber or Customer models
        if phone_number:
            try:
                clean_phone = validate_phone_number(phone_number)
                if (Customer.objects.filter(phone_number=clean_phone).exists() or 
                    Barber.objects.filter(phone_number=clean_phone).exists()):
                    errors.append("Phone number already registered.")
            except ValidationError:
                pass  # Already handled above

        # Validate password strength
        if password:
            try:
                validate_password(password)
            except ValidationError as e:
                errors.extend(e.messages)

        # If there are any validation errors, show them to the user
        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'registration.html')

        # Create user and corresponding role profile
        try:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name
            )

            clean_phone = validate_phone_number(phone_number)

            # Create either a Barber or Customer profile
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
# Handles user login (by username or email)
# Redirects to dashboard based on user role
# -------------------------------
def login_view(request):
    if request.method == "POST":
        email_or_username = request.POST.get("email")
        password = request.POST.get("password")

        # Check if user exists by email or username
        user_exists = False
        try:
            user_obj = User.objects.get(email=email_or_username)
            username = user_obj.username
            user_exists = True
        except User.DoesNotExist:
            # Maybe user entered username instead
            if User.objects.filter(username=email_or_username).exists():
                user_exists = True
                username = email_or_username
            else:
                username = None

        # If user doesn't exist, trigger email tooltip
        if not user_exists:
            return render(request, "login.html", {"user_not_found": True})

        # Authenticate password
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)

            # Redirect based on role
            if hasattr(user, "barber_profile"):
                return redirect("barber_dashboard")
            elif hasattr(user, "customer_profile"):
                return redirect("customer_dashboard")

        # Wrong password case
        return render(request, "login.html", {"wrong_password": True})

    return render(request, "login.html")



# -------------------------------
# Displays the barber dashboard (requires authentication)
# -------------------------------
def barber_dashboard(request):
    if not request.user.is_authenticated:
        return redirect("login")
    return render(request, "barber_dashboard.html")


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
# Displays the customer dashboard (requires authentication)
# -------------------------------
def customer_dashboard(request):
    if not request.user.is_authenticated:
        return redirect("login")
    return render(request, "customer_dashboard.html")


# -------------------------------
# Logs out the current user and redirects to login page
# -------------------------------
def logout_view(request):
    logout(request)
    return redirect("login")


# -------------------------------
# Custom function to validate and sanitize phone numbers
# Ensures Philippine format: must start with 09 and contain 11 digits
# -------------------------------
def validate_phone_number(phone_number):
    """
    Custom phone number validator similar to password validation.
    Returns a cleaned phone number or raises ValidationError if invalid.
    """
    if not phone_number:
        raise ValidationError("Phone number is required.")
    
    # Remove any spaces or dashes for uniformity
    clean_phone = re.sub(r'[\s\-]', '', phone_number)
    
    # Validate pattern: 09 followed by 9 digits (11 total)
    if not re.match(r'^09[0-9]{9}$', clean_phone):
        raise ValidationError(
            "Phone number must start with 09 and contain exactly 11 digits (e.g., 09123456789)."
        )
    
    return clean_phone

