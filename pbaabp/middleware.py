import zoneinfo

from django.conf import settings
from django.utils import timezone

from pbaabp.forms import NewsletterSignupForm


class TimezoneMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        tzname = settings.TIME_ZONE
        if tzname:
            timezone.activate(zoneinfo.ZoneInfo(tzname))
        else:
            timezone.deactivate()
        return self.get_response(request)


class FooterNewsletterSignupFormMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.newsletter_form = NewsletterSignupForm(form_name="footer")
        request.google_recaptcha_site_key = settings.RECAPTCHA_PUBLIC_KEY
        return self.get_response(request)
