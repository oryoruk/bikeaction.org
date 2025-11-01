from csvexport.actions import csvexport
from django.contrib import admin

from events.models import EventRSVP, EventSignIn, ScheduledEvent


class ScheduledEventAdmin(admin.ModelAdmin):
    list_display = ["title", "start_datetime", "status"]
    list_filter = ["status"]
    ordering = ["-status", "start_datetime"]
    search_fields = ["title"]


class EventSignInAdmin(admin.ModelAdmin):
    actions = [csvexport]
    list_display = ["get_name", "get_event", "council_district", "newsletter_opt_in"]
    list_filter = ["event__title", "council_district", "zip_code"]
    search_fields = ["first_name", "last_name", "email", "zip_code"]
    ordering = ["-updated_at"]
    readonly_fields = [
        "event",
        "mailjet_contact_id",
        "first_name",
        "last_name",
        "email",
        "zip_code",
        "council_district",
        "newsletter_opt_in",
    ]

    csvexport_selected_fields = [
        "first_name",
        "last_name",
        "email",
        "get_council_district_display",
        "zip_code",
        "event.title",
    ]

    def get_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"

    def get_event(self, obj):
        return obj.event.title


class EventRSVPAdmin(admin.ModelAdmin):
    actions = [csvexport]
    list_display = ["get_name", "get_event"]
    list_filter = ["event__title"]
    search_fields = ["first_name", "last_name", "email"]
    readonly_fields = ["event", "user", "first_name", "last_name", "email"]

    def get_name(self, obj):
        if obj.user is None:
            return f"{obj.first_name} {obj.last_name}"
        return f"{obj.user.first_name} {obj.user.last_name}"

    def get_event(self, obj):
        return obj.event.title


admin.site.register(ScheduledEvent, ScheduledEventAdmin)
admin.site.register(EventSignIn, EventSignInAdmin)
admin.site.register(EventRSVP, EventRSVPAdmin)
