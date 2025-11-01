from asgiref.sync import async_to_sync, sync_to_async
from celery import shared_task
from django.conf import settings
from django.urls import reverse
from interactions.models.discord.enums import AutoArchiveDuration

from organizers.models import OrganizerApplication
from pba_discord.bot import bot


async def _add_new_organizer_message_and_thread(organizer_application_id):
    application = await OrganizerApplication.objects.filter(id=organizer_application_id).afirst()
    if application is None or application.draft or application.thread_id:
        return

    await bot.login(settings.DISCORD_BOT_TOKEN)
    guild = await bot.fetch_guild(settings.NEW_ORGANIZER_REVIEW_DISCORD_GUILD_ID)
    selection_channel = await guild.fetch_channel(settings.NEW_ORGANIZER_REVIEW_DISCORD_CHANNEL_ID)
    mention_role = await guild.fetch_role(settings.NEW_ORGANIZER_REVIEW_DISCORD_ROLE_MENTION_ID)
    submitter = await sync_to_async(lambda: application.submitter)()
    profile = await sync_to_async(lambda: submitter.profile)()
    discord = await sync_to_async(lambda: profile.discord)()
    discord_username = discord.extra_data["username"]
    thread = await selection_channel.create_thread(
        name=f"{application.submitter.first_name} {application.submitter.last_name}",
        reason=f"Organizer Application submitted by {discord_username}",
        auto_archive_duration=AutoArchiveDuration.ONE_WEEK,
    )
    if not application.markdown:
        await sync_to_async(application.render_markdown)()
    msg = ""
    in_response = False
    for line in application.markdown.split("\n"):
        if line == "```":
            if in_response:
                in_response = False
            else:
                in_response = True
        if len(msg) + len(line) >= 1990:
            if in_response:
                msg += "```\n"
            await thread.send(msg)
            msg = ""
            if in_response:
                msg += "```\n"
        msg += line + "\n"
    await thread.send(msg)
    link = reverse("organizer_application_view", kwargs={"pk": application.id})
    link = f"https://apps.bikeaction.org{link}"
    await thread.send(
        f"{mention_role.mention} please review!\n\n"
        f"You can view the application online at <{link}> after logging in.\n\n"
        "Organizers - please review and follow these instructions:\n\n"
        "1️⃣  The Nominating Organizer in this application must  "
        "reply to this thread with a reccomendationn\n\n"
        "2️⃣  At least 2 Organizers who have worked with the candidate "
        "should provide endorsement\n\n"
        "3️⃣  One Organizer must volunteer to mentor this new organizeer"
        "(tell them they were approved, explain how pba works, "
        "answer questions, etc)\n\n"
        "4️⃣  Once the above has happened, everyone can vote ✅ or ❌ "
        "(minimum 5 votes required, "
        "contentious votes should be referred to the Board)."
    )
    application.thread_id = thread.id
    await application.asave()


@shared_task
def add_new_organizer_message_and_thread(organizer_application_id):
    async_to_sync(_add_new_organizer_message_and_thread)(organizer_application_id)
