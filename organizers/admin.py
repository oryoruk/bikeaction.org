from django.contrib import admin

from organizers.models import OrganizerApplication


class OrganizerApplicationAdmin(admin.ModelAdmin):
    list_display = ("__str__", "submitter")


admin.site.register(OrganizerApplication, OrganizerApplicationAdmin)
