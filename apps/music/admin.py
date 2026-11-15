from django.contrib import admin

from .models import Album, Review, Tag, Track, TrackTag

admin.site.register(Album)
admin.site.register(Track)
admin.site.register(Review)
admin.site.register(Tag)
admin.site.register(TrackTag)
