import base64
import logging
import mimetypes
import os
import urllib.parse
from pprint import pprint as pp

import interactions
import requests
from django.conf import settings
from django.utils import timezone


def submit_violation_report_to_ppa(violation_report):
    """Submit a violation report to PPA via Power Automate API."""
    violation_report.screenshot_error.delete()

    # Build the API URL
    domain = settings.PPA_API_DOMAIN
    workflow = settings.PPA_API_WORKFLOW
    sig = settings.PPA_API_SIG

    if not all([domain, workflow, sig]):
        raise ValueError(
            "PPA API settings (PPA_API_DOMAIN, PPA_API_WORKFLOW, PPA_API_SIG) must be configured"
        )

    url = (
        f"https://{domain}:443/powerautomate/automations/direct/workflows/{workflow}"
        f"/triggers/manual/paths/invoke?api-version=1"
        f"&sp={urllib.parse.quote('/triggers/manual/run')}&sv=1.0&sig={sig}"
    )

    # Prepare the photo attachment
    image = violation_report.submission.image
    image.seek(0)
    image_content = base64.b64encode(image.read()).decode("utf-8")
    image_name = os.path.basename(image.name)
    content_type = mimetypes.guess_type(image_name)[0] or "image/jpeg"

    # Build the payload
    payload = {
        "dateObserved": violation_report.date_observed,
        "timeObserved": violation_report.time_observed,
        "make": violation_report.make,
        "model": violation_report.model,
        "bodyStyle": violation_report.body_style,
        "vehicleColor": violation_report.vehicle_color,
        "violationObserved": violation_report.violation_observed,
        "frequency": violation_report.occurrence_frequency,
        "blockNumber": violation_report.block_number,
        "streetName": violation_report.street_name,
        "zipCode": violation_report.zip_code,
        "citizenNotes": violation_report.additional_information or "",
        "attachments": [
            {
                "fileName": image_name,
                "fileContent": image_content,
                "contentType": content_type,
            }
        ],
    }

    headers = {
        "Content-Type": "application/json",
    }

    logging.info(
        f"Submitting violation report to PPA API (attachment size: {len(image_content)} bytes)"
    )

    if settings.DEBUG:
        logging.info("DEBUG mode: skipping actual API submission")
        debug_payload = payload.copy()
        debug_payload["attachments"] = [
            {**a, "fileContent": a["fileContent"][:30] + "..."} for a in payload["attachments"]
        ]
        pp(debug_payload)
        return

    response = requests.post(url, json=payload, headers=headers, timeout=60)
    response.raise_for_status()

    # Extract service_id from response
    response_data = response.json()
    service_id = response_data.get("itemId")

    violation_report.submitted = timezone.now()
    violation_report.service_id = service_id
    violation_report.submission_response = response_data
    violation_report.save()


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
