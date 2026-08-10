"""Load Excel column mapping from a JSON config file (not hardcoded).

Until Sandra's official dictionary and Patryk's sample file arrive, this
mapping is a working placeholder — see docs/otwarte_wejscia_zespolu.md.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field

# Default path relative to the repository root (cwd when running the app).
DEFAULT_MAPPING_PATH = Path("config/excel_column_mapping.json")


class ExcelColumnMapping(BaseModel):
    """Declarative mapping of logical fields → spreadsheet column names."""

    header_row: int = Field(ge=1, description="1-based header row index in the sheet")
    sheet_name: str | None = None
    weight_unit: str = Field(default="kg", pattern="^(kg|lb)$")
    date_formats: list[str] = Field(default_factory=lambda: ["%Y-%m-%d", "%m/%d/%Y"])
    columns: dict[str, str]
    equipment_aliases: dict[str, str] = Field(default_factory=dict)

    def column(self, logical: str) -> str:
        try:
            return self.columns[logical]
        except KeyError as exc:
            raise KeyError(f"Logical column {logical!r} missing from mapping config") from exc


def load_excel_column_mapping(path: Path | None = None) -> ExcelColumnMapping:
    mapping_path = path or DEFAULT_MAPPING_PATH
    raw = json.loads(mapping_path.read_text(encoding="utf-8"))
    # Strip documentation-only keys.
    raw.pop("_comment", None)
    return ExcelColumnMapping.model_validate(raw)


@lru_cache
def get_excel_column_mapping() -> ExcelColumnMapping:
    from crossdock.config import get_settings

    return load_excel_column_mapping(get_settings().excel_mapping_path)
