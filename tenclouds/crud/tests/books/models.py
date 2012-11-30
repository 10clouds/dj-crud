from mongoengine import Document
from mongoengine import StringField, BooleanField


class Book(Document):
    title = StringField(max_length=200)
    is_available = BooleanField(default=True)
    author_name = StringField(max_length=100)
    note = StringField()
