from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html

from elections.models import Election, Nomination, Nominee


class NominationInline(admin.TabularInline):
    model = Nomination
    extra = 0
    fields = ("nominator", "draft", "acceptance_status", "created_at")
    readonly_fields = ("nominator", "created_at")
    can_delete = False
    show_change_link = True


class ElectionAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "eligibility_closed",
        "nominations_open_status",
        "nominations_closed_status",
        "voting_open_status",
        "voting_closed_status",
        "nominee_count",
    )
    search_fields = ("title", "description")
    ordering = ("-membership_eligibility_deadline",)

    def eligibility_closed(self, obj):
        return timezone.now() >= obj.membership_eligibility_deadline

    eligibility_closed.boolean = True
    eligibility_closed.short_description = "Eligibility Closed"

    def nominations_open_status(self, obj):
        now = timezone.now()
        return obj.nominations_open <= now < obj.nominations_close

    nominations_open_status.boolean = True
    nominations_open_status.short_description = "Nominations Open"

    def nominations_closed_status(self, obj):
        return timezone.now() >= obj.nominations_close

    nominations_closed_status.boolean = True
    nominations_closed_status.short_description = "Nominations Closed"

    def voting_open_status(self, obj):
        now = timezone.now()
        return obj.voting_opens <= now < obj.voting_closes

    voting_open_status.boolean = True
    voting_open_status.short_description = "Voting Open"

    def voting_closed_status(self, obj):
        return timezone.now() >= obj.voting_closes

    voting_closed_status.boolean = True
    voting_closed_status.short_description = "Voting Closed"

    def nominee_count(self, obj):
        count = obj.nominees.count()
        return format_html(
            '<a href="/admin/elections/nominee/?election__id__exact={}">{} nominee{}</a>',
            obj.id,
            count,
            "s" if count != 1 else "",
        )

    nominee_count.short_description = "Nominees"


class NomineeAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "election",
        "nomination_count",
        "accepted_nomination_count",
        "created_at",
    )
    list_filter = ("election", "created_at")
    search_fields = (
        "user__first_name",
        "user__last_name",
        "user__email",
    )
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
        "nomination_count",
        "accepted_nomination_count",
    )
    ordering = ("-created_at",)
    inlines = [NominationInline]

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "id",
                    "election",
                    "user",
                    "nomination_count",
                    "accepted_nomination_count",
                    "created_at",
                    "updated_at",
                )
            },
        ),
        (
            "Profile Information",
            {
                "fields": (
                    "photo",
                    "public_display_name",
                    "board_responsibilities_acknowledged",
                )
            },
        ),
    )


class NominationAdmin(admin.ModelAdmin):
    list_display = (
        "nominee",
        "nominator",
        "get_election",
        "draft",
        "created_at",
    )
    list_filter = ("nominee__election", "draft", "created_at")
    search_fields = (
        "nominee__user__first_name",
        "nominee__user__last_name",
        "nominee__user__email",
        "nominator__first_name",
        "nominator__last_name",
        "nominator__email",
    )
    readonly_fields = ("id", "created_at", "updated_at")
    ordering = ("-created_at",)

    def get_election(self, obj):
        return obj.nominee.election

    get_election.short_description = "Election"

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "id",
                    "nominee",
                    "nominator",
                    "draft",
                    "acceptance_status",
                    "acceptance_date",
                    "acceptance_note",
                    "created_at",
                    "updated_at",
                )
            },
        ),
        ("Nomination Content", {"fields": ("nomination_statement",)}),
    )


admin.site.register(Election, ElectionAdmin)
admin.site.register(Nominee, NomineeAdmin)
admin.site.register(Nomination, NominationAdmin)
