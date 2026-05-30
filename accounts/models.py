from django.db import models


class Customer(models.Model):
	full_name = models.CharField(max_length=150)
	phone_number = models.CharField(max_length=20, unique=True)
	email = models.EmailField(blank=True)
	account_number = models.CharField(max_length=30, unique=True)
	address = models.TextField(blank=True)
	is_active = models.BooleanField(default=True)
	created_at = models.DateTimeField(auto_now_add=True)

	def __str__(self):
		return f"{self.full_name} ({self.account_number})"
