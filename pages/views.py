from django.shortcuts import redirect, render
from django.views.decorators.clickjacking import xframe_options_exempt
from wagtail.models import Site

from cms.models import HomePage
from pages.models import LegacyQRCode, LegacyQRCodeScan


def index(request, *args, **kwargs):
    # Handle legacy qr codes, which were sent to the index page 💀
    # /?rest_route=/rapi/dynamic-qr-code&qr=take-the-lane-rsvp
    if request.GET.get("rest_route", None) == "/rapi/dynamic-qr-code":
        if qr := request.GET.get("qr", None):
            qr_code = LegacyQRCode.objects.filter(active=True, key=qr).first()
            if qr_code:
                LegacyQRCodeScan.objects.create(qr_code=qr_code)
                return redirect(qr_code.target)

    site = Site.find_for_request(request)
    root_page = site.root_page
    page = HomePage.objects.get(id=root_page.id)
    return page.serve(request)


def brand(request):
    return render(request, "brand-guidelines.html")


def safe_streets_ride(request):
    return render(request, "safe-streets-ride.html")


@xframe_options_exempt
def safe_streets_ride_inner(request):
    return render(request, "safe-streets-ride-inner.html")
