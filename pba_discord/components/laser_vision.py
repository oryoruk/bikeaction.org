import re

from django.conf import settings
from interactions import Extension, component_callback
from redis.asyncio import Redis
from redis_lock.asyncio import RedisLock
from redis_lock.exceptions import AcquireFailedError

from lazer.models import ViolationReport
from lazer.tasks import submit_violation_report_to_ppa
from lazer.utils import build_embed


class LaserVision(Extension):
    def __init__(self, bot):
        self._redis = Redis.from_url(settings._REDIS_URL)
        self.bot = bot

    APPROVE_BUTTON_ID_REGEX = re.compile(r"laser_violation_approve_(.*)")

    @component_callback(APPROVE_BUTTON_ID_REGEX)
    async def approve_callback(self, ctx):
        violation_id = ctx.custom_id.replace("laser_violation_approve_", "")
        try:
            async with RedisLock(
                self._redis, name=f"laser-violation-report-{violation_id}", blocking_timeout=1.0
            ):
                violation_report = (
                    await ViolationReport.objects.filter(id=violation_id)
                    .select_related("submission")
                    .afirst()
                )
                if violation_report is None:
                    await ctx.send("No violation report found!", ephemeral=True)
                    await ctx.edit_origin(components=[])
                    return

                if violation_report.submitted is not None:
                    await ctx.send("Violation report already submitted!", ephemeral=True)
                    await ctx.edit_origin(components=[])
                    return

                submit_violation_report_to_ppa.delay(violation_report.id)

                embed = build_embed(violation_report)
                embed.description = f"**VIOLATION REPORT APPROVED by {ctx.member}**"
                await ctx.edit_origin(embeds=[embed], components=[])
                await ctx.send("Violation report approved and submitted!", ephemeral=True)
        except AcquireFailedError:
            await ctx.send("Another user has already responded", ephemeral=True)

    REJECT_BUTTON_ID_REGEX = re.compile(r"laser_violation_reject_(.*)")

    @component_callback(REJECT_BUTTON_ID_REGEX)
    async def reject_callback(self, ctx):
        violation_id = ctx.custom_id.replace("laser_violation_reject_", "")
        try:
            async with RedisLock(
                self._redis, name=f"laser-violation-report-{violation_id}", blocking_timeout=1.0
            ):
                violation_report = (
                    await ViolationReport.objects.filter(id=violation_id)
                    .select_related("submission")
                    .afirst()
                )
                if violation_report is None:
                    await ctx.send("No violation report found!", ephemeral=True)
                    await ctx.edit_origin(components=[])
                    return

                if violation_report.submitted is not None:
                    await ctx.send("Violation report already submitted!", ephemeral=True)
                    await ctx.edit_origin(components=[])
                    return

                embed = build_embed(violation_report)
                embed.description = f"**VIOLATION REPORT REJECTED by {ctx.member}**"
                await ctx.edit_origin(embeds=[embed], components=[])
                await ctx.send("Violation report rejected!", ephemeral=True)
                return
        except AcquireFailedError:
            await ctx.send("Another user has already responded", ephemeral=True)
            return


def setup(bot):
    LaserVision(bot)
