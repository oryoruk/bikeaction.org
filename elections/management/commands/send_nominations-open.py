from datetime import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from pbaabp.email import send_email_message
from profiles.models import Profile

# Track sent emails to avoid duplicates if the command is run multiple times
SENT = []


class Command(BaseCommand):
    help = "Send nominations-open email to all members who were eligible voters as of 2025-10-15"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print eligible users without sending emails",
        )

    def handle(self, *args, **options):
        dry_run = options.get("dry_run", False)

        # Target date for eligibility check
        target_date = timezone.make_aware(datetime(2025, 10, 15))

        eligible_count = 0
        ineligible_count = 0
        skipped_count = 0

        for profile in Profile.objects.all().select_related("user"):
            user_email = profile.user.email.lower()

            # Skip if already sent
            if user_email in SENT:
                skipped_count += 1
                self.stdout.write(f"Skipping {profile.user.email} (already sent)")
                continue

            # Check if user was eligible as of target date
            eligibility = profile.eligible_as_of(target_date)

            if eligibility["eligible"]:
                eligible_count += 1

                if dry_run:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Would send to: {profile.user.first_name} {profile.user.last_name} "
                            f"<{profile.user.email}>"
                        )
                    )
                else:
                    try:
                        send_email_message(
                            "nominations-open",
                            "Philly Bike Action <noreply@bikeaction.org>",
                            [profile.user.email],
                            {
                                "first_name": profile.user.first_name,
                            },
                            reply_to=["info@bikeaction.org"],
                        )
                        SENT.append(user_email)
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"Sent to: {profile.user.first_name} {profile.user.last_name} "
                                f"<{profile.user.email}>"
                            )
                        )
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(f"Failed to send to {profile.user.email}: {str(e)}")
                        )
            else:
                ineligible_count += 1
                self.stdout.write(
                    f"Skipping {profile.user.email} (not eligible as of {target_date.date()})"
                )

        # Summary
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS("Summary:"))
        self.stdout.write(f"  Eligible users: {eligible_count}")
        self.stdout.write(f"  Ineligible users: {ineligible_count}")
        self.stdout.write(f"  Already sent: {skipped_count}")
        if not dry_run:
            self.stdout.write(self.style.SUCCESS(f"  Total sent: {len(SENT)}"))
        else:
            self.stdout.write(self.style.WARNING("  DRY RUN - No emails sent"))
