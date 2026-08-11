"""Location coordinate dictionary: seed + CRUD helpers for UI."""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy.orm import Session

from crossdock.config import Settings, get_settings
from crossdock.domain.models import Location
from crossdock.storage.repositories import AuditLogRepository, LocationCoordsRepository

DEFAULT_SEED_PATH = Path("config/location_coords_seed.json")


def load_seed_locations(path: Path | None = None) -> list[Location]:
    seed_path = path or DEFAULT_SEED_PATH
    raw = json.loads(seed_path.read_text(encoding="utf-8"))
    locations: list[Location] = []
    for item in raw.get("locations", []):
        locations.append(
            Location(
                name=str(item["name"]),
                city=item.get("city"),
                country=item.get("country"),
                postal_code=item.get("postal_code"),
                latitude=float(item["latitude"]),
                longitude=float(item["longitude"]),
            )
        )
    return locations


def seed_location_coords(
    session: Session,
    *,
    path: Path | None = None,
    force: bool = False,
) -> int:
    """Insert seed locations when dictionary is empty (or always if force).

    Returns number of newly inserted rows (skips existing keys).
    """
    repo = LocationCoordsRepository(session)
    if not force and repo.count() > 0:
        return 0
    added = 0
    for location in load_seed_locations(path):
        key = location.location_key()
        if repo.get(key) is not None:
            continue
        repo.upsert(location)
        added += 1
    if added:
        AuditLogRepository(session).record(
            username="system",
            action="locations.seed",
            details={"count": added, "force": force},
        )
    return added


def list_locations(session: Session) -> list[Location]:
    return LocationCoordsRepository(session).list_all()


def upsert_location(session: Session, location: Location, *, username: str) -> Location:
    saved = LocationCoordsRepository(session).upsert(location)
    AuditLogRepository(session).record(
        username=username,
        action="locations.upsert",
        details={"key": location.location_key()},
    )
    return saved


def delete_location(session: Session, location_key: str, *, username: str) -> bool:
    deleted = LocationCoordsRepository(session).delete_by_key(location_key)
    if deleted:
        AuditLogRepository(session).record(
            username=username,
            action="locations.delete",
            details={"key": location_key},
        )
    return deleted


def seed_path_from_settings(settings: Settings | None = None) -> Path:
    _ = settings or get_settings()
    return DEFAULT_SEED_PATH


def apply_coords_to_existing_orders(session: Session) -> int:
    """Fill missing lat/lon on persisted orders from the coordinate dictionary."""
    from sqlalchemy import select

    from crossdock.storage.tables import OrderRow

    coords = LocationCoordsRepository(session)
    rows = session.scalars(select(OrderRow)).all()
    updated = 0
    for row in rows:
        changed = False
        if row.delivery_latitude is None or row.delivery_longitude is None:
            delivery = Location(
                name=row.delivery_name,
                city=row.delivery_city,
                country=row.delivery_country,
                postal_code=row.delivery_postal_code,
            )
            known = coords.get(delivery.location_key()) or coords.find_by_city_country(
                delivery.city, delivery.country
            )
            if known is not None and known.latitude is not None and known.longitude is not None:
                row.delivery_latitude = known.latitude
                row.delivery_longitude = known.longitude
                changed = True
        if row.pickup_latitude is None or row.pickup_longitude is None:
            pickup = Location(
                name=row.pickup_name,
                city=row.pickup_city,
                country=row.pickup_country,
                postal_code=row.pickup_postal_code,
            )
            known = coords.get(pickup.location_key()) or coords.find_by_city_country(
                pickup.city, pickup.country
            )
            if known is not None and known.latitude is not None and known.longitude is not None:
                row.pickup_latitude = known.latitude
                row.pickup_longitude = known.longitude
                changed = True
        if changed:
            updated += 1
    if updated:
        session.flush()
    return updated
