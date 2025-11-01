import datetime

from django import forms
from django.contrib import admin
from django.db.models import Value
from django.db.models.functions import Concat
from django.forms.models import BaseInlineFormSet

from aliases.models import Alias, AliasRecipient


class AliasRecipientInlineFormset(BaseInlineFormSet):
    def clean(self):
        super().clean()

        emails = []
        for form in self.forms:
            if self.can_delete and self._should_delete_form(form):
                continue
            email = form.cleaned_data.get("email_address")
            if email:
                if email in emails:
                    form.add_error("email_address", "Recipients must be unique")
                emails.append(email)


class AliasRecipientForm(forms.ModelForm):
    class Meta:
        model = AliasRecipient
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()
        if email_address := cleaned_data.get("email_address"):
            try:
                if AliasRecipient.objects.exclude(id=self.instance.id).filter(
                    alias=self.instance.alias, email_address=email_address
                ):
                    self.add_error(
                        "email_address",
                        (
                            "This recipient already exists for "
                            f"{self.instance.alias.alias}@{self.instance.alias.domain}."
                        ),
                    )
            except AliasRecipient.alias.RelatedObjectDoesNotExist:
                pass
        return cleaned_data


class AliasRecipientInline(admin.TabularInline):
    model = AliasRecipient
    form = AliasRecipientForm
    formset = AliasRecipientInlineFormset
    extra = 0


class AliasAdmin(admin.ModelAdmin):
    list_display = ("get_alias_display", "recip_display", "ready")
    inlines = [AliasRecipientInline]
    readonly_fields = ("domain", "mailgun_id", "mailgun_smtp_password", "ready")
    search_fields = ("alias", "recipients__email_address", "fq_alias")

    fieldsets = [
        ("ALIAS CONFIGURATION", {"fields": ("alias", "domain", "enable_smtp")}),
        ("Status", {"fields": ("ready", "mailgun_id", "mailgun_smtp_password")}),
    ]

    def get_form(self, request, obj=None, **kwargs):
        if obj and obj.enable_smtp and obj.mailgun_smtp_password:
            help_text = (
                f"SMTP Username: {obj.alias}@{obj.domain}<br>"
                f"SMTP Password: {obj.mailgun_smtp_password}<br>"
                "SMTP Hostname: smtp.mailgun.org<br>"
                "SMTP Port: 587<br>"
                "SMTP TLS: Yes<br>"
                'See <a href="https://support.google.com/mail/answer/22370">here</a> '
                'for instructions for gmail. <b>Note</b>: uncheck "treat as an alias"'
            )
        elif obj and obj.enable_smtp and not obj.mailgun_smtp_password:
            help_text = "SMTP credentials not ready, try refreshing..."
        else:
            help_text = "n/a"
        kwargs.update({"help_texts": {"mailgun_smtp_password": help_text}})
        return super(AliasAdmin, self).get_form(request, obj, **kwargs)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.annotate(
            fq_alias=Concat(
                "alias",
                Value("@"),
                "domain",
            )
        )
        qs = qs.order_by("alias")
        return qs

    def recip_display(self, obj=None):
        if obj is None:
            return None
        return ", ".join([r.email_address for r in obj.recipients.all()])

    recip_display.short_description = "Recipients"

    def ready(self, obj=None):
        if obj is None:
            return False
        return (
            (obj.mailgun_id is not None)
            and (obj.mailgun_updated_at is not None)
            and (obj.mailgun_updated_at > obj.updated_at - datetime.timedelta(seconds=1))
        )

    ready.boolean = True
    ready.short_description = "Alias ready"

    def get_alias_display(self, obj=None):
        if obj is None:
            return None
        return f"{obj.alias}@{obj.domain}"

    get_alias_display.short_description = "Alias"
    get_alias_display.admin_order_field = "alias"


admin.site.register(Alias, AliasAdmin)
