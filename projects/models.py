import uuid

from django.contrib.auth.models import User
from django.contrib.postgres.fields import ArrayField
from django.db import models, transaction
from django.template.loader import render_to_string

from projects.forms import ProjectApplicationForm


class ProjectApplication(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    submitter = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    project_lead_id = models.CharField(max_length=64, null=True, blank=True)

    # Draft Status
    draft = models.BooleanField(default=False)

    # Submission Data
    data = models.JSONField()
    markdown = models.TextField(blank=True, null=True)
    thread_id = models.CharField(max_length=64, null=True, blank=True)

    # Voting Data
    vote_initiator = models.CharField(max_length=64, null=True, blank=True)
    voting_thread_id = models.CharField(max_length=64, null=True, blank=True)
    yay_votes = ArrayField(models.CharField(max_length=32), default=list, blank=True)
    nay_votes = ArrayField(models.CharField(max_length=32), default=list, blank=True)

    # Channel Data
    channel_id = models.CharField(max_length=64, null=True, blank=True)

    # Mentor for this project
    mentor_id = models.CharField(max_length=64, null=True, blank=True)

    # Lifecycle Statuses
    approved = models.BooleanField(default=False)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.CharField(max_length=64, null=True, blank=True)
    archived = models.BooleanField(default=False)
    archived_at = models.DateTimeField(null=True, blank=True)
    archived_by = models.CharField(max_length=64, null=True, blank=True)

    def __str__(self):
        return f"{self.data.get('shortname', {'value': 'TBD'}).get('value')}"

    def render_markdown(self):
        context = {field: data["value"] for field, data in self.data.items()}
        form = ProjectApplicationForm(label_suffix="")
        context["application"] = self
        context["form"] = form
        self.markdown = render_to_string("project_application.md", context)

    def save(self, *args, **kwargs):
        if not self.draft and not self.thread_id:
            from projects.tasks import add_new_project_message_and_thread

            transaction.on_commit(lambda: add_new_project_message_and_thread.delay(self.id))
        super(ProjectApplication, self).save(*args, **kwargs)
