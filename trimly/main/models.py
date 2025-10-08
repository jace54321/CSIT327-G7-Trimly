from django.db import models
from django.contrib.auth.models import User

class Barber(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    shop_name = models.CharField(max_length=100, blank=True, null=True)
    experience_years = models.IntegerField(default=0)

    def __str__(self):
        return f"Barber: {self.user.username}"

class Customer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    preferred_style = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"Customer: {self.user.username}"
