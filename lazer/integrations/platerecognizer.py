import httpx
from django.conf import settings


async def read_plate(image, utc_time):
    url = "https://api.platerecognizer.com/v1/plate-reader/"
    headers = {"Authorization": f"Token {settings.PLATERECOGNIZER_API_KEY}"}

    data = {
        "upload": image,
        "regions": ["us-pa", "us-nj", "us-ny"],
        "timestamp": utc_time.isoformat(),
        "mmc": True,
        "config": {"detection_mode": "vehicle"},
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=data)
        return response.json()
