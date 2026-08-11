# Tydzień 7 — Buforowanie FR-022 + operacyjność (plan implementacji)

> Daty w harmonogramie: **25–31.08.2026**.
> Harmonogram: [`plan_tworzenia_aplikacji.md`](plan_tworzenia_aplikacji.md) — wiersz T7.
> Fundament: T6 (kolejka FR-020, raporty), UX planu (Jedzie/Zostaje). Powiązane: FR-022.

## Cel tygodnia

**„System proponuje, które zlecenia opłaca się przytrzymać; aplikacja wygląda na wykończoną.”**

## Założenia

- Heurystyka „wyślij vs buforuj” w `optimization/` (czysty Python).
- Stawki W-06: placeholdery w `Settings` + golden test liczbowy (próg 15%).
- Akceptacja propozycji → `warehouse_queue` ze statusem `held` + note `buffer:Xd`.
- Bez auto-enqueue przy Generuj plan.
- Stan systemu, nocny backup SQLite (APScheduler), baner last_import.

## DoD

- Propozycja buforowania na `/warehouse` + audyt
- `/system` (DB, plan, logi, backup)
- Backup nocny + ręczny
- Testy FR-022 + walkthrough

## Poza T7

OSRM, API e2open, golden Patryka (T8).
