from tempfile import TemporaryDirectory

import interactions
from asgiref.sync import async_to_sync
from django.conf import settings
from django.utils import timezone

from lazer.integrations.submit_form import (
    MobilityAccessViolation,
    submit_form_with_playwright,
)


def submit_violation_report_to_ppa(violation_report):
    violation_report.screenshot_error.delete()
    mobility_access_violation = MobilityAccessViolation(
        make=violation_report.make,
        model=violation_report.model,
        body_style=violation_report.body_style,
        vehicle_color=violation_report.vehicle_color,
        violation_observed=violation_report.violation_observed,
        occurrence_frequency=violation_report.occurrence_frequency,
        additional_information=violation_report.additional_information,
        date_time_observed=None,
        _date_observed=violation_report.date_observed,
        _time_observed=violation_report.time_observed,
        address=None,
        _block_number=violation_report.block_number,
        _street_name=violation_report.street_name,
        _zip_code=violation_report.zip_code,
    )
    with TemporaryDirectory() as temp_dir:
        violation = async_to_sync(submit_form_with_playwright)(
            submission=violation_report.submission,
            violation=mobility_access_violation,
            photo=violation_report.submission.image,
            screenshot_dir=temp_dir,
            violation_report=violation_report,
        )
        violation.save()


def build_embed(violation_report):
    embed = interactions.Embed(
        title="Violation report from a new user submitted!",
        description=(
            "**New reporters need to be vetted.**\n\n"
            "Review this report and click the Approve or Reject button below."
        ),
        timestamp=timezone.now(),
    )
    embed.add_field("Date Observed", violation_report.date_observed, inline=True)
    embed.add_field("Time Observed", violation_report.time_observed, inline=True)
    embed.add_field("\u200B", "\u200B", inline=True)
    embed.add_field("Make", violation_report.make, inline=True)
    embed.add_field("Model", violation_report.model, inline=True)
    embed.add_field("Body Style", violation_report.body_style, inline=True)
    embed.add_field("Vehicle Color", violation_report.vehicle_color, inline=True)
    embed.add_field("\u200B", "\u200B", inline=True)
    embed.add_field("\u200B", "\u200B", inline=True)
    embed.add_field("Block Number", violation_report.block_number, inline=True)
    embed.add_field("Street Name", violation_report.street_name, inline=True)
    embed.add_field("Zip Code", violation_report.zip_code, inline=True)
    embed.add_field("Violation", violation_report.violation_observed)
    embed.add_field("Occurrence", violation_report.occurrence_frequency)
    embed.add_field("Additional", violation_report.additional_information)

    image_url = violation_report.submission.image.url
    if not image_url.startswith("http"):
        image_url = f"{settings.SITE_URL}{image_url}"
    embed.set_thumbnail(url=image_url)
    embed.add_field("View Image", f"[here]({image_url})")

    return embed
