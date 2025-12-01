import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Optional

import pyap
import pytz
from django.conf import settings
from django.core.files.base import ContentFile
from django.db.models.fields.files import ImageFieldFile
from django.utils import timezone
from playwright.async_api import FilePayload
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright, expect
from playwright_stealth import stealth_async

from lazer.models import ViolationReport, ViolationSubmission

PPA_SMARTSHEET_URL = os.getenv(
    "PPA_SMARTSHEET_URL",
    "https://ppa-forms-neu.powerappsportals.com/Mobility-Access-Request/",
)
SUBMIT_SMARTSHEET_URL = os.getenv(
    "SUBMIT_SMARTSHEET_URL",
    "https://ppa-forms-neu.powerappsportals.com/Mobility-Access-Request/",
)


class FinderEnum(StrEnum):
    """Base class for enums that can find the closest match based on a string."""

    @classmethod
    def unknown_value(cls) -> Any:
        raise NotImplementedError(f"{cls.__name__} must implement the unknown_value method.")

    @classmethod
    def get_legacy_mappings(cls) -> dict[str, str]:
        """Return legacy mappings for this enum. Override in subclasses if needed."""
        return {}

    @classmethod
    def find_closest(cls, value: str) -> "FinderEnum":
        """Finds the closest enum member based on the provided value string.

        First checks legacy mappings for exact matches (case-insensitive),
        then tries substring matching against current enum values.
        """
        value_lower = value.lower()

        # Check legacy mappings first (for backlog reports from old Smartsheet form)
        legacy_mappings = cls.get_legacy_mappings()
        if legacy_mappings:
            for legacy_key, new_value in legacy_mappings.items():
                if legacy_key.lower() == value_lower:
                    logging.info(
                        f"Mapping legacy value '{value}' to '{new_value}' " f"for {cls.__name__}"
                    )
                    # Find and return the enum member with this value
                    for member in cls:
                        if member.value == new_value:
                            return member

        # Fall back to substring matching
        for member in cls:
            if value_lower in member.value.lower():
                return member

        return cls.unknown_value()


class ViolationObserved(FinderEnum):
    BIKE_LANE = "Bike Lane (vehicle parked in bike lane)"
    CORNER_CLEARANCE = "Corner Clearance (vehicle parked on corner)"
    CROSSWALK = "Crosswalk (vehicle on crosswalk)"
    HANDICAP_RAMP = "Handicap Ramp (vehicle blocking handicap ramp)"
    SIDEWALK = "Sidewalk"

    @classmethod
    def unknown_value(cls) -> "ViolationObserved":
        """Returns a default value for unknown violations."""
        return cls.BIKE_LANE


class OccurrenceFrequency(FinderEnum):
    NOT_FREQUENTLY = "Not Frequently"
    SOMEWHAT_OFTEN = "Somewhat Often"
    FREQUENTLY = "Frequently"
    UNSURE = "Unsure"

    @classmethod
    def unknown_value(cls) -> "OccurrenceFrequency":
        """Returns a default value for unknown violations."""
        return cls.UNSURE


class VehicleType(FinderEnum):
    COUPE = "Coupe (2 door car)"
    SEDAN = "Sedan (4 door car)"
    SUV = "SUV"
    MINIVAN = "Minivan"
    VAN = "Van"
    PICKUP_TRUCK = "Pickup Truck"
    BOX_TRUCK = "Box-Truck"
    BUS = "Bus"
    BOAT = "Boat"
    RV = "RV"
    MOTORCYCLE = "Motorcycle"
    ATV = "ATV"
    TRACTOR = "Tractor"
    TRAILER = "Trailer"
    CAMPER = "Camper"
    CONSTRUCTION_EQUIPMENT = "Construction Equipment"
    FLATBED = "Flatbed"
    TOW_TRUCK = "Tow-Truck"
    UNKNOWN = "Unknown"

    @classmethod
    def get_legacy_mappings(cls) -> dict[str, str]:
        """Legacy mappings from old Smartsheet form to new PowerApps form."""
        return {
            "Dirt Bike": "Motorcycle",  # Old form had "Dirt Bike", map to closest equivalent
        }

    @classmethod
    def unknown_value(cls) -> "VehicleType":
        """Returns a default value for unknown violations."""
        return cls.UNKNOWN


class VehicleColor(FinderEnum):
    BEIGE = "Beige"
    BLACK = "Black"
    BLUE = "Blue"
    BROWN = "Brown"
    GOLD = "Gold"
    GRAY = "Gray"
    GREEN = "Green"
    MAROON = "Maroon"
    OTHER = "Other"
    PINK = "Pink"
    PURPLE = "Purple"
    RED = "Red"
    SILVER = "Silver"
    TEAL = "Teal"
    WHITE = "White"

    @classmethod
    def get_legacy_mappings(cls) -> dict[str, str]:
        """Legacy mappings from old Smartsheet form to new PowerApps form."""
        return {
            "Yellow": "Gold",  # Closest color match
            "Orange": "Red",  # Map to closest available color
            "Magenta": "Pink",  # Magenta is similar to pink
            "Violet": "Purple",  # Violet is a shade of purple
            "Cyan": "Teal",  # Cyan and teal are in the same color family
        }

    @classmethod
    def unknown_value(cls) -> "VehicleColor":
        """Returns a default value for unknown vehicle colors."""
        return cls.OTHER


@dataclass
class MobilityAccessViolation:

    make: str
    body_style: VehicleType | str
    vehicle_color: VehicleColor | str

    violation_observed: ViolationObserved | str

    _date_observed: Optional[str]
    _time_observed: Optional[str]
    _block_number: Optional[str]
    _street_name: Optional[str]
    _zip_code: Optional[str]

    # Parsable fields, optionally provided instead of strings
    parsed_address: Optional[pyap.Address] = field(init=False)
    address: Optional[str]
    date_time_observed: Optional[datetime]

    # optional fields
    occurrence_frequency: OccurrenceFrequency = OccurrenceFrequency.UNSURE
    model: str = ""
    # this field is good to report license plate, since
    # there's no field for it in the form.
    additional_information: str = ""

    def __post_init__(self):
        """Post-initialization to parse the address."""
        if not all([self._block_number, self._street_name, self._zip_code]) or self.address:
            raise ValueError("Must supply all address parts or an address to parse")
        self.parsed_address = None
        if self.address:
            parsed_addresses = pyap.parse(self.address, country="US")
            if (
                len(parsed_addresses) != 1
                or parsed_addresses[0].street_name is None
                or parsed_addresses[0].street_type is None
                or parsed_addresses[0].postal_code is None
            ):
                raise ValueError(f"address could not be parsed: {self.address}")
            self.parsed_address = parsed_addresses[0]

        if not all([self._date_observed, self._time_observed]) or self.date_time_observed:
            raise ValueError("Must supply all date/time observed parts or a datetime to parse")
        if self.date_time_observed:
            # convert to est
            est = pytz.timezone("US/Eastern")
            self.date_time_observed = self.date_time_observed.astimezone(est)

        # ensure all enum fields are of the correct type
        fields: list[str, FinderEnum] = [
            ("body_style", VehicleType),
            ("vehicle_color", VehicleColor),
            ("violation_observed", ViolationObserved),
            ("occurrence_frequency", OccurrenceFrequency),
        ]

        for field_name, field_type in fields:
            field_value = getattr(self, field_name)
            if not isinstance(field_value, field_type):
                closest_value = field_type.find_closest(field_value)
                setattr(self, field_name, closest_value)

    # street name here is a dropdown, not a free form.
    # block_number: int
    # street_name: str
    # example address: Wharton Square Park, 2300 Wharton St, Philadelphia, PA 19146, USA
    @property
    def block_number(self) -> int:
        """Returns the block number from the address."""
        if self._block_number:
            return self._block_number
        return self.parsed_address.street_number  # type: ignore

    @property
    def street_name(self) -> str:
        """Returns the street name from the address."""
        if self._street_name:
            return self._street_name
        return (
            self.parsed_address.street_name.upper()  # type: ignore
            + " "
            + self.parsed_address.street_type.upper()  # type: ignore
        )

    @property
    def zip_code(self) -> str:
        """Returns the zip code from the address."""
        if self._zip_code:
            return self._zip_code
        return self.parsed_address.postal_code  # type: ignore

    @property
    def date_observed(self) -> str:
        """Returns the date part of the observed datetime."""
        if self._date_observed:
            return self._date_observed
        return self.date_time_observed.strftime("%m/%d/%Y")

    @property
    def time_observed(self) -> str:
        """Returns the time part of the observed datetime."""
        if self._time_observed:
            return self._time_observed
        # Return the time in EST (should this be 24 hour format?)
        return self.date_time_observed.strftime("%I:%M %p")

    @classmethod
    def from_json(cls, data: dict) -> "MobilityAccessViolation":
        """Creates a MobilityAccessViolation instance from a JSON-like dictionary."""
        vehicle = data.get("vehicle", {})
        if not vehicle:
            # see if there is an array
            vehicles = data.get("vehicles", [])
            if vehicles:
                vehicle = vehicles[0]
            else:
                raise ValueError("Vehicle data is required to create a MobilityAccessViolation.")
        if "timestamp" not in data or "address" not in data:
            raise ValueError("Timestamp and address are required fields.")
        plate = vehicle.get("plate", {}).get("props", {}).get("plate", {})[0].get("value", "")
        region = vehicle.get("plate", {}).get("props", {}).get("region", {})[0].get("value", "")
        # override to make it easier
        vehicle = vehicle.get("vehicle", {})

        vehicle_type = vehicle.get("type", "")
        body_style = VehicleType.find_closest(vehicle_type)

        props = vehicle.get("props")

        make_model = props.get("make_model", {})[0]
        make = make_model.get("make", "")
        model = make_model.get("model", "")
        color = props.get("color", "")[0].get("value", "")
        vehicle_color = VehicleColor.find_closest(color)

        return cls(
            date_time_observed=datetime.fromisoformat(data["timestamp"]),
            make=make,
            model=model,
            body_style=body_style,
            vehicle_color=vehicle_color,
            additional_information=f"License Plate: {plate} ({region})",
            # not sure which one to select here...
            violation_observed=ViolationObserved.BIKE_LANE,  # type: ignore
            address=data["address"],
            # picture=data.get("picture", ""),
        )


async def submit_form_with_playwright(
    submission: ViolationSubmission,
    violation: MobilityAccessViolation,
    photo: str | ImageFieldFile | ContentFile,
    send_copy_to_email: str | None = None,
    tracing: bool = False,
    screenshot_dir: str | None = None,
    violation_report: ViolationReport | None = None,
) -> ViolationReport:
    """Method to submit a violation to the PPA's Smartsheet using Playwright.

    Args:
        violation (MobilityAccessViolation): The description of the violation to submit.
    """
    # smartsheet allows pre-filling of fields using query parameters.
    # for example, date observed would be Date%20Observed=06/03/2025

    if violation_report is None:
        violation_report = ViolationReport(
            submission=submission,
            date_observed=violation.date_observed,
            time_observed=violation.time_observed,
            make=violation.make,
            model=violation.model,
            body_style=violation.body_style,
            vehicle_color=violation.vehicle_color,
            violation_observed=violation.violation_observed,
            occurrence_frequency=violation.occurrence_frequency,
            block_number=violation.block_number,
            street_name=violation.street_name,
            zip_code=violation.zip_code,
            additional_information=violation.additional_information,
        )

    if isinstance(photo, str):
        if not os.path.exists(photo):
            raise FileNotFoundError(f"Photo file not found: {photo}")
        with open(photo, "rb") as f:
            photo = ContentFile(f.read(), name=os.path.basename(photo))
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=not tracing)
        context = await browser.new_context(viewport={"width": 1024, "height": 3000})

        if tracing:
            tracing_debug_key = os.urandom(3).hex()
            await context.tracing.start(screenshots=True, snapshots=True, sources=True)

        page = await context.new_page()
        await stealth_async(page)

        # Navigate to the form
        # Note: PowerApps forms do not support query parameter pre-filling like Smartsheet did
        # All fields must be filled manually via Playwright (see below)
        await page.goto(PPA_SMARTSHEET_URL)
        # wait for the form to load
        await page.wait_for_load_state("networkidle")

        # Fill in all form fields manually using label-based selectors
        # This is more stable than using IDs which may change if the form is recreated

        # Date field - uses datetimepicker widget that's initialized by JavaScript
        date_input = page.get_by_label("Date Observed (Citizen)")

        # Try multiple approaches to fill the date field
        date_filled = False

        # Approach 1: Click, clear, and type the value (simulates user typing)
        try:
            await date_input.click()
            await page.wait_for_timeout(300)
            await date_input.clear()
            await date_input.press_sequentially(violation.date_observed, delay=50)
            await date_input.press("Tab")  # Tab out to trigger validation
            await page.wait_for_timeout(200)
            date_filled = True
        except Exception as e:
            logging.warning(f"Approach 1 (type) failed for date field: {e}")

        # Approach 2: Use JavaScript if typing failed
        if not date_filled:
            try:
                logging.info("Trying JavaScript approach for date field")
                await page.evaluate(
                    """
                    (dateValue) => {
                        // Find the input by data-ui attribute
                        const input = document.querySelector('[data-ui="datetimepicker"]');
                        if (input) {
                            input.value = dateValue;
                            input.dispatchEvent(new Event('input', { bubbles: true }));
                            input.dispatchEvent(new Event('change', { bubbles: true }));
                            input.dispatchEvent(new Event('blur', { bubbles: true }));
                            // Also trigger jQuery events if they exist
                            if (window.jQuery) {
                                jQuery(input).trigger('change');
                            }
                        }
                    }
                    """,
                    violation.date_observed,
                )
                date_filled = True
            except Exception as e:
                logging.error(f"All approaches failed for date field: {e}")

        # Time field
        await page.get_by_label("Time Observed (Citizen)").fill(violation.time_observed)

        # Make (dropdown)
        await page.get_by_label("Make").select_option(label=violation.make)

        # Model (text input)
        if violation.model:
            await page.get_by_label("Model").fill(violation.model)

        # Body Style (dropdown)
        await page.get_by_label("Body Style").select_option(label=str(violation.body_style.value))

        # Vehicle Color (dropdown)
        await page.get_by_label("Vehicle Color").select_option(
            label=str(violation.vehicle_color.value)
        )

        # Violation Observed (dropdown)
        await page.get_by_label("Violation Observed").select_option(
            label=str(violation.violation_observed.value)
        )

        # Block Number (text input)
        await page.get_by_label("Block Number").fill(str(violation.block_number))

        # Street Name (text input)
        await page.get_by_label("Street Name").fill(violation.street_name)

        # Zip Code (text input)
        await page.get_by_label("Zip Code").fill(violation.zip_code)

        # How frequently does this occur? (dropdown)
        await page.get_by_label("How frequently does this occur?", exact=True).select_option(
            label=str(violation.occurrence_frequency.value)
        )

        # Additional Information / Citizen's Notes (textarea)
        if violation.additional_information:
            # Try multiple label variations in case the label text changes slightly
            try:
                await page.get_by_label("Citizen's Notes").fill(violation.additional_information)
            except Exception:
                # Fallback to other possible label text
                await page.get_by_label("Additional Information", exact=False).fill(
                    violation.additional_information
                )

        # Wait a moment to ensure all JavaScript validation and field updates complete
        await page.wait_for_timeout(500)

        # Click the file upload button - find by text instead of fragile ID
        async with page.expect_file_chooser() as fc_info:
            await page.get_by_role("button", name="Upload").click()
        file_chooser = await fc_info.value
        if isinstance(photo, str):
            await file_chooser.set_files(photo)
        elif isinstance(photo, ContentFile) or isinstance(photo, ImageFieldFile):
            upload = FilePayload(
                name=getattr(photo, "name", "violation_photo.jpg"),
                mimeType="image/jpeg",
                buffer=photo.read(),  # limit how much we read?
            )

            await file_chooser.set_files(upload)

        # submit the form
        try:
            if screenshot_dir:
                await page.screenshot(
                    path=f"{screenshot_dir}/screenshot-before-submit.png", full_page=True
                )
                with open(f"{screenshot_dir}/screenshot-before-submit.png", "rb") as f:
                    violation_report.screenshot_before_submit.save(
                        "screenshot-before-submit.png", f, save=False
                    )
                    await violation_report.asave()

            if not settings.DEBUG:
                async with page.expect_request(
                    lambda request: request.url == SUBMIT_SMARTSHEET_URL
                    and request.method.lower() == "post"
                ) as _:
                    # Click submit button by value instead of fragile ID
                    await page.get_by_role("button", name="Submit").click()

            if screenshot_dir:
                await page.screenshot(
                    path=f"{screenshot_dir}/screenshot-after-submit.png", full_page=True
                )
                with open(f"{screenshot_dir}/screenshot-after-submit.png", "rb") as f:
                    violation_report.screenshot_after_submit.save(
                        "screenshot-after-submit.png", f, save=False
                    )
                    await violation_report.asave()

            # make sure there is a POST to the form URL and it returned 200
            # also, the submission page should have an h1 element with specific
            await page.wait_for_load_state("networkidle")
            if not settings.DEBUG:
                # validate the submission page
                await expect(
                    page.locator('div[data-client-id="submission-confirmation-container"]')
                ).to_be_visible(timeout=10000)

            if screenshot_dir:
                await page.screenshot(
                    path=f"{screenshot_dir}/screenshot-success.png", full_page=True
                )
                with open(f"{screenshot_dir}/screenshot-success.png", "rb") as f:
                    violation_report.screenshot_success.save(
                        "screenshot-success.png", f, save=False
                    )
                    await violation_report.asave()
            violation_report.submitted = timezone.now()

        except PlaywrightTimeoutError:
            logging.error("Playwright timed out.", exc_info=True)
            if screenshot_dir:
                await page.screenshot(
                    path=f"{screenshot_dir}/screenshot-error.png", full_page=True
                )
                with open(f"{screenshot_dir}/screenshot-error.png", "rb") as f:
                    violation_report.screenshot_error.save("screenshot-error.png", f, save=False)
                    await violation_report.asave()
            if tracing:
                await context.tracing.stop(path=f"tracing_{tracing_debug_key}.zip")
            await context.close()
            await browser.close()
            return violation_report

        if tracing:
            await context.tracing.stop(path=f"tracing_{tracing_debug_key}.zip")
        if screenshot_dir:
            await page.screenshot(path=f"{screenshot_dir}/screenshot-final.png", full_page=True)
            with open(f"{screenshot_dir}/screenshot-final.png", "rb") as f:
                violation_report.screenshot_final.save("screenshot-final.png", f, save=False)
                await violation_report.asave()
        await context.close()
        await browser.close()
        return violation_report
