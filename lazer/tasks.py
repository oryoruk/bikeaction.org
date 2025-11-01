import interactions
from asgiref.sync import async_to_sync
from celery import shared_task
from django.conf import settings

from lazer.models import ViolationReport
from lazer.utils import build_embed
from lazer.utils import (
    submit_violation_report_to_ppa as _submit_violation_report_to_ppa,
)
from pba_discord.bot import bot


@shared_task
def submit_violation_report_to_ppa(violation_id):
    violation_report = ViolationReport.objects.get(id=violation_id)
    _submit_violation_report_to_ppa(violation_report)


async def _submit_violation_report_discord(violation_id):
    if (
        settings.NEW_ORGANIZER_REVIEW_DISCORD_GUILD_ID is None
        or settings.NEW_LASER_VIOLATION_CHANNEL_ID is None
    ):
        return

    violation_report = await ViolationReport.objects.select_related("submission").aget(
        id=violation_id
    )
    embed = build_embed(violation_report)

    await bot.login(settings.DISCORD_BOT_TOKEN)
    guild = await bot.fetch_guild(settings.NEW_LASER_VIOLATION_GUILD_ID)
    notification_channel = await guild.fetch_channel(settings.NEW_LASER_VIOLATION_CHANNEL_ID)

    components = [
        interactions.Button(
            style=interactions.ButtonStyle.GREEN,
            label="Approve",
            custom_id=f"laser_violation_approve_{violation_report.id}",
        ),
        interactions.Button(
            style=interactions.ButtonStyle.RED,
            label="Reject",
            custom_id=f"laser_violation_reject_{violation_report.id}",
        ),
    ]

    await notification_channel.send(embed=[embed], components=components)


@shared_task
def submit_violation_report_discord(violation_id):
    async_to_sync(_submit_violation_report_discord)(violation_id)
