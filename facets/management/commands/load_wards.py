import json
import pathlib
from collections import defaultdict

from django.contrib.gis.geos import GEOSGeometry, MultiPolygon
from django.core.management.base import BaseCommand
from shapely import union_all
from shapely.geometry import mapping, shape

from facets.models import Ward


class Command(BaseCommand):
    help = "Load wards by merging political divisions"

    def handle(self, *args, **options):
        geojson_path = (
            pathlib.Path(__file__).parent.parent.parent / "data" / "Political_Divisions.geojson"
        )

        with open(geojson_path) as f:
            data = json.load(f)

        divisions_by_ward = defaultdict(list)
        for feature in data["features"]:
            ward_num = feature["properties"]["DIVISION_NUM"][:2]
            divisions_by_ward[ward_num].append(shape(feature["geometry"]))

        for ward_num in sorted(divisions_by_ward.keys(), key=int):
            divisions = divisions_by_ward[ward_num]
            merged = union_all(divisions)

            geojson = json.dumps(mapping(merged))
            geos_geom = GEOSGeometry(geojson)

            if geos_geom.geom_type == "Polygon":
                geos_geom = MultiPolygon(geos_geom)

            ward, created = Ward.objects.update_or_create(
                name=f"Ward {int(ward_num)}",
                defaults={
                    "mpoly": geos_geom,
                    "properties": {"ward_number": int(ward_num)},
                },
            )

            action = "Created" if created else "Updated"
            self.stdout.write(f"{action} {ward.name}")

        self.stdout.write(self.style.SUCCESS(f"Loaded {len(divisions_by_ward)} wards"))
