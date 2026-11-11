from django.contrib import admin

from .models import Album, Review, Track

admin.site.register(Album)
admin.site.register(Track)
admin.site.register(Review)
