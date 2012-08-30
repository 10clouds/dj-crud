from django.db import models


class Book(models.Model):
    title = models.CharField(max_length=200)
    is_available = models.BooleanField(default=True)
    author_name = models.CharField(max_length=100)
    note = models.TextField()
