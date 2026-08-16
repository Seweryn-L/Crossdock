"""SLA helpers: last legal warehouse departure vs planning day."""

from datetime import date, timedelta

from hypothesis import given
from hypothesis import strategies as st

from crossdock.domain.sla import (
    departure_is_legal,
    is_must_ship,
    is_overdue,
    must_leave_by,
    route_should_send,
    slack_days,
)


def test_must_leave_by_is_delivery_minus_lead() -> None:
    assert must_leave_by(date(2026, 8, 10), 2) == date(2026, 8, 8)


def test_same_day_delivery_is_not_legal_with_default_lead() -> None:
    day = date(2026, 8, 10)
    assert departure_is_legal(day, day, 2) is False
    assert departure_is_legal(day, date(2026, 8, 8), 2) is True


def test_slack_last_day_and_overdue() -> None:
    delivery = date(2026, 8, 10)
    assert slack_days(delivery, date(2026, 8, 8), 2) == 0
    assert is_must_ship(0)
    assert slack_days(delivery, date(2026, 8, 9), 2) == -1
    assert is_overdue(-1)


def test_thin_route_holds_when_slack_remains() -> None:
    assert route_should_send(fill_ratio=0.40, min_fill_ratio=0.90, slacks=(5, 3)) is False


def test_thin_route_sends_on_last_departure_day() -> None:
    assert route_should_send(fill_ratio=0.40, min_fill_ratio=0.90, slacks=(0, 4)) is True


def test_full_route_sends_even_with_slack() -> None:
    assert route_should_send(fill_ratio=0.95, min_fill_ratio=0.90, slacks=(6,)) is True


@given(
    lead=st.integers(min_value=0, max_value=10),
    offset=st.integers(min_value=-5, max_value=20),
)
def test_slack_matches_must_leave_minus_planning(lead: int, offset: int) -> None:
    delivery = date(2026, 8, 20)
    planning = delivery + timedelta(days=offset)
    slack = slack_days(delivery, planning, lead)
    assert slack == (must_leave_by(delivery, lead) - planning).days
    assert is_must_ship(slack) is (slack <= 0)
    assert is_overdue(slack) is (slack < 0)


@given(
    lead=st.integers(min_value=0, max_value=8),
    slack=st.integers(min_value=-5, max_value=12),
    fill=st.floats(min_value=0.05, max_value=1.2, allow_nan=False),
)
def test_send_past_deadline_always_flags_overdue(lead: int, slack: int, fill: float) -> None:
    delivery = date(2026, 8, 20)
    planning = must_leave_by(delivery, lead) - timedelta(days=slack)
    assert slack_days(delivery, planning, lead) == slack
    send = route_should_send(fill_ratio=fill, min_fill_ratio=0.90, slacks=(slack,))
    if slack < 0:
        assert is_overdue(slack)
        assert send
    assert not (send and slack > 0 and fill + 1e-9 < 0.90)
