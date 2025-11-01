from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from lazer.models import ViolationReport
from lazer.tasks import submit_violation_report_discord, submit_violation_report_to_ppa


@receiver(post_save, sender=ViolationReport, dispatch_uid="violation_report_post_save")
def violation_report_post_save(sender, instance, created, update_fields, **kwargs):
    if instance.submitted is not None:
        return
    if created:
        if (
            ViolationReport.objects.filter(
                submission__created_by=instance.submission.created_by, submitted__isnull=False
            ).count()
            > 1
        ):
            transaction.on_commit(lambda: submit_violation_report_to_ppa.delay(instance.id))
        else:
            transaction.on_commit(lambda: submit_violation_report_discord.delay(instance.id))
