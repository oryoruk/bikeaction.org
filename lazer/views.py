import asyncio
import base64
import datetime
import json
import secrets
from functools import wraps
from importlib import import_module

import pytz
from asgiref.sync import sync_to_async
from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.gis.geos import Point
from django.core.files.base import ContentFile
from django.core.paginator import Paginator
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.cache import cache_page
from django.views.decorators.csrf import csrf_exempt

from campaigns.admin import randomize_lat_long
from facets.utils import reverse_geocode_point
from lazer.forms import ReportForm, SubmissionForm
from lazer.integrations.platerecognizer import read_plate
from lazer.integrations.submit_form import MobilityAccessViolation
from lazer.models import ViolationReport, ViolationSubmission

SessionStore = import_module(settings.SESSION_ENGINE).SessionStore
User = get_user_model()


def get_image_from_data_url(data_url):
    _format, _dataurl = data_url.split(";base64,")
    _filename, _extension = secrets.token_hex(20), _format.split("/")[-1]

    file = ContentFile(base64.b64decode(_dataurl), name=f"{_filename}.{_extension}")

    return file, (_filename, _extension)


@sync_to_async
def get_user_from_request(request):
    return request.user if bool(request.user) else None


def api_auth(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_authenticated:
            return view_func(request, *args, **kwargs)
        if "Authorization" in request.headers and request.headers["Authorization"].startswith(
            "Session: "
        ):
            session_key = request.headers["Authorization"].split("Session: ")[1]
            session = SessionStore(session_key=session_key)
            request.session = session
            user_id = session.get("_auth_user_id")
            try:
                request.user = User.objects.get(id=user_id)
                return view_func(request, *args, **kwargs)
            except User.DoesNotExist:
                pass
        return JsonResponse({"error": "invalid auth"}, status=403)

    return _wrapped_view


def aapi_auth(view_func):
    @wraps(view_func)
    async def _wrapped_view(request, *args, **kwargs):
        _user = await request.auser()
        if _user.is_authenticated:
            return await view_func(request, *args, **kwargs)
        if "Authorization" in request.headers and request.headers["Authorization"].startswith(
            "Session: "
        ):
            session_key = request.headers["Authorization"].split("Session: ")[1]
            session = SessionStore(session_key=session_key)
            request.session = session
            user_id = await session.aget("_auth_user_id")
            try:
                request.user = await User.objects.aget(id=user_id)
                return await view_func(request, *args, **kwargs)
            except User.DoesNotExist:
                pass
        return JsonResponse({"error": "invalid auth"}, status=403)

    return _wrapped_view


@aapi_auth
@csrf_exempt
@transaction.non_atomic_requests
async def submission_api(request):
    if request.method == "POST":
        form = SubmissionForm(request.POST)
        if form.is_valid():
            image, _ = get_image_from_data_url(form.cleaned_data["image"])
            user = await get_user_from_request(request)

            submission = ViolationSubmission(
                image=image,
                location=Point(
                    float(form.cleaned_data["longitude"]), float(form.cleaned_data["latitude"])
                ),
                captured_at=form.cleaned_data["datetime"],
                created_by=user,
            )
            await submission.asave()
            await submission.arefresh_from_db()

            data, addresses = await asyncio.gather(
                read_plate(
                    form.cleaned_data["image"].split(";base64,")[1],
                    datetime.datetime.now(datetime.timezone.utc),
                ),
                reverse_geocode_point(
                    f"{form.cleaned_data['latitude']}, {form.cleaned_data['longitude']}",
                    exactly_one=False,
                ),
            )

            vehicles = data.get("results", [])
            return JsonResponse(
                {
                    "vehicles": (
                        sorted(
                            [v for v in vehicles if v.get("vehicle") is not None],
                            key=lambda x: x.get("vehicle", {}).get("score", 0),
                            reverse=True,
                        )[:4]
                    ),
                    "addresses": [address.address for address in addresses],
                    "address": addresses[0].address,
                    "timestamp": form.cleaned_data["datetime"],
                    "submissionId": submission.submission_id,
                },
                status=200,
            )
        else:
            return JsonResponse({}, status=400)


@aapi_auth
@csrf_exempt
@transaction.non_atomic_requests
async def report_api(request):
    if request.method == "POST":
        form = ReportForm(request.POST)
        if form.is_valid():
            submission = await ViolationSubmission.objects.filter(
                submission_id=form.cleaned_data["submission_id"]
            ).afirst()
            if submission is None:
                return JsonResponse(
                    {"submitted": False, "error": "Reports must have a valid submission_id"},
                    status=400,
                )

            mobility_access_violation = MobilityAccessViolation(
                make=form.cleaned_data["make"],
                model=form.cleaned_data["model"],
                body_style=form.cleaned_data["body_style"],
                vehicle_color=form.cleaned_data["vehicle_color"],
                violation_observed=form.cleaned_data["violation_observed"],
                occurrence_frequency=form.cleaned_data["occurrence_frequency"],
                additional_information=form.cleaned_data["additional_information"],
                date_time_observed=None,
                _date_observed=form.cleaned_data["date_observed"],
                _time_observed=form.cleaned_data["time_observed"],
                address=None,
                _block_number=form.cleaned_data["block_number"],
                _street_name=form.cleaned_data["street_name"],
                _zip_code=form.cleaned_data["zip_code"],
            )

            violation_report = ViolationReport(
                submission=submission,
                date_observed=mobility_access_violation.date_observed,
                time_observed=mobility_access_violation.time_observed,
                make=mobility_access_violation.make,
                model=mobility_access_violation.model,
                body_style=mobility_access_violation.body_style,
                vehicle_color=mobility_access_violation.vehicle_color,
                violation_observed=mobility_access_violation.violation_observed,
                occurrence_frequency=mobility_access_violation.occurrence_frequency,
                block_number=mobility_access_violation.block_number,
                street_name=mobility_access_violation.street_name,
                zip_code=mobility_access_violation.zip_code,
                additional_information=mobility_access_violation.additional_information,
            )

            await violation_report.asave()

            return JsonResponse(
                {
                    "submitted": True,
                },
                status=200,
            )
        else:
            return JsonResponse({"submitted": False}, status=400)


@cache_page(30)
def map_data(request):
    violation_filter = request.GET.get("violation", None)
    date_gte = request.GET.get("date_gte", None)
    date_lte = request.GET.get("date_lte", None)
    date = request.GET.get("date", None)

    pins = []
    queryset = ViolationReport.objects.filter(submitted__isnull=False).select_related("submission")
    if violation_filter:
        queryset = queryset.filter(violation_observed__startswith=violation_filter).filter(
            submission__captured_at__lt=timezone.now() - datetime.timedelta(minutes=15)
        )

    if date:
        queryset = queryset.filter(
            submission__captured_at__date=datetime.datetime.strptime(date, "%Y-%m-%d")
            .astimezone(pytz.timezone("America/New_York"))
            .date()
        )
    else:
        if date_gte:
            queryset = queryset.filter(
                submission__captured_at__gte=datetime.datetime.strptime(date_gte, "%Y-%m-%d")
                .astimezone(pytz.timezone("America/New_York"))
                .date()
            )
        if date_lte:
            queryset = queryset.filter(
                submission__captured_at__lte=datetime.datetime.strptime(date_lte, "%Y-%m-%d")
                .astimezone(pytz.timezone("America/New_York"))
                .date()
            )

    # Count unique users who submitted violations
    unique_users = set()
    for report in queryset.only("submission__location", "submission__created_by").all():
        if report.submission.created_by_id:
            unique_users.add(report.submission.created_by_id)
        lat, lng = randomize_lat_long(
            report.id, *(report.submission.location.y, report.submission.location.x)
        )
        pins.append([lat, lng, 1])

    return JsonResponse({"pins": pins, "unique_users_count": len(unique_users)}, safe=False)


def map(request):
    return render(request, "heatmap.html")


def list(request):
    queryset = (
        ViolationReport.objects.filter(submitted__isnull=False)
        .select_related("submission")
        .order_by("-submission__captured_at")
        .all()
    )
    paginator = Paginator(queryset, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    return render(request, "list.html", {"page_obj": page_obj})


@csrf_exempt
def login_api(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body.decode())
        except json.JSONDecodeError:
            return JsonResponse({"error": "invalid JSON"}, status=400)

        username = data.get("username")
        password = data.get("password")

        errors = []
        if username is None:
            errors.append("username required")
        if password is None:
            errors.append("password required")

        if errors:
            return JsonResponse({"error": ",".join(errors)}, status=400)
    else:
        return JsonResponse({"error": "POST only"}, status=400)

    user = authenticate(username=username, password=password)
    if user is not None:
        login(request, user)
        request.session.set_expiry(30 * 24 * 60 * 60)
        session_key = request.session.session_key
        expiry_date = request.session.get_expiry_date()
        return JsonResponse(
            {
                "success": "ok",
                "username": request.user.email,
                "first_name": request.user.first_name,
                "session_key": session_key,
                "expiry_date": expiry_date,
                "donor": request.user.profile.donor(),
            },
            status=200,
        )
    return JsonResponse({"error": "invalid auth"}, status=403)


@api_auth
def check_login(request):
    return JsonResponse(
        {
            "success": "ok",
            "username": request.user.email,
            "first_name": request.user.first_name,
            "donor": request.user.profile.donor(),
        },
        status=200,
    )


def logout_api(request):
    logout(request)
    return JsonResponse({"success": "ok"}, status=200)
