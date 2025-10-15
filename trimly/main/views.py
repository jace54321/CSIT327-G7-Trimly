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



def landing_view(request):
    # If already logged in, optionally jump straight to the correct dashboard.
    if request.user.is_authenticated:
        if hasattr(request.user, "barber"):
            return redirect("barber_dashboard")
        if hasattr(request.user, "customer"):
            return redirect("customer_dashboard")
    return render(request, "landing.html")

def registration_view(request):
    if request.method == "POST":
        # Get form data
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        phone_number = request.POST.get("phone_number", "").strip()
        password = request.POST.get("password", "")
        confirm_password = request.POST.get("confirm-password", "")
        role = request.POST.get("role", "")

        # Validation errors list
        errors = []

        # Required fields validation
        if not all([username, email, first_name, last_name, phone_number, password, confirm_password, role]):
            errors.append("All fields are required.")

        # Phone number validation (same approach as password validation)
        if phone_number:
            try:
                clean_phone = validate_phone_number(phone_number)
            except ValidationError as e:
                errors.extend(e.messages)

        # Password confirmation
        if password != confirm_password:
            errors.append("Passwords do not match.")

        # Email format validation
        if email:
            try:
                EmailValidator(message="Enter a valid email address.")(email)
            except ValidationError:
                errors.append("Enter a valid email address.")

        # Check for existing users
        if User.objects.filter(username=username).exists():
            errors.append("Username already taken.")
        
        if User.objects.filter(email=email).exists():
            errors.append("Email already registered.")

        # Check for existing phone number
        if phone_number:
            try:
                clean_phone = validate_phone_number(phone_number)
                # Check if phone number already exists in Customer or Barber
                if (Customer.objects.filter(phone_number=clean_phone).exists() or 
                    Barber.objects.filter(phone_number=clean_phone).exists()):
                    errors.append("Phone number already registered.")
            except ValidationError:
                pass  # Error already added above

        # Password policy validation (same as your current approach)
        if password:
            try:
                validate_password(password)
            except ValidationError as e:
                errors.extend(e.messages)

        # Display errors if any
        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'registration.html')

        try:
            # Create user with all fields
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name
            )

            # Use the validated clean phone number
            clean_phone = validate_phone_number(phone_number)

            # Create profile based on role
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

def login_view(request):
    if request.method == "POST":
        email_or_username = request.POST.get("email")
        password = request.POST.get("password")

        try:
            user_obj = User.objects.get(email=email_or_username)
            username = user_obj.username
        except User.DoesNotExist:
            username = email_or_username

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            if hasattr(user, "barber"):
                return redirect("barber_dashboard")
            elif hasattr(user, "customer"):
                return redirect("customer_dashboard")
            messages.error(request, "No role assigned to this account.")
            return redirect("login")
        messages.error(request, "Invalid email/username or password.")
        return redirect("login")

    return render(request, "login.html")

def barber_dashboard(request):
    if not request.user.is_authenticated:
        return redirect("login")
    return render(request, "barber_dashboard.html")

def customer_dashboard(request):
    if not request.user.is_authenticated:
        return redirect("login")
    return render(request, "customer_dashboard.html")

def logout_view(request):
    logout(request)
    return redirect("login")


def validate_phone_number(phone_number):
    """
    Custom phone number validator similar to password validation
    """
    if not phone_number:
        raise ValidationError("Phone number is required.")
    
    # Remove any spaces or dashes
    clean_phone = re.sub(r'[\s\-]', '', phone_number)
    
    # Check if it matches the pattern: 09 followed by 9 digits (total 11)
    if not re.match(r'^09[0-9]{9}$', clean_phone):
        raise ValidationError(
            "Phone number must start with 09 and contain exactly 11 digits (e.g., 09123456789)."
        )
    
    return clean_phone