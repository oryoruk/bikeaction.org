from django.contrib import admin

from projects.models import ProjectApplication


class ProjectApplicationAdmin(admin.ModelAdmin):
    list_display = ("__str__", "submitter")


admin.site.register(ProjectApplication, ProjectApplicationAdmin)
