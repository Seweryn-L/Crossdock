"""OrderSource port — interchangeable Excel (Faza 1) / e2open API (Faza 2)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from crossdock.domain.models import Order


@dataclass(frozen=True)
class RowError:
    """Validation failure for a single spreadsheet row (1-based Excel row number)."""

    row_number: int
    message: str


@dataclass
class ImportReport:
    """Result of an import: accepted domain orders + per-row errors."""

    orders: list[Order] = field(default_factory=list)
    rejected: list[RowError] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def accepted_count(self) -> int:
        return len(self.orders)


class OrderSource(Protocol):
    """Port: load transport orders from an external source."""

    def load(self, source: Path | bytes) -> ImportReport:
        """Parse source into domain orders; never raise on per-row data errors."""
        ...
