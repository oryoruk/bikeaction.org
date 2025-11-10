from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from elections.models import Election, Nomination, Nominee, get_user_display_name


class NominationModelTests(TestCase):
    """Test critical nomination model behavior."""

    def setUp(self):
        """Create test users and election."""
        self.user_a = User.objects.create_user(
            username="user_a",
            email="a@test.com",
            first_name="Alice",
            last_name="Anderson",
        )
        self.user_b = User.objects.create_user(
            username="user_b",
            email="b@test.com",
            first_name="Bob",
            last_name="Brown",
        )

        # Create election with dates
        now = timezone.now()
        self.election = Election.objects.create(
            title="Test Election 2025",
            description="Test election",
            membership_eligibility_deadline=now - timedelta(days=30),
            nominations_open=now - timedelta(days=7),
            nominations_close=now + timedelta(days=7),
            voting_opens=now + timedelta(days=14),
            voting_closes=now + timedelta(days=21),
        )

    @patch("elections.models.Nominee.send_notification_email")
    def test_self_nomination_auto_accepts(self, mock_send_email):
        """Self-nominations should automatically be accepted."""
        # Create nominee record
        nominee = Nominee.objects.create(
            election=self.election,
            user=self.user_a,
        )

        # Create self-nomination (non-draft)
        nomination = Nomination.objects.create(
            nominee=nominee,
            nominator=self.user_a,  # Same user = self-nomination
            nomination_statement="I want to serve on the board",
            draft=False,
        )

        # Assert auto-accepted
        self.assertEqual(nomination.acceptance_status, Nomination.AcceptanceStatus.ACCEPTED)
        self.assertIsNotNone(nomination.acceptance_date)
        # Should NOT send email for self-nomination
        mock_send_email.assert_not_called()

    @patch("elections.models.Nominee.send_notification_email")
    def test_nomination_sends_email_to_nominee(self, mock_send_email):
        """Non-self nominations should send email notification."""
        # Create nominee record
        nominee = Nominee.objects.create(
            election=self.election,
            user=self.user_b,
        )

        # Create nomination from A to B (non-draft)
        nomination = Nomination.objects.create(
            nominee=nominee,
            nominator=self.user_a,
            nomination_statement="Bob would be great",
            draft=False,
        )

        # Assert email was sent
        mock_send_email.assert_called_once_with(nomination)
        # Assert still pending (not auto-accepted)
        self.assertEqual(nomination.acceptance_status, Nomination.AcceptanceStatus.PENDING)

    @patch("elections.models.Nominee.send_notification_email")
    def test_draft_nomination_does_not_send_email(self, mock_send_email):
        """Draft nominations should not send email."""
        nominee = Nominee.objects.create(election=self.election, user=self.user_b)

        # Create draft nomination
        nomination = Nomination.objects.create(
            nominee=nominee,
            nominator=self.user_a,
            nomination_statement="Draft statement",
            draft=True,
        )

        # No email for draft
        mock_send_email.assert_not_called()

        # Now submit (change draft to False)
        nomination.draft = False
        nomination.save()

        # Email should now be sent
        mock_send_email.assert_called_once_with(nomination)

    def test_duplicate_nomination_prevented_by_database(self):
        """Database constraint prevents duplicate nominations."""
        nominee = Nominee.objects.create(election=self.election, user=self.user_b)

        # Create first nomination
        Nomination.objects.create(
            nominee=nominee,
            nominator=self.user_a,
            nomination_statement="First nomination",
            draft=False,
        )

        # Try to create duplicate - should raise IntegrityError
        from django.db import IntegrityError

        with self.assertRaises(IntegrityError):
            Nomination.objects.create(
                nominee=nominee,
                nominator=self.user_a,
                nomination_statement="Second nomination",
                draft=False,
            )

    def test_nominee_unique_per_election(self):
        """Each user can only have one Nominee record per election."""
        # Create first nominee
        Nominee.objects.create(election=self.election, user=self.user_a)

        # Try to create duplicate - should raise IntegrityError
        from django.db import IntegrityError

        with self.assertRaises(IntegrityError):
            Nominee.objects.create(election=self.election, user=self.user_a)

    def test_profile_completion_requires_photo_and_acknowledgment(self):
        """is_profile_complete() requires both photo and acknowledgment."""
        nominee = Nominee.objects.create(election=self.election, user=self.user_a)

        # Initially incomplete
        self.assertFalse(nominee.is_profile_complete())

        # Add photo only
        nominee.photo = "nominee_photos/test.jpg"
        nominee.save()
        self.assertFalse(nominee.is_profile_complete())

        # Remove photo, add acknowledgment only
        nominee.photo = ""
        nominee.board_responsibilities_acknowledged = True
        nominee.save()
        self.assertFalse(nominee.is_profile_complete())

        # Add both
        nominee.photo = "nominee_photos/test.jpg"
        nominee.board_responsibilities_acknowledged = True
        nominee.save()
        self.assertTrue(nominee.is_profile_complete())

    def test_nomination_count_methods(self):
        """Test nomination counting methods on Nominee."""
        nominee = Nominee.objects.create(election=self.election, user=self.user_a)

        # Create additional users for different nominators
        user_c = User.objects.create_user(username="user_c", email="c@test.com")
        user_d = User.objects.create_user(username="user_d", email="d@test.com")

        # Create mix of nominations
        # Draft - should not count
        Nomination.objects.create(
            nominee=nominee,
            nominator=self.user_b,
            nomination_statement="Draft",
            draft=True,
        )

        # Pending - should count in total but not accepted
        Nomination.objects.create(
            nominee=nominee,
            nominator=user_c,
            nomination_statement="Pending",
            draft=False,
            acceptance_status=Nomination.AcceptanceStatus.PENDING,
        )

        # Accepted - should count in both
        Nomination.objects.create(
            nominee=nominee,
            nominator=user_d,
            nomination_statement="Accepted",
            draft=False,
            acceptance_status=Nomination.AcceptanceStatus.ACCEPTED,
        )

        self.assertEqual(nominee.nomination_count(), 2)  # Excludes draft
        self.assertEqual(nominee.accepted_nomination_count(), 1)  # Only accepted
        self.assertTrue(nominee.has_accepted_nomination())

    @patch("elections.models.Nominee.send_notification_email")
    def test_self_nomination_draft_to_submitted_auto_accepts(self, mock_send_email):
        """Self-nomination that starts as draft should auto-accept when submitted."""
        nominee = Nominee.objects.create(election=self.election, user=self.user_a)

        # Create draft self-nomination
        nomination = Nomination.objects.create(
            nominee=nominee,
            nominator=self.user_a,
            nomination_statement="Draft self-nomination",
            draft=True,
        )

        # Should still be pending
        self.assertEqual(nomination.acceptance_status, Nomination.AcceptanceStatus.PENDING)

        # Submit the draft
        nomination.draft = False
        nomination.save()

        # Should now be auto-accepted
        self.assertEqual(nomination.acceptance_status, Nomination.AcceptanceStatus.ACCEPTED)
        self.assertIsNotNone(nomination.acceptance_date)
        # Still no email for self-nomination
        mock_send_email.assert_not_called()

    def test_get_eligible_voters_returns_members_as_of_deadline(self):
        """get_eligible_voters() should return profiles who were members at the deadline."""
        from membership.models import Membership
        from profiles.models import Profile

        # Create users with profiles
        user_c = User.objects.create_user(
            username="user_c",
            email="c@test.com",
            first_name="Carol",
            last_name="Chen",
        )
        profile_c = Profile.objects.create(user=user_c)

        user_d = User.objects.create_user(
            username="user_d",
            email="d@test.com",
            first_name="David",
            last_name="Davis",
        )
        profile_d = Profile.objects.create(user=user_d)

        # Create profiles for existing test users
        profile_a = Profile.objects.create(user=self.user_a)
        profile_b = Profile.objects.create(user=self.user_b)

        # Election deadline is 30 days ago (from setUp)
        deadline = self.election.membership_eligibility_deadline

        # User A: Has membership that covers the deadline (eligible)
        Membership.objects.create(
            user=self.user_a,
            kind=Membership.Kind.FISCAL,
            start_date=(deadline - timedelta(days=60)).date(),
            end_date=(deadline + timedelta(days=30)).date(),
        )

        # User B: Has membership that ended before deadline (not eligible)
        Membership.objects.create(
            user=self.user_b,
            kind=Membership.Kind.FISCAL,
            start_date=(deadline - timedelta(days=60)).date(),
            end_date=(deadline - timedelta(days=10)).date(),
        )

        # User C: Has membership starting after deadline (not eligible)
        Membership.objects.create(
            user=user_c,
            kind=Membership.Kind.FISCAL,
            start_date=(deadline + timedelta(days=10)).date(),
            end_date=(deadline + timedelta(days=100)).date(),
        )

        # User D: No membership (not eligible)

        # Get eligible voters
        eligible_voters = self.election.get_eligible_voters()

        # Should return a QuerySet
        self.assertTrue(hasattr(eligible_voters, "count"))

        # Should include only user_a's profile
        eligible_ids = [p.id for p in eligible_voters]
        self.assertIn(profile_a.id, eligible_ids)
        self.assertNotIn(profile_b.id, eligible_ids)
        self.assertNotIn(profile_c.id, eligible_ids)
        self.assertNotIn(profile_d.id, eligible_ids)


@override_settings(
    STORAGES={
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }
)
class NominationViewTests(TestCase):
    """Test critical view logic and permissions."""

    def setUp(self):
        """Create test users and election with profiles."""
        from membership.models import Membership
        from profiles.models import Profile

        self.user_a = User.objects.create_user(
            username="user_a",
            email="a@test.com",
            first_name="Alice",
            last_name="Anderson",
            password="testpass123",
        )
        # Create complete profile for user_a
        self.profile_a = Profile.objects.create(
            user=self.user_a,
            street_address="123 Test St",
            zip_code="19123",
        )

        self.user_b = User.objects.create_user(
            username="user_b",
            email="b@test.com",
            first_name="Bob",
            last_name="Brown",
            password="testpass123",
        )
        # Create complete profile for user_b
        self.profile_b = Profile.objects.create(
            user=self.user_b,
            street_address="456 Test Ave",
            zip_code="19123",
        )

        # Create election with dates
        now = timezone.now()
        self.election = Election.objects.create(
            title="Test Election 2025",
            slug="test-election-2025",
            description="Test election",
            membership_eligibility_deadline=now - timedelta(days=30),
            nominations_open=now - timedelta(days=7),
            nominations_close=now + timedelta(days=7),
            voting_opens=now + timedelta(days=14),
            voting_closes=now + timedelta(days=21),
        )

        # Create memberships for both users (so they're eligible)
        Membership.objects.create(
            user=self.user_a,
            kind=Membership.Kind.FISCAL,
            start_date=(now - timedelta(days=60)).date(),
            end_date=(now + timedelta(days=300)).date(),
        )
        Membership.objects.create(
            user=self.user_b,
            kind=Membership.Kind.FISCAL,
            start_date=(now - timedelta(days=60)).date(),
            end_date=(now + timedelta(days=300)).date(),
        )

    @patch("elections.models.Nominee.send_notification_email")
    def test_only_nominee_nominator_or_staff_can_view_nomination(self, mock_send_email):
        """Test nomination view permissions."""
        # Create nomination from A to B
        nominee = Nominee.objects.create(election=self.election, user=self.user_b)
        nomination = Nomination.objects.create(
            nominee=nominee,
            nominator=self.user_a,
            nomination_statement="Test",
            draft=False,
        )

        # Create third user (not involved)
        user_c = User.objects.create_user(  # noqa: F841
            username="user_c", email="c@test.com", password="testpass123"
        )

        url = reverse(
            "nomination_view", kwargs={"election_slug": self.election.slug, "pk": nomination.id}
        )

        # Nominator can view
        self.client.login(username="user_a", password="testpass123")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.client.logout()

        # Nominee can view
        self.client.login(username="user_b", password="testpass123")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.client.logout()

        # Unrelated user cannot view
        self.client.login(username="user_c", password="testpass123")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)  # Redirected
        self.client.logout()

    @patch("elections.models.Nominee.send_notification_email")
    def test_cannot_accept_nomination_without_complete_profile(self, mock_send_email):
        """Accepting nomination requires complete profile."""
        # Create nomination from A to B
        nominee = Nominee.objects.create(
            election=self.election,
            user=self.user_b,
            # No photo, no acknowledgment = incomplete
        )
        nomination = Nomination.objects.create(
            nominee=nominee,
            nominator=self.user_a,
            nomination_statement="Test",
            draft=False,
        )

        # Login as nominee
        self.client.login(username="user_b", password="testpass123")

        # Try to accept
        url = reverse(
            "nomination_respond",
            kwargs={"election_slug": self.election.slug, "pk": nomination.id},
        )
        response = self.client.post(url, {"action": "accept"})

        # Should redirect to profile edit
        self.assertEqual(response.status_code, 302)
        self.assertIn("nominee", response.url)
        self.assertIn("profile", response.url)

        # Nomination should still be pending
        nomination.refresh_from_db()
        self.assertEqual(nomination.acceptance_status, Nomination.AcceptanceStatus.PENDING)

    @patch("elections.models.Nominee.send_notification_email")
    def test_can_withdraw_self_nomination(self, mock_send_email):
        """Test withdrawing a self-nomination."""
        # Create self-nomination (will auto-accept)
        nominee = Nominee.objects.create(
            election=self.election,
            user=self.user_a,
            photo="test.jpg",
            board_responsibilities_acknowledged=True,
        )
        nomination = Nomination.objects.create(
            nominee=nominee,
            nominator=self.user_a,
            nomination_statement="Self-nomination",
            draft=False,
        )

        # Should be auto-accepted
        self.assertEqual(nomination.acceptance_status, Nomination.AcceptanceStatus.ACCEPTED)

        # Login and withdraw
        self.client.login(username="user_a", password="testpass123")
        url = reverse(
            "nomination_respond",
            kwargs={"election_slug": self.election.slug, "pk": nomination.id},
        )
        response = self.client.post(url, {"action": "withdraw"})

        # Should succeed
        self.assertEqual(response.status_code, 302)

        # Check it's now declined
        nomination.refresh_from_db()
        self.assertEqual(nomination.acceptance_status, Nomination.AcceptanceStatus.DECLINED)

    @patch("elections.models.Nominee.send_notification_email")
    def test_cannot_edit_withdrawn_self_nomination(self, mock_send_email):
        """Withdrawn self-nominations cannot be edited."""
        # Create and withdraw self-nomination
        nominee = Nominee.objects.create(
            election=self.election,
            user=self.user_a,
            photo="test.jpg",
            board_responsibilities_acknowledged=True,
        )
        nomination = Nomination.objects.create(
            nominee=nominee,
            nominator=self.user_a,
            nomination_statement="Self-nomination",
            draft=False,
            acceptance_status=Nomination.AcceptanceStatus.DECLINED,  # Already withdrawn
        )

        # Try to edit
        self.client.login(username="user_a", password="testpass123")
        url = reverse(
            "nomination_edit",
            kwargs={"election_slug": self.election.slug, "pk": nomination.id},
        )
        response = self.client.get(url)

        # Should be redirected (cannot edit withdrawn)
        self.assertEqual(response.status_code, 302)


class NominationFormTests(TestCase):
    """Test form validation."""

    def setUp(self):
        """Create test data."""
        from profiles.models import Profile

        self.user_a = User.objects.create_user(
            username="user_a", email="a@test.com", first_name="Alice", last_name="Anderson"
        )
        # Create profile so user_a is in the form queryset
        Profile.objects.create(user=self.user_a, street_address="123 Test", zip_code="19123")

        self.user_b = User.objects.create_user(
            username="user_b", email="b@test.com", first_name="Bob", last_name="Brown"
        )
        # Create profile so user_b is in the form queryset
        Profile.objects.create(user=self.user_b, street_address="456 Test", zip_code="19123")

        now = timezone.now()
        self.election = Election.objects.create(
            title="Test Election 2025",
            slug="test-election-2025",
            membership_eligibility_deadline=now - timedelta(days=30),
            nominations_open=now - timedelta(days=7),
            nominations_close=now + timedelta(days=7),
            voting_opens=now + timedelta(days=14),
            voting_closes=now + timedelta(days=21),
        )

    def test_form_validates_duplicate_nomination(self):
        """Form should prevent duplicate nominations."""
        from elections.forms import NominationForm

        # Create first nomination
        nominee = Nominee.objects.create(election=self.election, user=self.user_b)
        Nomination.objects.create(
            nominee=nominee,
            nominator=self.user_a,
            nomination_statement="First",
            draft=False,
        )

        # Try to create duplicate via form
        form = NominationForm(
            data={
                "nominee": self.user_b.id,
                "nomination_statement": "Second attempt",
            },
            election=self.election,
            nominator=self.user_a,
        )

        # Should be invalid
        self.assertFalse(form.is_valid())
        self.assertIn("nominee", form.errors)
        self.assertIn("already submitted", str(form.errors["nominee"]))

    def test_form_allows_editing_existing_nomination(self):
        """Form should allow editing when nomination_id is provided."""
        from elections.forms import NominationForm

        # Create nomination
        nominee = Nominee.objects.create(election=self.election, user=self.user_b)
        nomination = Nomination.objects.create(
            nominee=nominee,
            nominator=self.user_a,
            nomination_statement="Original",
            draft=False,
        )

        # Edit same nomination should be allowed
        form = NominationForm(
            data={
                "nominee": self.user_b.id,
                "nomination_statement": "Updated statement",
            },
            instance=nomination,
            election=self.election,
            nominator=self.user_a,
            nomination_id=nomination.id,  # Provide existing ID
        )

        # Should be valid (editing own nomination)
        self.assertTrue(form.is_valid())

    def test_nominee_profile_form_requires_board_acknowledgment(self):
        """Nominee profile form should require board acknowledgment."""
        from elections.forms import NomineeProfileForm

        nominee = Nominee.objects.create(election=self.election, user=self.user_a)

        # Try to submit without acknowledgment
        form = NomineeProfileForm(
            data={
                "photo": "",  # Can be empty
                "public_display_name": "",  # Can be empty
                "board_responsibilities_acknowledged": False,  # Not checked
            },
            instance=nominee,
            user=self.user_a,
        )

        # Should be invalid (acknowledgment required)
        self.assertFalse(form.is_valid())
        self.assertIn("board_responsibilities_acknowledged", form.errors)


@override_settings(
    STORAGES={
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }
)
class PIIProtectionTests(TestCase):
    """Test that PII (Personal Identifiable Information) is properly protected."""

    def setUp(self):
        """Create test users with full names and email."""
        from membership.models import Membership
        from profiles.models import Profile

        self.user_with_long_name = User.objects.create_user(
            username="testuser",
            email="alice.anderson@example.com",
            first_name="Alice",
            last_name="AndersonLongLastName",
            password="testpass123",
        )
        Profile.objects.create(
            user=self.user_with_long_name,
            street_address="123 Test St",
            zip_code="19123",
        )

        # Create election
        now = timezone.now()
        self.election = Election.objects.create(
            title="Test Election 2025",
            slug="test-election-2025",
            membership_eligibility_deadline=now - timedelta(days=30),
            nominations_open=now - timedelta(days=7),
            nominations_close=now + timedelta(days=7),
            voting_opens=now + timedelta(days=14),
            voting_closes=now + timedelta(days=21),
        )

        # Create membership
        Membership.objects.create(
            user=self.user_with_long_name,
            kind=Membership.Kind.FISCAL,
            start_date=(now - timedelta(days=60)).date(),
            end_date=(now + timedelta(days=300)).date(),
        )

    def test_get_user_display_name_returns_first_and_last_initial(self):
        """get_user_display_name should return first name + last initial only."""
        display_name = get_user_display_name(self.user_with_long_name)

        # Should contain first name
        self.assertIn("Alice", display_name)
        # Should contain only first letter of last name
        self.assertIn("A.", display_name)
        # Should NOT contain full last name
        self.assertNotIn("Anderson", display_name)
        self.assertNotIn("LongLastName", display_name)
        # Should be exactly "Alice A."
        self.assertEqual(display_name, "Alice A.")

    def test_nominee_get_display_name_without_preferred_name(self):
        """Nominee.get_display_name should return first + last initial when no preferred name."""
        nominee = Nominee.objects.create(
            election=self.election,
            user=self.user_with_long_name,
            # No public_display_name set
        )

        display_name = nominee.get_display_name()

        # Should be first name + last initial
        self.assertEqual(display_name, "Alice A.")
        self.assertNotIn("Anderson", display_name)

    def test_nominee_get_display_name_with_preferred_name(self):
        """Nominee.get_display_name should return preferred name when set."""
        nominee = Nominee.objects.create(
            election=self.election,
            user=self.user_with_long_name,
            public_display_name="Ali Anderson",  # User chose to show full name
        )

        display_name = nominee.get_display_name()

        # Should return exactly what user specified
        self.assertEqual(display_name, "Ali Anderson")

    def test_flash_messages_dont_leak_full_names(self):
        """Success messages should not contain full last names."""
        from membership.models import Membership
        from profiles.models import Profile

        now = timezone.now()
        nominator = User.objects.create_user(
            username="nominator",
            email="bob@example.com",
            first_name="Bob",
            last_name="Brown",
            password="testpass123",
        )
        Profile.objects.create(user=nominator, street_address="456 Test", zip_code="19123")
        # Create membership so nominator is eligible
        Membership.objects.create(
            user=nominator,
            kind=Membership.Kind.FISCAL,
            start_date=(now - timedelta(days=60)).date(),
            end_date=(now + timedelta(days=300)).date(),
        )

        # Login and submit nomination
        self.client.login(username="nominator", password="testpass123")
        response = self.client.post(
            reverse("nomination_form", kwargs={"election_slug": self.election.slug}),
            {
                "nominee": self.user_with_long_name.id,
                "nomination_statement": "Great candidate",
                "submit-nomination": "Submit",
            },
            follow=True,
        )

        # Check messages don't contain full last name
        messages = list(response.context["messages"])
        self.assertTrue(len(messages) > 0)
        message_text = str(messages[0])

        # Should contain first name + initial
        self.assertIn("Alice A.", message_text)
        # Should NOT contain full last name
        self.assertNotIn("AndersonLongLastName", message_text)

    @patch("elections.models.Nominee.send_notification_email")
    def test_nominee_search_doesnt_return_email(self, mock_send_email):
        """Nominee search should never return email addresses."""
        self.client.login(username="testuser", password="testpass123")

        response = self.client.get(
            reverse("nominee_search"), {"q": "alice"}, HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )

        # Should return results
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")

        # Should contain display name
        self.assertIn("Alice A.", content)
        # Should NOT contain email
        self.assertNotIn("@example.com", content)
        self.assertNotIn("alice.anderson", content)

    @patch("elections.models.Nominee.send_notification_email")
    def test_election_detail_page_shows_safe_names(self, mock_send_email):
        """Election detail page should show first name + last initial only."""
        # Create nomination
        nominee = Nominee.objects.create(election=self.election, user=self.user_with_long_name)
        Nomination.objects.create(
            nominee=nominee,
            nominator=self.user_with_long_name,
            nomination_statement="Self-nomination",
            draft=False,
        )

        # Login and view election detail
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(
            reverse("election_detail", kwargs={"election_slug": self.election.slug})
        )

        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")

        # Should show safe display name
        self.assertIn("Alice A.", content)
        # Should NOT show full last name
        self.assertNotIn("AndersonLongLastName", content)

    @patch("elections.models.Nominee.send_notification_email")
    def test_nomination_view_shows_safe_names(self, mock_send_email):
        """Nomination view page should show first name + last initial."""
        nominee = Nominee.objects.create(election=self.election, user=self.user_with_long_name)
        nomination = Nomination.objects.create(
            nominee=nominee,
            nominator=self.user_with_long_name,
            nomination_statement="Test",
            draft=False,
        )

        # Login and view nomination
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(
            reverse(
                "nomination_view",
                kwargs={"election_slug": self.election.slug, "pk": nomination.id},
            )
        )

        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")

        # Should NOT contain full last name anywhere
        self.assertNotIn("AndersonLongLastName", content)
        # Should NOT contain email
        self.assertNotIn("alice.anderson@example.com", content)

    def test_profile_page_nominations_use_safe_names(self):
        """Profile page nominations section should display safe names for OTHER users."""
        from profiles.models import Profile

        # Create another user to nominate the first user
        nominator = User.objects.create_user(
            username="nominator",
            email="nominator@example.com",
            first_name="Bob",
            last_name="BrownLongName",
            password="testpass123",
        )
        Profile.objects.create(user=nominator, street_address="789 Test", zip_code="19123")

        # Create nomination from nominator to user_with_long_name
        nominee = Nominee.objects.create(election=self.election, user=self.user_with_long_name)

        with patch("elections.models.Nominee.send_notification_email"):
            Nomination.objects.create(
                nominee=nominee,
                nominator=nominator,
                nomination_statement="Great candidate",
                draft=False,
            )

        # Login as nominee and check profile page
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(reverse("profile"))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")

        # Nominator's name should be shown as "Bob B." not full name
        self.assertIn("Bob B.", content)
        self.assertNotIn("BrownLongName", content)

        # Nominator's email should never appear (user's own email in profile section is OK)
        self.assertNotIn("nominator@example.com", content)
