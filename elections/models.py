import uuid

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.utils.text import slugify


def get_user_display_name(user):
    """
    Get safe public display name for a user.
    Returns first name + last initial only.
    NEVER returns full last name, email, or discord handle.
    """
    first_name = user.first_name or ""
    last_name = user.last_name or ""
    last_initial = f"{last_name[0]}." if last_name else ""
    return f"{first_name} {last_initial}".strip() or user.username


class Election(models.Model):
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    description = models.TextField(blank=True)

    membership_eligibility_deadline = models.DateTimeField(
        help_text="Deadline for membership eligibility to vote"
    )
    nominations_open = models.DateTimeField(help_text="When nominations open")
    nominations_close = models.DateTimeField(help_text="When nominations close")
    voting_opens = models.DateTimeField(help_text="When voting opens")
    voting_closes = models.DateTimeField(help_text="When voting closes")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def get_upcoming(cls):
        """
        Get the next upcoming election where the membership eligibility deadline hasn't passed.
        Returns None if no upcoming elections.
        """
        return (
            cls.objects.filter(membership_eligibility_deadline__gte=timezone.now())
            .order_by("membership_eligibility_deadline")
            .first()
        )

    def is_nominations_open(self):
        """Check if nominations are currently open."""
        now = timezone.now()
        return self.nominations_open <= now < self.nominations_close

    def is_nominations_closed(self):
        """Check if nominations have closed."""
        return timezone.now() >= self.nominations_close

    def is_acceptance_period_closed(self):
        """Check if the acceptance period has closed (7 days after nominations close)."""
        import datetime

        acceptance_deadline = self.nominations_close + datetime.timedelta(days=7)
        return timezone.now() >= acceptance_deadline

    def is_voting_open(self):
        """Check if voting is currently open."""
        now = timezone.now()
        return self.voting_opens <= now < self.voting_closes

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class Nominee(models.Model):
    """
    Represents a person who has been nominated for an election.
    Can have multiple nominations from different nominators.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    election = models.ForeignKey(Election, on_delete=models.CASCADE, related_name="nominees")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="nominee_records")

    # Public display information
    photo = models.ImageField(
        upload_to="nominee_photos/",
        blank=True,
        null=True,
        help_text="A headshot, selfie, or even discord profile picture",
    )
    public_display_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Optional, if you go by a different name than you provided on your profile",
    )
    board_responsibilities_acknowledged = models.BooleanField(
        default=False,
        help_text=mark_safe(
            "I have read the <a href='https://docs.google.com/document/d/"
            "1ptPY_IUtLQR6gI_yN76YwRmKGN9SsWXwol66HLl5iS0/edit?tab=t.0' "
            "target='_blank'>PBA Board "
            "responsibilities and expectations</a>"
        ),
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("election", "user")
        ordering = ["-created_at"]

    def __str__(self):
        nominee_name = self.user.get_full_name() or self.user.email
        return f"{nominee_name} for {self.election.title}"

    def nomination_count(self):
        """Return count of non-draft nominations."""
        return self.nominations.filter(draft=False).count()

    def accepted_nomination_count(self):
        """Return count of accepted nominations."""
        return self.nominations.filter(draft=False, acceptance_status="accepted").count()

    def has_accepted_nomination(self):
        """Check if nominee has accepted at least one nomination."""
        return self.nominations.filter(draft=False, acceptance_status="accepted").exists()

    def is_profile_complete(self):
        """Check if nominee profile is complete (has photo and acknowledged responsibilities)."""
        return bool(self.photo) and self.board_responsibilities_acknowledged

    def get_display_name(self):
        """
        Get the public display name for this nominee.
        Returns public_display_name if set, otherwise first name + last initial.
        NEVER returns full last name, email, or discord handle.
        """
        if self.public_display_name:
            return self.public_display_name

        first_name = self.user.first_name or ""
        last_name = self.user.last_name or ""
        last_initial = f"{last_name[0]}." if last_name else ""
        return f"{first_name} {last_initial}".strip()

    def get_slug(self):
        """
        Generate a URL-safe slug for the nominee based on first name + last initial.
        Format: firstname-l
        """
        from django.utils.text import slugify

        first_name = self.user.first_name or ""
        last_name = self.user.last_name or ""
        last_initial = last_name[0].lower() if last_name else ""

        if self.public_display_name:
            return slugify(self.public_display_name)

        return slugify(f"{first_name}-{last_initial}")

    def send_notification_email(self, nomination):
        """Send email notification to nominee for a specific nomination."""
        from django.db import transaction

        from elections.tasks import send_nomination_notification

        transaction.on_commit(lambda: send_nomination_notification.delay(str(nomination.id)))


class Nomination(models.Model):
    """
    Represents a single nomination of a person for an election.
    Multiple people can nominate the same Nominee.
    """

    class AcceptanceStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        DECLINED = "declined", "Declined"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nominee = models.ForeignKey(Nominee, on_delete=models.CASCADE, related_name="nominations")
    nominator = models.ForeignKey(User, on_delete=models.CASCADE, related_name="nominations_given")

    # Nomination statement
    nomination_statement = models.TextField(
        help_text="Why are you nominating this person?", blank=True, default=""
    )

    # Draft support
    draft = models.BooleanField(default=False)

    # Acceptance tracking (nominee's response to this specific nomination)
    acceptance_status = models.CharField(
        max_length=20,
        choices=AcceptanceStatus.choices,
        default=AcceptanceStatus.PENDING,
    )
    acceptance_date = models.DateTimeField(null=True, blank=True)
    acceptance_note = models.TextField(
        blank=True, null=True, help_text="Optional note from nominee about their decision"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("nominee", "nominator")
        ordering = ["-created_at"]

    def __str__(self):
        nominee_name = self.nominee.user.get_full_name() or self.nominee.user.email
        nominator_name = self.nominator.get_full_name() or self.nominator.email
        status = " (Draft)" if self.draft else f" ({self.get_acceptance_status_display()})"
        return f"{nominee_name} nominated by {nominator_name}{status}"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        was_draft = False
        is_self_nomination = self.nominator == self.nominee.user

        if not is_new:
            try:
                old_instance = Nomination.objects.get(pk=self.pk)
                was_draft = old_instance.draft
            except Nomination.DoesNotExist:
                pass

        # Auto-accept self-nominations
        if not self.draft and is_self_nomination and (is_new or was_draft):
            if self.acceptance_status == Nomination.AcceptanceStatus.PENDING:
                self.acceptance_status = Nomination.AcceptanceStatus.ACCEPTED
                self.acceptance_date = timezone.now()

        super().save(*args, **kwargs)

        # Send email notification for new non-draft nominations (but skip self-nominations)
        if not self.draft and (is_new or was_draft) and not is_self_nomination:
            self.nominee.send_notification_email(self)
