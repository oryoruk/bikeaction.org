import base64
import json

import sesame.utils
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, SuspiciousOperation
from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import FormView
from wagtail.models import Site

from pbaabp.email import send_email_message
from pbaabp.forms import EmailLoginForm, NewsletterSignupForm
from pbaabp.tasks import subscribe_to_newsletter
from profiles.tasks import add_mailjet_subscriber, unsubscribe_mailjet_email


class EmailLoginView(FormView):
    template_name = "email_login.html"
    form_class = EmailLoginForm

    def get_user(self, email):
        """Find the user with this email address."""
        User = get_user_model()
        try:
            return User.objects.get(email=email)
        except User.DoesNotExist:
            return None

    def create_link(self, user):
        """Create a login link for this user."""
        link = reverse("sesame_login")
        link = self.request.build_absolute_uri(link)
        link += sesame.utils.get_query_string(user)
        return link

    def send_email(self, user, link):
        """Send an email with this login link to this user."""
        subject = f"Login link for {self.request.get_host()}"
        message = f"""
Hello {user.first_name},

You requested that we send you a link to log in to our app:

* [Login Now]({link})

Thank you for being a part of the action!
        """
        send_email_message(None, None, [user.email], None, message=message, subject=subject)

    def email_submitted(self, email):
        user = self.get_user(email)
        if user is None:
            # Ignore the case when no user is registered with this address.
            # Possible improvement: send an email telling them to register.
            print("user not found:", email)
            return
        link = self.create_link(user)
        self.send_email(user, link)

    def form_valid(self, form):
        self.email_submitted(form.cleaned_data["email"])
        return render(self.request, "email_login_success.html")


@csrf_exempt
def newsletter_bridge(request):
    if settings.MAILJET_SECRET_SIGNUP_URL is None:
        raise Http404()

    name = request.POST.get("Name")
    email = request.POST.get("Email")

    errors = []
    if email is None:
        errors.append("Email is not provided")
    if name is None:
        errors.append("Name is not provided")
    if errors:
        raise SuspiciousOperation(f"Errors: {','.join(errors)}")

    first_name, _, last_name = name.partition(" ")
    add_mailjet_subscriber.delay(email, first_name, last_name, name)
    return HttpResponse("OK")


@csrf_exempt
def mailjet_unsubscribe(request):
    auth_header = request.META.get("HTTP_AUTHORIZATION")
    if auth_header is not None and auth_header.startswith("Basic "):
        encoded_credentials = auth_header[6:]
        decoded_credentials = base64.b64decode(encoded_credentials).decode("utf-8").split(":")
        username, password = decoded_credentials[0], decoded_credentials[1]
        if username != "mailjet" or password != settings.MAILJET_WEBHOOK_SECRET:
            raise PermissionDenied()
    else:
        raise PermissionDenied()

    data = json.loads(request.body)
    if data.get("mj_list_id") and data.get("email"):
        unsubscribe_mailjet_email.delay(data.get("mj_list_id"), data.get("email"))

    return HttpResponse("OK")


def _newsletter_signup_partial(request):
    if request.method == "POST":
        form_name = request.POST.get("form_name", None)
        show_header = request.POST.get("show_header", True)
        form = NewsletterSignupForm(request.POST, form_name=form_name, show_header=show_header)
        if form.is_valid():
            name = form.cleaned_data["newsletter_signup_name"]
            email = form.cleaned_data["newsletter_signup_email"]

            subscribe_to_newsletter.delay(email, name)

            return render(
                request,
                "_newsletter_signup_success_partial.html",
                {"first_name": name.split(" ")[0]},
            )
        else:
            return render(request, "_newsletter_signup_partial.html", {"form": form})

    return render(request, "_newsletter_signup_partial.html", {"form": form})


def wagtail_pages(request):
    site = Site.find_for_request(request)
    if site is None:
        site = Site.objects.select_related("root_page").get(is_default_site=True)
    pages = (
        site.root_page.get_descendants(inclusive=True)
        .live()
        .public()
        .order_by("path")
        .defer_streamfields()
        .specific()
    )

    return render(request, "wagtail_pages.html", {"pages": pages})
