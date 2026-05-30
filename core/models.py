from django.db import models


class Package(models.Model):
	name = models.CharField(max_length=100, unique=True)
	price = models.DecimalField(max_digits=10, decimal_places=2)
	data_gb = models.PositiveIntegerField(help_text="Included data in GB")
	voice_minutes = models.PositiveIntegerField(help_text="Included voice minutes")
	sms_count = models.PositiveIntegerField(default=0)
	is_active = models.BooleanField(default=True)
	description = models.TextField(blank=True)

	def __str__(self):
		return self.name
