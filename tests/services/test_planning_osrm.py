"""Planning pipeline with mocked OSRM distance matrices."""

from __future__ import annotations

from datetime import date

import httpx
import numpy as np

from crossdock.distance.haversine import HaversineDistanceProvider
from crossdock.distance.osrm import OsrmDistanceProvider
from crossdock.distance.osrm_client import OsrmClient
from crossdock.optimization.dto import SolverOrder, SolverVehicle
from crossdock.services.planning import (
    OrderGeoSnapshot,
    PlanSolveRequest,
    build_routing_bundle,
    solve_assignment_stage,
    solve_prepared_plan,
)


def _request() -> PlanSolveRequest:
    return PlanSolveRequest(
        solver_orders=(
            SolverOrder(id=1, delivery_code="A", weight_kg=1000.0, drop_key="51.2000|4.9000"),
            SolverOrder(id=2, delivery_code="B", weight_kg=1000.0, drop_key="51.1000|4.8000"),
        ),
        solver_vehicles=(SolverVehicle(id=10, code="T1", weight_capacity_kg=12000.0),),
        order_geos=(
            OrderGeoSnapshot(
                id=1,
                delivery_code="A",
                weight_kg=1000.0,
                latitude=51.20,
                longitude=4.90,
                drop_key="51.2000|4.9000",
            ),
            OrderGeoSnapshot(
                id=2,
                delivery_code="B",
                weight_kg=1000.0,
                latitude=51.10,
                longitude=4.80,
                drop_key="51.1000|4.8000",
            ),
        ),
        held_skipped=(),
        skipped_weight=(),
        existing_run_id=None,
        assignment_limit_s=2.0,
        routing_limit_s=2.0,
        seed=1,
        max_drops_per_route=3,
        depot=(51.176, 4.836),
        cost_per_km=1.2,
        planning_date=date(2026, 7, 30),
        ship_lead_days=2,
    )


def test_build_routing_bundle_uses_osrm_matrix() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        # Force asymmetric-looking but symmetric metre matrix distinct from haversine.
        n = 3  # depot + 2 drops
        distances = [[0.0 if i == j else 50_000.0 for j in range(n)] for i in range(n)]
        return httpx.Response(200, json={"code": "Ok", "distances": distances})

    client = OsrmClient("http://osrm.test", transport=httpx.MockTransport(handler))
    provider = OsrmDistanceProvider(client)
    stage = solve_assignment_stage(_request())
    bundle = build_routing_bundle(stage.assignment, _request(), distance=provider)
    assert len(bundle.vehicles) == 1
    matrix = bundle.vehicles[0].distance_matrix_m
    assert matrix[0][1] == 50_000
    # Haversine would be much smaller for these nearby points.
    haver = HaversineDistanceProvider().distance_matrix(
        [(51.176, 4.836), (51.20, 4.90), (51.10, 4.80)]
    )
    assert float(np.max(haver)) * 1000 < 40_000


def test_solve_prepared_plan_attaches_polyline() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "/table/" in url:
            n = url.count(";") + 1
            distances = [[0.0 if i == j else 10_000.0 for j in range(n)] for i in range(n)]
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
                                [4.85, 51.18],
                                [4.90, 51.20],
                                [4.836, 51.176],
                            ]
                        }
                    }
                ],
            },
        )

    client = OsrmClient("http://osrm.test", transport=httpx.MockTransport(handler))
    provider = OsrmDistanceProvider(client)
    prepared = solve_prepared_plan(
        _request(),
        distance=provider,
        route_fetcher=provider.route_polyline,
    )
    assert prepared.routes
    poly = prepared.routes[0].get("polyline")
    assert poly is not None
    assert len(poly) >= 3
    assert poly[0] == (51.176, 4.836)
