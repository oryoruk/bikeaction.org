import hashlib
import json

from csvexport.actions import csvexport
from django.contrib import admin
from django.shortcuts import render
from ordered_model.admin import OrderedModelAdmin

from campaigns.models import Campaign, Petition, PetitionSignature
from campaigns.tasks import geocode_signature
from facets.models import District, RegisteredCommunityOrganization
from pbaabp.admin import ReadOnlyLeafletGeoAdminMixin


class CampaignAdmin(OrderedModelAdmin):
    readonly_fields = ["wordpress_id", "donation_total"]
    autocomplete_fields = ["events"]
    list_display = ("__str__", "status", "visible", "move_up_down_links")
    list_filter = ["status", "visible"]
    ordering = ("status", "order")

    def get_form(self, *args, **kwargs):
        help_texts = {
            "donation_action": "Encourage one-time donation",
            "subscription_action": "Encourage recurring donation",
        }
        kwargs.update({"help_texts": help_texts})
        return super().get_form(*args, **kwargs)


def pretty_report(modeladmin, request, queryset):
    _petitions = {}
    for petition in queryset:
        _petitions[petition] = sorted(
            list(petition.signatures.order_by("email").distinct("email").all()),
            key=lambda x: x.created_at,
        )
    return render(request, "petition_signatures_pretty_report.html", {"petitions": _petitions})


class PetitionAdmin(admin.ModelAdmin):
    actions = [pretty_report]
    readonly_fields = ["petition_report"]

    def petition_report(self, obj):
        report = ""
        totalsigs = obj.signatures.count()
        report += f"Total signatures: {totalsigs}\n"
        totaldistinctsigs = obj.signatures.distinct("email").count()
        report += f"Total signatures (distinct by email): {totaldistinctsigs}\n\n"
        nongeocoded = obj.signatures.distinct("email").filter(location=None).count()
        report += f"Non-geocoded signatures: {nongeocoded}\n\n"
        report += "Districts:\n"
        philly = 0
        for district in District.objects.all():
            cnt = obj.signatures.filter(location__within=district.mpoly).distinct("email").count()
            philly += cnt
            report += f"{district.name}: {cnt}\n"
        report += f"\nAll of Philadelphia: {philly}\n"
        report += "\nRCOs:\n"
        for rco in RegisteredCommunityOrganization.objects.all():
            cnt = obj.signatures.filter(location__within=rco.mpoly).distinct("email").count()
            report += f"{rco.name}: {cnt}\n"
        return report


def geocode(modeladmin, request, queryset):
    for obj in queryset:
        if obj.location is None:
            geocode_signature.delay(obj.id)


def randomize_lat_long(salt, lat, long):
    hash = hashlib.sha256(f"{salt}-{lat}-{long}".encode())
    smear_int = int.from_bytes(hash.digest(), "big")
    x_smear = (((smear_int % 2179) / 2179) - 0.5) * 0.000287
    y_smear = (((smear_int % 2803) / 2803) - 0.5) * 0.000358
    return (lat + x_smear, long + y_smear)


def heatmap(modeladmin, request, queryset):
    pins = []
    for signature in queryset:
        if signature.location:
            lat, lng = randomize_lat_long(
                signature.petition.id, signature.location.y, signature.location.x
            )
            pins.append([lat, lng, 1])
    return render(request, "petition/heatmap.html", {"pins_json": json.dumps(pins)})


class DistrictFilter(admin.SimpleListFilter):
    title = "District"
    parameter_name = "district"

    def lookups(self, request, model_amin):
        return [(f.id, f.name) for f in District.objects.all() if f.targetable]

    def queryset(self, request, queryset):
        if self.value():
            d = District.objects.get(id=self.value())
            return queryset.filter(location__within=d.mpoly)
        return queryset


class PetitionSignatureAdmin(admin.ModelAdmin, ReadOnlyLeafletGeoAdminMixin):
    actions = [csvexport, geocode, heatmap]
    list_display = [
        "get_name",
        "email",
        "zip_code",
        "created_at",
        "has_comment",
        "visible",
        "get_petition",
    ]
    list_filter = ["petition", "visible", DistrictFilter]
    ordering = ["-created_at"]
    search_fields = ["first_name", "last_name", "comment", "email", "zip_code"]
    readonly_fields = [
        "first_name",
        "last_name",
        "email",
        "postal_address_line_1",
        "postal_address_line_2",
        "city",
        "state",
        "zip_code",
        "comment",
        "petition",
        "created_at",
    ]

    csvexport_selected_fields = [
        "first_name",
        "last_name",
        "email",
        "postal_address_line_1",
        "postal_address_line_2",
        "city",
        "state",
        "zip_code",
        "comment",
        "petition.title",
    ]

    def get_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"

    get_name.short_description = "Name"

    def get_petition(self, obj):
        return str(obj.petition)[:37] + "..." if len(str(obj.petition)) > 37 else ""

    get_petition.short_description = "Petition"

    def has_comment(self, obj):
        return bool(obj.comment)

    has_comment.boolean = True


admin.site.register(Campaign, CampaignAdmin)
admin.site.register(Petition, PetitionAdmin)
admin.site.register(PetitionSignature, PetitionSignatureAdmin)
