import csv
import datetime
import os
import uuid
from io import StringIO

from allauth.socialaccount.models import SocialAccount
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from djstripe.models import Customer, Price, Product, Subscription

from facets.models import District, ZipCode
from membership.models import Membership
from profiles.models import DiscordActivity, Profile

User = get_user_model()


class ExportVoterListCommandTestCase(TestCase):
    def setUp(self):
        """Create test data for all tests"""
        # Create test users
        self.user1 = User.objects.create_user(
            username="member1",
            email="member1@example.com",
            password="testpass",
            first_name="Alice",
            last_name="Smith",
        )
        self.profile1 = Profile.objects.create(user=self.user1)

        self.user2 = User.objects.create_user(
            username="member2",
            email="member2@example.com",
            password="testpass",
            first_name="Bob",
            last_name="Jones",
        )
        self.profile2 = Profile.objects.create(user=self.user2)

        self.user3 = User.objects.create_user(
            username="member3",
            email="member3@example.com",
            password="testpass",
            first_name="Carol",
            last_name="Williams",
        )
        self.profile3 = Profile.objects.create(user=self.user3)

        # Create test districts with simple geometry
        self.district5 = District.objects.create(
            name="District 5",
            mpoly=MultiPolygon(
                Polygon(
                    (
                        (-75.1, 39.9),
                        (-75.1, 40.0),
                        (-75.0, 40.0),
                        (-75.0, 39.9),
                        (-75.1, 39.9),
                    )
                )
            ),
            properties={},
        )

        self.district7 = District.objects.create(
            name="District 7",
            mpoly=MultiPolygon(
                Polygon(
                    (
                        (-75.2, 39.9),
                        (-75.2, 40.0),
                        (-75.1, 40.0),
                        (-75.1, 39.9),
                        (-75.2, 39.9),
                    )
                )
            ),
            properties={},
        )

        # Set user locations (in districts)
        self.profile1.location = Point(-75.05, 39.95)  # In District 5
        self.profile1.street_address = "123 Main St"
        self.profile1.save()

        self.profile2.location = Point(-75.15, 39.95)  # In District 7
        self.profile2.street_address = "456 Oak Ave"
        self.profile2.save()

        # user3 has no location (no district)

    def _create_stripe_subscription(self, user, status="active", days_until_end=60):
        """Helper to create a Stripe subscription for a user"""
        customer = Customer.objects.create(
            id=f"cus_{uuid.uuid4().hex[:10]}",
            subscriber=user,
            livemode=False,
        )

        product, _ = Product.objects.get_or_create(
            id=f"prod_{uuid.uuid4().hex[:10]}",
            defaults={
                "name": "Monthly Donation",
                "type": "service",
                "livemode": False,
            },
        )

        price, _ = Price.objects.get_or_create(
            id=f"price_{uuid.uuid4().hex[:10]}",
            defaults={
                "product": product,
                "currency": "usd",
                "unit_amount": 1000,
                "recurring": {"interval": "month"},
                "livemode": False,
                "active": True,
            },
        )

        now = timezone.now()
        return Subscription.objects.create(
            id=f"sub_{uuid.uuid4().hex[:10]}",
            customer=customer,
            status=status,
            created=now - datetime.timedelta(days=60),  # Created 60 days ago
            current_period_start=now - datetime.timedelta(days=30),
            current_period_end=now + datetime.timedelta(days=days_until_end),
            livemode=False,
        )

    def _create_discord_activity(self, user, days_ago=5):
        """Helper to create Discord activity for a user"""
        # Create Discord social account
        SocialAccount.objects.get_or_create(
            user=user,
            provider="discord",
            defaults={"uid": f"discord_{user.id}"},
        )

        # Create activity
        date = timezone.now().date() - datetime.timedelta(days=days_ago)
        DiscordActivity.objects.create(profile=user.profile, date=date, count=10)

    def _read_csv(self, filename):
        """Helper to read and parse CSV file"""
        with open(filename, "r") as f:
            reader = csv.DictReader(f)
            return list(reader)

    def test_export_with_explicit_membership(self):
        """Test exporting users with explicit Membership records"""
        now = timezone.now().date()

        # Create active membership for user1
        Membership.objects.create(
            user=self.user1,
            kind=Membership.Kind.FISCAL,
            start_date=now - datetime.timedelta(days=30),
            end_date=None,
        )

        # Export
        output_file = "test_export_membership.csv"
        try:
            call_command("export_voter_list", now.isoformat(), output=output_file)

            # Verify CSV
            rows = self._read_csv(output_file)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["email"], "member1@example.com")
            # Verify unique_id format: d5-{UUID}
            self.assertTrue(rows[0]["unique_id"].startswith("d5-"))
            uuid.UUID(rows[0]["unique_id"].split("-", 1)[1])  # Verify UUID part
            self.assertEqual(rows[0]["full_name"], "Alice Smith")
            # Verify password is literal "password,"
            self.assertEqual(rows[0]["password"], "password,")
        finally:
            if os.path.exists(output_file):
                os.remove(output_file)

    def test_export_with_discord_activity(self):
        """Test exporting users with Discord activity"""
        now = timezone.now().date()

        # Create Discord activity for user2
        self._create_discord_activity(self.user2, days_ago=10)

        # Export
        output_file = "test_export_discord.csv"
        try:
            call_command("export_voter_list", now.isoformat(), output=output_file)

            # Verify CSV
            rows = self._read_csv(output_file)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["email"], "member2@example.com")
            # Verify unique_id format: d7-{UUID}
            self.assertTrue(rows[0]["unique_id"].startswith("d7-"))
            uuid.UUID(rows[0]["unique_id"].split("-", 1)[1])  # Verify UUID part
            self.assertEqual(rows[0]["full_name"], "Bob Jones")
        finally:
            if os.path.exists(output_file):
                os.remove(output_file)

    def test_export_with_stripe_subscription(self):
        """Test exporting users with active Stripe subscriptions"""
        now = timezone.now().date()

        # Create Stripe subscription for user1
        self._create_stripe_subscription(self.user1)

        # Export
        output_file = "test_export_stripe.csv"
        try:
            call_command("export_voter_list", now.isoformat(), output=output_file)

            # Verify CSV
            rows = self._read_csv(output_file)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["email"], "member1@example.com")
        finally:
            if os.path.exists(output_file):
                os.remove(output_file)

    def test_export_user_without_district(self):
        """Test exporting user without district uses d0"""
        now = timezone.now().date()

        # Create membership for user3 (no location/district)
        Membership.objects.create(
            user=self.user3,
            kind=Membership.Kind.FISCAL,
            start_date=now - datetime.timedelta(days=30),
            end_date=None,
        )

        # Export
        output_file = "test_export_no_district.csv"
        try:
            call_command("export_voter_list", now.isoformat(), output=output_file)

            # Verify CSV
            rows = self._read_csv(output_file)
            self.assertEqual(len(rows), 1)
            # Verify unique_id format: d0-{UUID}
            self.assertTrue(rows[0]["unique_id"].startswith("d0-"))
            uuid.UUID(rows[0]["unique_id"].split("-", 1)[1])  # Verify UUID part
        finally:
            if os.path.exists(output_file):
                os.remove(output_file)

    def test_export_user_with_zip_code_only(self):
        """Test inferring district from zip code when no location is set"""
        now = timezone.now().date()

        # Create a ZipCode that overlaps with District 5
        ZipCode.objects.create(
            name="19103",
            mpoly=MultiPolygon(
                Polygon(
                    (
                        (-75.1, 39.9),
                        (-75.1, 40.0),
                        (-75.05, 40.0),
                        (-75.05, 39.9),
                        (-75.1, 39.9),
                    )
                )
            ),
            properties={},
        )

        # Create a new user with only zip code (no location)
        user_zip_only = User.objects.create_user(
            username="ziponly",
            email="ziponly@example.com",
            password="testpass",
            first_name="David",
            last_name="Lee",
        )
        Profile.objects.create(user=user_zip_only, zip_code="19103")
        # Do NOT set location - we want to test zip code inference

        # Create membership
        Membership.objects.create(
            user=user_zip_only,
            kind=Membership.Kind.FISCAL,
            start_date=now - datetime.timedelta(days=30),
            end_date=None,
        )

        # Export
        output_file = "test_export_zip_inference.csv"
        try:
            call_command("export_voter_list", now.isoformat(), output=output_file)

            # Verify CSV - should infer District 5 from zip code
            rows = self._read_csv(output_file)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["email"], "ziponly@example.com")
            # Should have inferred district 5 from zip code 19103
            self.assertTrue(rows[0]["unique_id"].startswith("d5-"))
            uuid.UUID(rows[0]["unique_id"].split("-", 1)[1])  # Verify UUID part
        finally:
            if os.path.exists(output_file):
                os.remove(output_file)

    def test_export_user_with_zip_code_no_match(self):
        """Test user with zip code that doesn't match any district uses d0"""
        now = timezone.now().date()

        # Create a new user with zip code that doesn't exist in database
        user_unknown_zip = User.objects.create_user(
            username="unknownzip",
            email="unknownzip@example.com",
            password="testpass",
            first_name="Eve",
            last_name="Chen",
        )
        Profile.objects.create(user=user_unknown_zip, zip_code="99999")  # Non-existent zip

        # Create membership
        Membership.objects.create(
            user=user_unknown_zip,
            kind=Membership.Kind.FISCAL,
            start_date=now - datetime.timedelta(days=30),
            end_date=None,
        )

        # Export
        output_file = "test_export_unknown_zip.csv"
        try:
            call_command("export_voter_list", now.isoformat(), output=output_file)

            # Verify CSV - should use d0 since zip doesn't exist
            rows = self._read_csv(output_file)
            self.assertEqual(len(rows), 1)
            # Should use d0 prefix with UUID
            self.assertTrue(rows[0]["unique_id"].startswith("d0-"))
            uuid.UUID(rows[0]["unique_id"].split("-", 1)[1])  # Verify UUID part
        finally:
            if os.path.exists(output_file):
                os.remove(output_file)

    def test_export_multiple_members(self):
        """Test exporting multiple members with different membership types"""
        now = timezone.now().date()

        # User1: Explicit membership
        Membership.objects.create(
            user=self.user1,
            kind=Membership.Kind.FISCAL,
            start_date=now - datetime.timedelta(days=30),
            end_date=None,
        )

        # User2: Discord activity
        self._create_discord_activity(self.user2, days_ago=5)

        # User3: Stripe subscription
        self._create_stripe_subscription(self.user3)

        # Export
        output_file = "test_export_multiple.csv"
        try:
            call_command("export_voter_list", now.isoformat(), output=output_file)

            # Verify CSV
            rows = self._read_csv(output_file)
            self.assertEqual(len(rows), 3)

            emails = {row["email"] for row in rows}
            self.assertEqual(
                emails,
                {"member1@example.com", "member2@example.com", "member3@example.com"},
            )
        finally:
            if os.path.exists(output_file):
                os.remove(output_file)

    def test_export_date_filtering(self):
        """Test that date filtering works correctly"""
        now = timezone.now().date()

        # Create membership that expires before target date
        Membership.objects.create(
            user=self.user1,
            kind=Membership.Kind.FISCAL,
            start_date=now - datetime.timedelta(days=100),
            end_date=now - datetime.timedelta(days=10),  # Expired 10 days ago
        )

        # Create membership that's active on target date
        Membership.objects.create(
            user=self.user2,
            kind=Membership.Kind.FISCAL,
            start_date=now - datetime.timedelta(days=30),
            end_date=now + datetime.timedelta(days=30),
        )

        # Export
        output_file = "test_export_date_filter.csv"
        try:
            call_command("export_voter_list", now.isoformat(), output=output_file)

            # Verify only user2 is exported
            rows = self._read_csv(output_file)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["email"], "member2@example.com")
        finally:
            if os.path.exists(output_file):
                os.remove(output_file)

    def test_export_kind_filter_fiscal(self):
        """Test filtering by fiscal membership kind"""
        now = timezone.now().date()

        # Create fiscal membership
        Membership.objects.create(
            user=self.user1,
            kind=Membership.Kind.FISCAL,
            start_date=now - datetime.timedelta(days=30),
            end_date=None,
        )

        # Create participation membership
        Membership.objects.create(
            user=self.user2,
            kind=Membership.Kind.PARTICIPATION,
            start_date=now - datetime.timedelta(days=30),
            end_date=None,
        )

        # Export with fiscal filter
        output_file = "test_export_fiscal.csv"
        try:
            call_command("export_voter_list", now.isoformat(), output=output_file, kind="fiscal")

            # Verify only fiscal member is exported
            rows = self._read_csv(output_file)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["email"], "member1@example.com")
        finally:
            if os.path.exists(output_file):
                os.remove(output_file)

    def test_export_kind_filter_participation(self):
        """Test filtering by participation membership kind"""
        now = timezone.now().date()

        # Create fiscal membership
        Membership.objects.create(
            user=self.user1,
            kind=Membership.Kind.FISCAL,
            start_date=now - datetime.timedelta(days=30),
            end_date=None,
        )

        # Create participation membership
        Membership.objects.create(
            user=self.user2,
            kind=Membership.Kind.PARTICIPATION,
            start_date=now - datetime.timedelta(days=30),
            end_date=None,
        )

        # Export with participation filter
        output_file = "test_export_participation.csv"
        try:
            call_command(
                "export_voter_list",
                now.isoformat(),
                output=output_file,
                kind="participation",
            )

            # Verify only participation member is exported
            rows = self._read_csv(output_file)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["email"], "member2@example.com")
        finally:
            if os.path.exists(output_file):
                os.remove(output_file)

    def test_export_kind_filter_does_not_affect_discord_stripe(self):
        """Test that kind filter doesn't exclude Discord/Stripe members"""
        now = timezone.now().date()

        # Create fiscal membership for user1
        Membership.objects.create(
            user=self.user1,
            kind=Membership.Kind.FISCAL,
            start_date=now - datetime.timedelta(days=30),
            end_date=None,
        )

        # Create Discord activity for user2 (no explicit membership)
        self._create_discord_activity(self.user2, days_ago=5)

        # Export with participation filter
        output_file = "test_export_kind_discord.csv"
        try:
            call_command(
                "export_voter_list",
                now.isoformat(),
                output=output_file,
                kind="participation",
            )

            # Verify Discord member is still exported (kind filter doesn't apply)
            rows = self._read_csv(output_file)
            emails = {row["email"] for row in rows}
            self.assertIn("member2@example.com", emails)
            # Fiscal member should NOT be exported
            self.assertNotIn("member1@example.com", emails)
        finally:
            if os.path.exists(output_file):
                os.remove(output_file)

    def test_csv_format(self):
        """Test CSV output has correct format and headers"""
        now = timezone.now().date()

        # Create a member
        Membership.objects.create(
            user=self.user1,
            kind=Membership.Kind.FISCAL,
            start_date=now - datetime.timedelta(days=30),
            end_date=None,
        )

        # Export
        output_file = "test_export_format.csv"
        try:
            call_command("export_voter_list", now.isoformat(), output=output_file)

            # Read CSV
            with open(output_file, "r") as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames
                rows = list(reader)

            # Verify headers
            self.assertEqual(headers, ["password", "unique_id", "email", "full_name"])

            # Verify data format
            row = rows[0]
            # Password should be literal "password,"
            self.assertEqual(row["password"], "password,")
            # unique_id should match pattern dN-{UUID}
            self.assertTrue(row["unique_id"].startswith("d"))
            self.assertIn("-", row["unique_id"])
            # Verify UUID part is valid
            uuid_part = row["unique_id"].split("-", 1)[1]
            uuid.UUID(uuid_part)
            # email should be valid
            self.assertIn("@", row["email"])
        finally:
            if os.path.exists(output_file):
                os.remove(output_file)

    def test_unique_id_uniqueness(self):
        """Test that each member gets a unique unique_id"""
        now = timezone.now().date()

        # Create multiple members
        Membership.objects.create(
            user=self.user1,
            kind=Membership.Kind.FISCAL,
            start_date=now - datetime.timedelta(days=30),
            end_date=None,
        )
        Membership.objects.create(
            user=self.user2,
            kind=Membership.Kind.FISCAL,
            start_date=now - datetime.timedelta(days=30),
            end_date=None,
        )

        # Export
        output_file = "test_export_unique_ids.csv"
        try:
            call_command("export_voter_list", now.isoformat(), output=output_file)

            rows = self._read_csv(output_file)
            unique_ids = [row["unique_id"] for row in rows]
            passwords = [row["password"] for row in rows]

            # All unique_ids should be unique
            self.assertEqual(len(unique_ids), len(set(unique_ids)))

            # All passwords should be "password,"
            for password in passwords:
                self.assertEqual(password, "password,")

            # All unique_ids should contain valid UUIDs
            for unique_id in unique_ids:
                uuid_part = unique_id.split("-", 1)[1]
                uuid.UUID(uuid_part)
        finally:
            if os.path.exists(output_file):
                os.remove(output_file)

    def test_discord_activity_30_day_window(self):
        """Test that Discord activity respects 30-day window"""
        now = timezone.now().date()

        # Create Discord activity 29 days ago (within window)
        self._create_discord_activity(self.user1, days_ago=29)

        # Create Discord activity 31 days ago (outside window)
        self._create_discord_activity(self.user2, days_ago=31)

        # Export
        output_file = "test_export_discord_window.csv"
        try:
            call_command("export_voter_list", now.isoformat(), output=output_file)

            rows = self._read_csv(output_file)
            emails = [row["email"] for row in rows]

            # Only user1 should be exported
            self.assertIn("member1@example.com", emails)
            self.assertNotIn("member2@example.com", emails)
        finally:
            if os.path.exists(output_file):
                os.remove(output_file)

    def test_no_duplicate_users(self):
        """Test that users with multiple membership criteria aren't duplicated"""
        now = timezone.now().date()

        # Give user1 multiple membership criteria
        Membership.objects.create(
            user=self.user1,
            kind=Membership.Kind.FISCAL,
            start_date=now - datetime.timedelta(days=30),
            end_date=None,
        )
        self._create_discord_activity(self.user1, days_ago=5)
        self._create_stripe_subscription(self.user1)

        # Export
        output_file = "test_export_no_dupes.csv"
        try:
            call_command("export_voter_list", now.isoformat(), output=output_file)

            rows = self._read_csv(output_file)
            emails = [row["email"] for row in rows]

            # Should only have one entry for user1
            self.assertEqual(emails.count("member1@example.com"), 1)
        finally:
            if os.path.exists(output_file):
                os.remove(output_file)

    def test_invalid_date_format(self):
        """Test that invalid date format raises error"""
        output_file = "test_export_invalid_date.csv"
        try:
            out = StringIO()
            err = StringIO()
            call_command(
                "export_voter_list",
                "invalid-date",
                output=output_file,
                stdout=out,
                stderr=err,
            )

            # Should have error message
            self.assertIn("Invalid", err.getvalue())
        finally:
            if os.path.exists(output_file):
                os.remove(output_file)

    def test_default_output_filename(self):
        """Test that default output filename is voter_list.csv"""
        now = timezone.now().date()

        Membership.objects.create(
            user=self.user1,
            kind=Membership.Kind.FISCAL,
            start_date=now - datetime.timedelta(days=30),
            end_date=None,
        )

        try:
            call_command("export_voter_list", now.isoformat())

            # Should create voter_list.csv
            self.assertTrue(os.path.exists("voter_list.csv"))
        finally:
            if os.path.exists("voter_list.csv"):
                os.remove("voter_list.csv")
