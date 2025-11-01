from django.core.management.base import BaseCommand

from events.models import EventSignIn
from pbaabp.integrations.mailjet import Mailjet
from profiles.models import Profile


class Command(BaseCommand):
    help = "Populate Mailjet IDs for event signins and profiles"

    def handle(self, *args, **options):
        mailjet = Mailjet()
        email_to_id = {}
        for profile in Profile.objects.all():
            if profile.mailjet_contact_id:
                email_to_id[profile.user.email] = profile.mailjet_contact_id
                continue
            print(profile.user.email)
            if mj_id := email_to_id.get(profile.user.email):
                profile.mailjet_contact_id = mj_id
                profile.save()
            else:
                response = mailjet.get_contact(profile.user.email)
                if response:
                    email_to_id[profile.user.email] = response["ID"]
                    profile.mailjet_contact_id = response["ID"]
                    profile.save()
        for signin in EventSignIn.objects.all():
            if signin.mailjet_contact_id:
                email_to_id[signin.email] = signin.mailjet_contact_id
                continue
            print(signin.email)
            if mj_id := email_to_id.get(signin.email):
                signin.mailjet_contact_id = mj_id
                signin.save()
            else:
                response = mailjet.get_contact(signin.email)
                if response:
                    email_to_id[signin.email] = response["ID"]
                    signin.mailjet_contact_id = response["ID"]
                    signin.save()
