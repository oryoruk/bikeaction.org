from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver
from easy_thumbnails.signals import saved_file
from sitetree.models import Tree, TreeItem
from sitetree.sitetreeapp import get_sitetree

from pbaabp.tasks import generate_thumbnails


@receiver(saved_file)
def generate_thumbnails_async(sender, fieldfile, **kwargs):
    app_name = sender._meta.app_label
    object_name = sender._meta.object_name
    generate_thumbnails.delay(
        app_name=app_name,
        object_name=object_name,
        pk=fieldfile.instance.pk,
        field=fieldfile.field.name,
    )


@receiver(post_save, sender=Tree)
@receiver(post_save, sender=TreeItem)
@receiver(post_delete, sender=TreeItem)
@receiver(m2m_changed, sender=TreeItem.access_permissions)
def purge_sitetree_cache(sender, instance, **kwargs):
    cache_ = get_sitetree().cache
    cache_.empty()
    cache_.reset()
