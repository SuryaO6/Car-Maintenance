# AI Car Maintenance Predictor (Advanced Edition)

A rule-based maintenance predictor for one or more vehicles, upgraded from a
single-file script into a small, tested, modular application.

## What changed vs. the original

| Area | Before | Now |
|---|---|---|
| Structure | One `car_maintenance.py` file | `models.py`, `storage.py`, `service_config.py`, `predictor.py`, `cli.py`, `main.py` |
| Vehicles | One car per data file | A "garage" of multiple vehicles, switchable |
| Service intervals | Hardcoded dict | Editable `service_intervals.json`; add custom service types at runtime |
| Data integrity | Trusted the JSON as-is | Auto-fixes typo'd service names (e.g. "Oil Chnage" → "Oil Change") and de-duplicates repeated log entries on load |
| Predictions | km/months remaining only | Also projects a **calendar date** using your actual recorded mileage rate |
| Cost tracking | None | Optional cost + notes per service; spend totals in `stats` |
| History | Print only | View, plus **export to CSV** |
| Safety | Overwrites the JSON directly | Rotating backups (last 5) before every save, atomic write |
| Interface | Interactive menu only | Interactive menu **and** scriptable CLI subcommands (`--help` for full list) |
| Tests | None | `tests/test_predictor.py`, 12 unit tests covering the prediction logic |

## Web UI

A local browser dashboard, built on top of the same `models` / `storage` /
`predictor` / `service_config` engine the CLI uses -- no logic is duplicated.

```bash
pip install -r requirements.txt
python app.py
```
Then open **http://127.0.0.1:5000** in your browser.

What it gives you over the CLI:
- Odometer readout + vehicle switcher
- Upcoming services shown as color-coded tags (red = overdue, amber = due soon,
  green = on track, blue = no record yet)
- Quick-action forms for updating mileage and logging a service (with cost/notes,
  and a "custom service" option that adds it to the interval config on the fly)
- A service ledger page with a one-click CSV export
- Total spend / most-frequent-service stats on the dashboard

## CLI Usage

Interactive menu (same feel as before):
```bash
python main.py
```

Scriptable subcommands (for automation, cron, etc.):
```bash
python main.py setup --name "BMW" --mileage 15000 --condition Normal
python main.py mileage --value 15200
python main.py service --type "Oil Change" --cost 45.50 --notes "synthetic oil"
python main.py predict
python main.py stats
python main.py history
python main.py export --path history.csv
python main.py list
python main.py switch --name "BMW"
```

## Running tests
```bash
python -m unittest discover -s tests -v
```

## Data files
- `car_data.json` — your garage (vehicles, mileage, service/mileage history). Auto-migrated from the old single-car schema the first time you run a command that saves.
- `service_intervals.json` — editable service interval table (created automatically on first run).
- `backups/` — the last 5 snapshots of `car_data.json`, saved automatically before every write.

## Notes on the data you uploaded
Your original `car_data.json` had three "Oil Change" log entries at the same
mileage and date — two spelled "Oil Chnage". The migration logic fixes the
typo via fuzzy matching against the known service list and removes the
duplicates, so predictions aren't skewed by phantom repeat services.
