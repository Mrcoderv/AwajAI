"""FAQ knowledge base models."""

from django.db import models


class FAQ(models.Model):
    """Frequently asked question stored for telecom support."""

    question = models.CharField(max_length=255)
    answer = models.TextField()
    category = models.CharField(max_length=100, blank=True)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["question"]

    def __str__(self):
        return self.question
