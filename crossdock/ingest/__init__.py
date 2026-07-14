"""Ingest layer: OrderSource port (from T2).

Phase 1 adapter: Excel import (pandas + openpyxl); DataFrames never
leave this package — rows are validated into pydantic models here.
Phase 2 adapter: e2open TMS API.
"""
