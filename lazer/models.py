import uuid

from django.contrib.auth import get_user_model
from django.contrib.gis.db import models
from django.utils.safestring import mark_safe

User = get_user_model()


class ViolationSubmission(models.Model):
    submission_id = models.UUIDField(default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)

    captured_at = models.DateTimeField(db_index=True)
    location = models.PointField(srid=4326)
    image = models.ImageField(upload_to="lazer/violations")

    def image_tag_no_href(self):
        return mark_safe('<img src="%s" style="max-height: 50px;"/>' % (self.image.url,))

    def image_tag(self):
        return mark_safe(
            '<a href="%s"><img src="%s" style="max-height: 50px;"/></a>'
            % (self.image.url, self.image.url)
        )


def report_image_upload_to(instance, filename):
    return f"lazer/reports/{instance.submission.submission_id}/{filename}"


class ViolationReport(models.Model):
    submission = models.ForeignKey(ViolationSubmission, on_delete=models.CASCADE)

    date_observed = models.CharField()
    time_observed = models.CharField()

    make = models.CharField()
    model = models.CharField(null=True, blank=True)
    body_style = models.CharField()
    vehicle_color = models.CharField()

    violation_observed = models.CharField(db_index=True)
    occurrence_frequency = models.CharField()

    block_number = models.CharField()
    street_name = models.CharField()
    zip_code = models.CharField()

    additional_information = models.CharField(null=True, blank=True)

    screenshot_before_submit = models.ImageField(
        null=True, blank=True, upload_to=report_image_upload_to
    )
    screenshot_after_submit = models.ImageField(
        null=True, blank=True, upload_to=report_image_upload_to
    )
    screenshot_success = models.ImageField(null=True, blank=True, upload_to=report_image_upload_to)
    screenshot_error = models.ImageField(null=True, blank=True, upload_to=report_image_upload_to)
    screenshot_final = models.ImageField(null=True, blank=True, upload_to=report_image_upload_to)

    submitted = models.DateTimeField(null=True, blank=True)

    def is_submitted(self):
        return self.submitted is not None

    is_submitted.boolean = True

    def created_by(self):
        return self.submission.created_by

    def image_tag_violation_no_href(self):
        return mark_safe(
            '<img src="%s" style="max-height: 50px;"/>' % (self.submission.image.url,)
        )

    image_tag_violation_no_href.short_description = "Image"

    def violation_observed_short(self):
        return self.violation_observed.split(" (")[0]

    violation_observed_short.short_description = "Violation"

    def image_tag_violation(self):
        return mark_safe(
            '<a href="%s"><img src="%s" style="max-height: 50px;"/></a>'
            % (self.submission.image.url, self.submission.image.url)
        )

    def image_tag_before_submit(self):
        return mark_safe(
            '<a href="%s"><img src="%s" style="max-height: 50px;"/></a>'
            % (self.screenshot_before_submit.url, self.screenshot_before_submit.url)
        )

    def image_tag_after_submit(self):
        return mark_safe(
            '<a href="%s"><img src="%s" style="max-height: 50px;"/></a>'
            % (self.screenshot_after_submit.url, self.screenshot_after_submit.url)
        )

    def image_tag_success(self):
        return mark_safe(
            '<a href="%s"><img src="%s" style="max-height: 50px;"/></a>'
            % (self.screenshot_success.url, self.screenshot_success.url)
        )

    def image_tag_error(self):
        return mark_safe(
            '<a href="%s"><img src="%s" style="max-height: 50px;"/></a>'
            % (self.screenshot_error.url, self.screenshot_error.url)
        )

    def image_tag_final(self):
        return mark_safe(
            '<a href="%s"><img src="%s" style="max-height: 50px;"/></a>'
            % (self.screenshot_final.url, self.screenshot_final.url)
        )
