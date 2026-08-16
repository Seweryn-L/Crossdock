from pathlib import Path

raw = Path("crossdock/ui/pages.py").read_bytes()
text = raw.decode("utf-8", errors="replace")
idx = text.find('@ui.page("/")')
Path("_dash_snip.txt").write_text(text[idx : idx + 500], encoding="utf-8")
print("has order_status_pl", "order_status_pl" in text)
print("has collect_dashboard", "collect_dashboard" in text)
print("len", len(text))
