# NEM generation data

`nem_scada_collector.py` collects AEMO's five-minute Dispatch SCADA reports
and half-hourly rooftop PV measurement reports into `nem_scada.sqlite`. It
exports region/fuel totals to `nem_generation_by_fuel_frequent.csv`, which is
the input used by `plots.r`. The original `nem_generation_by_fuel.csv` remains
separate for the GitHub Actions snapshot workflow, avoiding conflicts between
the scheduled snapshots and the more frequent local collector.

Install dependencies and run the collector from this folder:

```powershell
python -m pip install -r requirements.txt
python nem_scada_collector.py
```

For regular five-minute data, schedule the command every five minutes in
Windows Task Scheduler and set **Start in** to this repository folder. The
collector processes every unseen report still listed in AEMO's Current
directories. Those directories are rolling, so running at least every five
minutes minimizes gaps; a long outage can exceed the retained window and leave
missing intervals. Failed downloads are reported and retried on the next run.

The CSV values are MW readings, not MWh. SCADA rows are five-minute snapshots;
rooftop PV is published at a half-hour interval. Timestamps are AEMO settlement
time as published in the reports.
