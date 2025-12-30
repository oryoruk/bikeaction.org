import sesame.utils
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db.models import Count
from django.urls import reverse

from lazer.models import LazerWrapped, ViolationReport
from pbaabp.email import send_email_message

SENT = []

User = get_user_model()


class Command(BaseCommand):
    help = "Send email to Laser Vision users with 5+ reports in 2025"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be sent without actually sending",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        # Find users with at least 5 reports in 2025
        users_with_reports = (
            ViolationReport.objects.filter(
                submission__created_at__year=2025,
                submission__created_by__isnull=False,
            )
            .values("submission__created_by")
            .annotate(report_count=Count("id"))
            .filter(report_count__gte=5)
        )

        user_ids = [u["submission__created_by"] for u in users_with_reports]

        users = User.objects.filter(id__in=user_ids)

        print(f"Found {users.count()} users with 5+ reports in 2025")

        for user in users:
            if user.email.lower() not in SENT:
                # Get their 2025 wrapped
                wrapped = LazerWrapped.objects.filter(user=user, year=2025).first()
                if not wrapped:
                    print(f"No 2025 wrapped found for {user.email}, skipping")
                    continue

                # Build sesame login URL with redirect to wrapped page
                wrapped_path = f"/tools/laser/wrapped/{wrapped.share_token}/"
                login_url = reverse("sesame_login")
                login_url = f"https://bikeaction.org{login_url}"
                login_url += sesame.utils.get_query_string(user)
                login_url += f"&next={wrapped_path}"

                if dry_run:
                    print(f"Would send to: {user.email} - {login_url}")
                else:
                    send_email_message(
                        "lazer-wrapped-2025",  # TODO: update template name
                        "Philly Bike Action <noreply@bikeaction.org>",
                        [user.email],
                        {
                            "first_name": user.first_name,
                            "wrapped_url": login_url,
                        },
                        reply_to=["info@bikeaction.org"],
                    )
                SENT.append(user.email.lower())
            else:
                print(f"skipping {user.email}")

        if dry_run:
            print(f"Would send to {len(SENT)} users")
        else:
            print(f"Sent {len(SENT)}")
