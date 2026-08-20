"""End-to-end smoke: mocked OSRM → plan persist → map uses stored geometry."""

from __future__ import annotations

from datetime import date

import httpx
from pydantic import SecretStr
from sqlalchemy.orm import Session

from crossdock.config import Settings
from crossdock.distance.osrm import OsrmDistanceProvider
from crossdock.distance.osrm_client import OsrmClient
from crossdock.domain.models import Location, Order, OrderStatus, Shipment, Vehicle, VehicleType
from crossdock.services.map_view import MapViewService
from crossdock.services.planning import PlanningService, solve_prepared_plan
from crossdock.storage.repositories import AssignmentRepository, OrderRepository, VehicleRepository


def _settings(*, use_osrm: bool = True) -> Settings:
    return Settings(
        storage_secret=SecretStr("test-secret-not-for-production"),
        solver_time_limit_s=5.0,
        solver_seed=42,
        max_drops_per_route=3,
        cost_per_km=1.2,
        depot_latitude=51.176,
        depot_longitude=4.836,
        planning_date=date(2026, 7, 30),
        ship_lead_days=2,
        warehouse_capacity_kg=1_000_000.0,
        use_osrm=use_osrm,
        osrm_url="http://osrm.test",
    )


def _seed(db_session: Session) -> None:
    VehicleRepository(db_session).add(
        Vehicle(
            code="T1",
            vehicle_type=VehicleType.TRUCK,
            pallet_capacity=20,
            weight_capacity_kg=12000,
            is_placeholder=False,
        )
    )
    hub = Location(name="Hub", city="Antwerp", country="BE", latitude=51.22, longitude=4.40)
    for code, lat, lon, city in [
        ("A", 50.85, 4.35, "Brussels"),
        ("B", 51.05, 3.72, "Ghent"),
    ]:
        OrderRepository(db_session).add_many(
            [
                Order(
                    delivery_code=code,
                    shipments=[Shipment(shipment_number=f"S-{code}", weight_kg=1500)],
                    pickup_location=hub,
                    delivery_location=Location(
                        name=f"Cust-{code}", city=city, country="BE", latitude=lat, longitude=lon
                    ),
                    delivery_date=date(2026, 8, 1),
                    status=OrderStatus.NEW,
                )
            ]
        )


def test_osrm_smoke_persist_and_map(db_session: Session) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "/table/" in url:
            n = url.count(";") + 1
            distances = [[0.0 if i == j else 25_000.0 for j in range(n)] for i in range(n)]
            return httpx.Response(200, json={"code": "Ok", "distances": distances})
        return httpx.Response(
            200,
            json={
                "code": "Ok",
                "routes": [
                    {
                        "geometry": {
                            "coordinates": [
                                [4.836, 51.176],
                                [4.50, 51.00],
                                [4.35, 50.85],
                                [3.90, 50.95],
                                [3.72, 51.05],
                                [4.836, 51.176],
                            ]
                        }
                    }
                ],
            },
        )

    _seed(db_session)
    settings = _settings(use_osrm=True)
    client = OsrmClient("http://osrm.test", transport=httpx.MockTransport(handler))
    provider = OsrmDistanceProvider(client)
    service = PlanningService(db_session, settings=settings)
    request = service.prepare_plan_request(force_new=True)
    prepared = solve_prepared_plan(
        request,
        distance=provider,
        route_fetcher=provider.route_polyline,
    )
    outcome = service.persist_prepared_plan(prepared, username="smoke")
    routes = AssignmentRepository(db_session).list_routes_for_run(outcome.run_id)
    assert routes
    assert routes[0].polyline_json is not None
    assert "51.0" in routes[0].polyline_json
    assert "4.5" in routes[0].polyline_json

    view = MapViewService(db_session, settings=settings).build_for_run(outcome.run_id)
    assert view is not None
    assert len(view.routes) >= 1
    # Stored OSRM geometry is denser than depot+drops+depot.
    assert len(view.routes[0].polyline) >= 5
