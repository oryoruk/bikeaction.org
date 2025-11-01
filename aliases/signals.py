from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from aliases.models import Alias
from aliases.tasks import remove_alias_from_mailgun, sync_alias_to_mailgun


@receiver(post_save, sender=Alias)
def update_mailgun(sender, instance, created, **kwargs):
    transaction.on_commit(lambda: sync_alias_to_mailgun.delay(instance.id))


@receiver(post_delete, sender=Alias)
def remove_mailgun_route(sender, instance, **kwargs):
    if instance.mailgun_id:
        transaction.on_commit(
            lambda: remove_alias_from_mailgun.delay(
                instance.alias, instance.domain, instance.mailgun_id
            )
        )
