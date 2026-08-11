# Tydzień 7 — Walkthrough (buforowanie + operacyjność)

> Plan: [`plan_t7_implementacja.md`](plan_t7_implementacja.md)

## Status

| Element | Status |
|---|---|
| FR-022 heurystyka + propozycja na Magazynie | done |
| `/system` Stan systemu | done |
| Backup SQLite (nocny + ręczny) | done |
| Baner / status ostatniego importu | done |

## Jak sprawdzić

```powershell
uv run pytest tests/optimization/test_buffering.py tests/services/test_backup.py tests/services/test_buffering_service.py -q
uv run crossdock
```

1. **Magazyn** → Wygeneruj propozycje → zaznacz „buforuj” → Akceptuj
2. **Stan systemu** → metryki + **Utwórz backup teraz**
3. **Zlecenia** → import → widać status ostatniego importu

## Uwagi

- Stawki W-06: placeholdery w `.env` (`STORAGE_COST_PER_PALLET_DAY`, `LTL_COST_MULTIPLIER`, próg 15%).
- Akceptacja bufora → `warehouse_queue` ze statusem `held` i note `buffer:Xd`.
