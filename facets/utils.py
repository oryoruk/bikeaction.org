import sentry_sdk
from django.conf import settings
from geopy.adapters import AioHTTPAdapter
from geopy.geocoders import GoogleV3, Nominatim

UA = "apps.bikeaction.org Geopy"


async def geocode_address(search_address):
    try:
        if settings.GOOGLE_MAPS_API_KEY is not None:
            async with GoogleV3(
                api_key=settings.GOOGLE_MAPS_API_KEY, user_agent=UA, adapter_factory=AioHTTPAdapter
            ) as geolocator:
                address = await geolocator.geocode(search_address)
        else:
            async with Nominatim(user_agent=UA, adapter_factory=AioHTTPAdapter) as geolocator:
                address = await geolocator.geocode(search_address)
        return address
    except Exception as err:
        sentry_sdk.capture_exception(err)
        raise


async def reverse_geocode_point(search_point, exactly_one=True):
    try:
        if settings.GOOGLE_MAPS_API_KEY is not None:
            async with GoogleV3(
                api_key=settings.GOOGLE_MAPS_API_KEY, user_agent=UA, adapter_factory=AioHTTPAdapter
            ) as geolocator:
                address = await geolocator.reverse(search_point, exactly_one=exactly_one)
        else:
            async with Nominatim(user_agent=UA, adapter_factory=AioHTTPAdapter) as geolocator:
                address = await geolocator.reverse(search_point, exactly_one=exactly_one)
        return address
    except Exception as err:
        sentry_sdk.capture_exception(err)
        raise
