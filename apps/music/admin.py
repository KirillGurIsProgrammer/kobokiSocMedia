from django.contrib import admin

from .models import Album, CollaborativePlaylist, CollaborativePlaylistInvite, CollaborativePlaylistMember, Review, Tag, Track, TrackTag

admin.site.register(Album)
admin.site.register(Track)
admin.site.register(Review)
admin.site.register(Tag)
admin.site.register(TrackTag)
admin.site.register(CollaborativePlaylist)
admin.site.register(CollaborativePlaylistInvite)
admin.site.register(CollaborativePlaylistMember)
