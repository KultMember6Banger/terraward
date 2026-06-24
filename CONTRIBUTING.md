# Contributing

The whole point of TerraWard is that **adding a capability is one function.** If you can
write a Python function that turns daily conditions into alerts, you can add a module.

## Add a module

```python
@module("my_risk", "One-line description of what it watches")
def my_risk(days):
    c = CONFIG["my_risk"]              # your thresholds live here
    alerts = []
    for d in days:
        if d.max_temp >= c["threshold"]:
            alerts.append(Alert("my_risk", Severity.WARNING,
                "What's happening and what to do — organically.", date=d.date))
    return alerts
```

Add your defaults to `DEFAULT_CONFIG`:

```python
"my_risk": {"threshold": 30.0},
```

That's it — it's now listed, toggleable, calibratable, loggable, and exportable like every
other module.

## Each module receives

A list of `DaySummary` objects: `date, min_temp, max_temp, mean_temp, mean_rh, humid_hours,
precip_mm, leaf_wet_hours`, plus optional sensor fields (`soil_moisture, soil_oxygen,
dissolved_oxygen, chlorophyll, water_temp, salinity, soil_temp_min`), each `None` if absent.

## Principles

- **Organic only.** No synthetic-chemical recommendations. Advise prevention and
  biological/management controls.
- **Ground your thresholds.** Cite the science (extension data, peer-reviewed models) in a
  docstring. Defaults are starting points farmers recalibrate.
- **Be honest about uncertainty.** Alerts flag *favourable conditions*, not certainties.
- **Add a test.** See `test_terraward.py`.

## Run the tests

```bash
python3 -m unittest test_terraward -v
```

## Swap points

Real deployments swap data sources: `fetch_weather()` for a regional feed (e.g. Agromet/CRA-W)
or Copernicus Marine for the sea. The rest of the engine only depends on the `DaySummary` shape.
