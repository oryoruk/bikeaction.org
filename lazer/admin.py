import asyncio

from admin_extra_buttons.api import ExtraButtonsMixin, button
from django.contrib import admin
from django.db.models import Q
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from facets.utils import reverse_geocode_point
from lazer.models import ViolationReport, ViolationSubmission
from lazer.tasks import submit_violation_report_to_ppa
from pbaabp.admin import ReadOnlyLeafletGeoAdminMixin


class ViolationSubmissionAdmin(ReadOnlyLeafletGeoAdminMixin, admin.ModelAdmin):
    list_display = (
        "image_tag_no_href",
        "captured_at",
        "created_by",
        "location",
        "violation_report_link",
    )
    readonly_fields = ("image_tag", "reverse_geocode_results")
    search_fields = (
        "created_by__email",
        "created_by__first_name",
        "created_by__last_name",
    )

    def violation_report_link(self, obj):
        try:
            report = ViolationReport.objects.get(submission=obj)
            url = reverse("admin:lazer_violationreport_change", args=[report.id])
            return format_html('<a href="{}">View Report</a>', url)
        except ViolationReport.DoesNotExist:
            return "-"

    violation_report_link.short_description = "Report"

    def reverse_geocode_results(self, obj):
        if not obj.location:
            return "No location data available"

        try:
            # Run the async function in a sync context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            coordinates = f"{obj.location.y}, {obj.location.x}"
            addresses = loop.run_until_complete(
                reverse_geocode_point(coordinates, exactly_one=False)
            )

            if not addresses:
                return "No addresses found"

            # Format the results as HTML
            html_parts = ["<div style='margin-top: 10px;'>"]
            html_parts.append(f"<strong>Coordinates:</strong> {coordinates}<br><br>")
            html_parts.append("<strong>Possible Addresses:</strong><br>")
            html_parts.append("<ul>")

            for i, address in enumerate(addresses):
                html_parts.append(f"<li>{address.address}</li>")

            html_parts.append("</ul>")
            html_parts.append("</div>")

            return mark_safe("".join(html_parts))

        except Exception as e:
            return f"Error retrieving addresses: {str(e)}"
        finally:
            loop.close()

    reverse_geocode_results.short_description = "Reverse Geocode Results"


class IsSubmittedFilter(admin.SimpleListFilter):
    title = "is submitted"
    parameter_name = "submitted"

    def lookups(self, request, model_admin):
        return ((True, "Yes"), (False, "No"))

    def queryset(self, request, queryset):
        if self.value() == "True":
            return queryset.filter(
                submitted__isnull=False,
            )
        elif self.value() == "False":
            return queryset.filter(Q(submitted__isnull=True))
        return queryset


class ViolationReportAdmin(ExtraButtonsMixin, admin.ModelAdmin):
    list_display = (
        "image_tag_violation_no_href",
        "violation_observed_short",
        "is_submitted",
        "created_by",
        "date_observed",
        "time_observed",
    )
    list_filter = ("violation_observed", IsSubmittedFilter)
    list_select_related = True
    search_fields = (
        "submission__created_by__email",
        "submission__created_by__first_name",
        "submission__created_by__last_name",
    )
    readonly_fields = (
        "image_tag_violation",
        "image_tag_before_submit",
        "image_tag_after_submit",
        "image_tag_success",
        "image_tag_error",
        "image_tag_final",
    )
    actions = ["bulk_resubmit_violations"]

    @button(
        label="Resubmit",
        change_form=True,
        change_list=True,
        permission=lambda request, obj, **kw: bool(obj.screenshot_error) or obj.submitted is None,
    )
    def resubmit(self, request, object_id):
        report = ViolationReport.objects.get(pk=object_id)
        submit_violation_report_to_ppa.delay(report.id)

    @admin.action(description="Re-submit selected violations to PPA")
    def bulk_resubmit_violations(self, request, queryset):
        """Bulk action to re-submit multiple violation reports to the PPA."""
        count = 0
        for report in queryset:
            # Queue each report for submission
            submit_violation_report_to_ppa.delay(report.id)
            count += 1

        self.message_user(
            request,
            f"Successfully queued {count} violation report(s) for re-submission to the PPA. "
            f"Check the Celery worker logs for progress.",
        )


admin.site.register(ViolationSubmission, ViolationSubmissionAdmin)
admin.site.register(ViolationReport, ViolationReportAdmin)
