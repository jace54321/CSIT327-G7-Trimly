from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.html import strip_tags


def send_appointment_confirmation_email(appointment, recipient_email):
    """
    Send appointment confirmation email
    Args:
        appointment: Reservation model instance
        recipient_email: Email address to send to
    """
    subject = f'Appointment Confirmation - {appointment.appointment_datetime.strftime("%B %d, %Y")}'
    
    # Render HTML template
    html_content = render_to_string('emails/appointment_confirmation.html', {
        'appointment': appointment,
        'customer_name': appointment.customer.user.get_full_name() or appointment.customer.user.username,
        'service': appointment.service_type.name,
        'date': appointment.appointment_datetime.date(),
        'time': appointment.appointment_datetime.time(),
        'barber_name': appointment.barber.get_full_name(),
        'price': appointment.price,
        'duration': appointment.duration,
    })
    
    # Create plain text version
    text_content = strip_tags(html_content)
    
    # Create email
    email = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[recipient_email]
    )
    
    # Attach HTML version
    email.attach_alternative(html_content, "text/html")
    
    # Send email
    try:
        email.send()
        return True
    except Exception as e:
        print(f"Error sending confirmation email: {e}")
        return False


def send_appointment_cancellation_email(appointment, recipient_email):
    """
    Send appointment cancellation email
    Args:
        appointment: Reservation model instance
        recipient_email: Email address to send to
    """
    subject = f'Appointment Cancelled - {appointment.appointment_datetime.strftime("%B %d, %Y")}'
    
    # Render HTML template
    html_content = render_to_string('emails/appointment_cancellation.html', {
        'appointment': appointment,
        'customer_name': appointment.customer.user.get_full_name() or appointment.customer.user.username,
        'service': appointment.service_type.name,
        'date': appointment.appointment_datetime.date(),
        'time': appointment.appointment_datetime.time(),
        'barber_name': appointment.barber.get_full_name(),
        'price': appointment.price,
        'duration': appointment.duration,
    })
    
    # Create plain text version
    text_content = strip_tags(html_content)
    
    # Create email
    email = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[recipient_email]
    )
    
    # Attach HTML version
    email.attach_alternative(html_content, "text/html")
    
    # Send email
    try:
        email.send()
        return True
    except Exception as e:
        print(f"Error sending cancellation email: {e}")
        return False
