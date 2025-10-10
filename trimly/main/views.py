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
        username = request.POST.get("username") or ""
        email = request.POST.get("email") or ""
        password = request.POST.get("password") or ""
        confirm_password = request.POST.get("confirm-password") or ""
        role = request.POST.get("role") or ""

        if password != confirm_password:
            messages.error(request, "Passwords do not match!")
            return redirect("register")

        # Email format validation
        try:
            EmailValidator(message="Enter a valid email address.")(email)
        except ValidationError as e:
            messages.error(request, str(e))
            return redirect("register")

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already taken!")
            return redirect("register")

        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already registered!")
            return redirect("register")

        # Password policy validation
        try:
            # Optionally pass a user-like object if available for similarity checks
            validate_password(password)
        except ValidationError as e:
            # Join all validator messages for display
            for msg in e.messages:
                messages.error(request, msg)
            return redirect("register")

        try:
            user = User.objects.create_user(username=username, email=email, password=password)
            if role == "barber":
                Barber.objects.create(user=user)
            elif role == "customer":
                Customer.objects.create(user=user)

            messages.success(request, "Registration successful! You can now log in.")
            return redirect("login")
        except IntegrityError:
            messages.error(request, "Registration unsuccessful!")
            return redirect("register")

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
