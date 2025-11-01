from django.contrib.auth import get_user_model
from django.db.models import F
from django.utils import timezone

from pba_discord.handlers import OnMessage

User = get_user_model()


class DiscordActivity(OnMessage):
    # defines the priority of this handler, lower numbers execute first
    # first condition to return true will have on_message called
    priority = 1

    # sets if this handler should stop all the rest from running
    terminal = False

    def __init__(self):
        pass

    async def condition(self, message):
        return True

    async def on_message(self, message):
        from profiles.models import DiscordActivity

        if (
            user := await User.objects.filter(
                socialaccount__provider="discord", socialaccount__uid=message.author.user.id
            )
            .select_related("profile")
            .aget()
        ):
            await DiscordActivity.objects.aupdate_or_create(
                profile=user.profile,
                date=timezone.now().date(),
                defaults={"count": F("count") + 1},
                create_defaults={"count": 1},
            )
