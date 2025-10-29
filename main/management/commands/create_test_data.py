# Create a file: main/management/commands/create_test_data.py

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from main.models import Customer, Barber, ServiceType, Reservation
from django.utils import timezone
from datetime import timedelta

class Command(BaseCommand):
    help = 'Create sample test data for development'

    def handle(self, *args, **kwargs):
        # Create test customer
        user1, created = User.objects.get_or_create(
            username='testcustomer',
            defaults={
                'email': 'customer@test.com',
                'first_name': 'John',
                'last_name': 'Doe'
            }
        )
        if created:
            user1.set_password('testpass123')
            user1.save()
            Customer.objects.create(user=user1, phone_number='09123456789')
            self.stdout.write(self.style.SUCCESS('Created test customer'))

        # Create test barber
        user2, created = User.objects.get_or_create(
            username='testbarber',
            defaults={
                'email': 'barber@test.com',
                'first_name': 'Mike',
                'last_name': 'Smith'
            }
        )
        if created:
            user2.set_password('testpass123')
            user2.save()
            Barber.objects.create(
                user=user2,
                phone_number='09987654321',
                experience_years=5,
                bio='Professional barber with 5 years experience'
            )
            self.stdout.write(self.style.SUCCESS('Created test barber'))

        # Create services
        services_data = [
            {'name': 'Classic Haircut', 'price': 35.00, 'duration': 45, 'description': 'Traditional haircut and styling'},
            {'name': 'Beard Trim', 'price': 25.00, 'duration': 30, 'description': 'Professional beard grooming'},
            {'name': 'Haircut + Beard', 'price': 55.00, 'duration': 60, 'description': 'Complete grooming package'},
            {'name': 'Hair Wash & Style', 'price': 30.00, 'duration': 30, 'description': 'Wash and professional styling'},
        ]
        
        for service_data in services_data:
            ServiceType.objects.get_or_create(
                name=service_data['name'],
                defaults={
                    'price': service_data['price'],
                    'duration': service_data['duration'],
                    'description': service_data['description'],
                    'is_active': True
                }
            )
        
        self.stdout.write(self.style.SUCCESS('Created services'))

        # Create sample bookings
        customer = Customer.objects.get(user__username='testcustomer')
        barber = Barber.objects.get(user__username='testbarber')
        service = ServiceType.objects.first()

        # Future booking
        Reservation.objects.get_or_create(
            customer=customer,
            barber=barber,
            service_type=service,
            appointment_datetime=timezone.now() + timedelta(days=7),
            defaults={
                'duration': service.duration,
                'price': service.price,
                'status': 'confirmed',
                'service_description': 'Please use thinning shears'
            }
        )

        # Past booking
        Reservation.objects.get_or_create(
            customer=customer,
            barber=barber,
            service_type=service,
            appointment_datetime=timezone.now() - timedelta(days=15),
            defaults={
                'duration': service.duration,
                'price': service.price,
                'status': 'completed',
                'service_description': 'Great service!'
            }
        )

        self.stdout.write(self.style.SUCCESS('✅ Test data created successfully!'))
        self.stdout.write(self.style.SUCCESS('Login with: testcustomer / testpass123'))
