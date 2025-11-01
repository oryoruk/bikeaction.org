from django.apps import apps
from django.contrib import admin
from django.contrib.admin.sites import NotRegistered
from djstripe.models import WebhookEndpoint
from leaflet.admin import LeafletGeoAdminMixin


class ReadOnlyLeafletGeoAdminMixin(LeafletGeoAdminMixin):
    modifiable = False


app_models = apps.get_app_config("djstripe").get_models()
for model in app_models:
    if model != WebhookEndpoint:
        try:
            admin.site.unregister(model)
        except NotRegistered:
            pass
