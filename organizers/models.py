import uuid

from django.contrib.auth.models import User
from django.db import models, transaction
from django.template.loader import render_to_string

from organizers.forms import OrganizerApplicationForm


class OrganizerApplication(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    submitter = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    thread_id = models.CharField(max_length=64, null=True, blank=True)

    draft = models.BooleanField(default=False)

    data = models.JSONField()
    markdown = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.submitter.first_name} {self.submitter.last_name}"

    def render_markdown(self):
        context = {field: data["value"] for field, data in self.data.items()}
        form = OrganizerApplicationForm(label_suffix="")
        context["application"] = self
        context["form"] = form
        self.markdown = render_to_string("organizer_application.md", context)

    def save(self, *args, **kwargs):
        self.render_markdown()
        if not self.draft and not self.thread_id:
            from organizers.tasks import add_new_organizer_message_and_thread

            transaction.on_commit(lambda: add_new_organizer_message_and_thread.delay(self.id))
        super(OrganizerApplication, self).save(*args, **kwargs)
