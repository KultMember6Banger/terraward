"""Test suite for terraward. Run: python3 -m unittest test_terraward -v"""
import unittest
import terraward as fre
from terraward import DaySummary, Severity


def ds(date="2026-06-01", tmin=12.0, tmax=20.0, tmean=16.0, humid=6, **kw):
    return DaySummary(date, tmin, tmax, tmean, humid, **kw)


class TestDataLayer(unittest.TestCase):
    def test_summarise(self):
        # hourly tuples are (time, temp, rh, precip, wind)
        hourly = [(f"2026-06-01T{h:02d}:00", 10.0 + h % 5, 95.0 if h < 8 else 60.0,
                   1.0 if h == 0 else 0.0, 5.0) for h in range(24)]
        days = fre._summarise(hourly)
        self.assertEqual(len(days), 1)
        d = days[0]
        self.assertEqual(d.humid_hours, 8)
        self.assertEqual(d.leaf_wet_hours, 8)
        self.assertAlmostEqual(d.precip_mm, 1.0)


class TestThi(unittest.TestCase):
    def test_formula(self):
        self.assertAlmostEqual(fre._thi(25, 50), 71.775, places=2)

    def test_severity(self):
        self.assertEqual(fre.livestock_thi([ds(tmax=33, mean_rh=66)])[0].severity, Severity.DANGER)
        self.assertEqual(fre.livestock_thi([ds(tmax=18, mean_rh=50)]), [])


class TestBlightEnsemble(unittest.TestCase):
    def test_high_confidence(self):
        days = [ds("2026-06-01", tmin=12, humid=12), ds("2026-06-02", tmin=12, humid=12)]
        a = fre.late_blight(days)
        self.assertEqual(a[-1].severity, Severity.DANGER)
        self.assertEqual(a[-1].confidence, "HIGH")

    def test_medium_confidence(self):
        days = [ds("2026-06-01", tmin=12, humid=7), ds("2026-06-02", tmin=12, humid=7)]
        self.assertEqual(fre.late_blight(days)[-1].confidence, "MEDIUM")

    def test_single_day_watch(self):
        days = [ds("2026-06-01", tmin=5, humid=0), ds("2026-06-02", tmin=12, humid=8),
                ds("2026-06-03", tmin=5, humid=0)]
        a = fre.late_blight(days)
        self.assertEqual(len(a), 1)
        self.assertEqual(a[0].severity, Severity.WATCH)


class TestThresholdModules(unittest.TestCase):
    def test_frost(self):
        self.assertEqual(fre.frost_risk([ds(tmin=-1)])[0].severity, Severity.DANGER)
        self.assertEqual(fre.frost_risk([ds(tmin=2)])[0].severity, Severity.WARNING)
        self.assertEqual(fre.frost_risk([ds(tmin=5)]), [])

    def test_heat(self):
        self.assertEqual(fre.heat_stress([ds(tmax=33)])[0].severity, Severity.DANGER)
        self.assertEqual(fre.heat_stress([ds(tmax=29)])[0].severity, Severity.WARNING)
        self.assertEqual(fre.heat_stress([ds(tmax=25)]), [])

    def test_soil_physical(self):
        sev = {a.severity for a in fre.soil_conditions([ds(soil_moisture=52, soil_oxygen=7)])}
        self.assertIn(Severity.DANGER, sev)
        self.assertEqual(fre.soil_conditions([ds(soil_moisture=5)])[0].severity, Severity.DANGER)
        self.assertEqual(fre.soil_conditions([ds(soil_moisture=8)])[0].severity, Severity.WARNING)

    def test_pollinators(self):
        self.assertEqual(fre.pollinators([ds(tmax=10)])[0].severity, Severity.WARNING)
        self.assertEqual(fre.pollinators([ds(tmax=16)])[0].severity, Severity.WATCH)
        self.assertEqual(fre.pollinators([ds(tmax=20)]), [])
        self.assertEqual(fre.pollinators([ds(tmax=20, precip_mm=5)])[0].severity, Severity.WARNING)


class TestColdStress(unittest.TestCase):
    def test_severe_via_windchill(self):
        # -12C air with 40 km/h wind chills well below the -15C severe threshold
        self.assertEqual(fre.cold_stress([ds(tmin=-12, max_wind=40)])[0].severity, Severity.DANGER)

    def test_wet_cold_warns(self):
        # 8C is fine for a dry coat, but a wet coat (rain) at 8C is a warning
        self.assertEqual(fre.cold_stress([ds(tmin=8, precip_mm=5)])[0].severity, Severity.WARNING)

    def test_mild_dry_none(self):
        self.assertEqual(fre.cold_stress([ds(tmin=10)]), [])


class TestWind(unittest.TestCase):
    def test_gale_and_strong(self):
        self.assertEqual(fre.wind_conditions([ds(max_wind=70)])[0].severity, Severity.DANGER)
        self.assertEqual(fre.wind_conditions([ds(max_wind=45)])[0].severity, Severity.WARNING)
        self.assertEqual(fre.wind_conditions([ds(max_wind=20)]), [])


class TestSoilNutrients(unittest.TestCase):
    def test_acidic_and_excess_phosphorus(self):
        sev = {a.severity for a in fre.soil_conditions([ds(soil_ph=5.2, soil_phosphorus=80)])}
        self.assertIn(Severity.WARNING, sev)

    def test_ideal_ph_only_info(self):
        alerts = fre.soil_conditions([ds(soil_ph=6.5)])
        self.assertTrue(all(a.severity == Severity.INFO for a in alerts))

    def test_low_nutrients_watch(self):
        watch = [a for a in fre.soil_conditions(
            [ds(soil_nitrogen=8, soil_potassium=70, soil_organic_matter=1.0)])
            if a.severity == Severity.WATCH]
        self.assertGreaterEqual(len(watch), 3)


class TestMarine(unittest.TestCase):
    def test_oxygen_and_bloom(self):
        sev = {a.severity for a in fre.marine_conditions([ds(dissolved_oxygen=1.5, chlorophyll=12)])}
        self.assertIn(Severity.DANGER, sev)
        self.assertEqual(fre.marine_conditions([ds(dissolved_oxygen=3.0)])[0].severity, Severity.WARNING)


class TestWaterQuality(unittest.TestCase):
    def test_toxic_ammonia_and_nitrite(self):
        self.assertEqual(fre.marine_conditions([ds(water_ammonia=2.5)])[0].severity, Severity.DANGER)
        self.assertEqual(fre.marine_conditions([ds(water_nitrite=1.2)])[0].severity, Severity.DANGER)

    def test_ph_out_of_band_warns(self):
        self.assertIn(Severity.WARNING,
                      {a.severity for a in fre.marine_conditions([ds(water_ph=5.8)])})

    def test_clean_water_only_info(self):
        alerts = fre.marine_conditions([ds(water_ammonia=0.1, water_nitrite=0.05,
                                           water_nitrate=10, water_ph=7.5)])
        self.assertTrue(all(a.severity == Severity.INFO for a in alerts))


class TestCamera(unittest.TestCase):
    def test_placeholder_is_info(self):
        alerts = fre.run_scan("/x.jpg", None, fre.placeholder_detector, None, "Loc")
        self.assertEqual(alerts[0].severity, Severity.INFO)

    def test_confident_detection_alerts_and_logs(self):
        import os, tempfile
        fd, dbp = tempfile.mkstemp(suffix=".db"); os.close(fd); os.remove(dbp)
        try:
            store = fre.Storage(dbp)
            det = lambda path, crop: [fre.Detection("late_blight", 0.9, "spots")]
            alerts = fre.run_scan("/leaf.jpg", "potato", det, store, "Loc")
            self.assertEqual(alerts[0].severity, Severity.DANGER)   # 0.9 >= danger_confidence
            self.assertEqual(len(store.sightings("Loc")), 1)        # auto-logged as sighting
        finally:
            os.remove(dbp)


class TestPests(unittest.TestCase):
    def test_milestone(self):
        days = [ds(tmean=20) for _ in range(10)]
        self.assertEqual(fre.insect_pests(days)[0].severity, Severity.WATCH)


class TestAccuracy(unittest.TestCase):
    def test_classification(self):
        sightings = [("2026-06-20", "late_blight", "confirmed"),
                     ("2026-06-14", "late_blight", "clear")]
        flagged = {("2026-06-20", "late_blight"), ("2026-06-14", "late_blight")}
        out = fre.render_accuracy("Test", sightings, flagged)
        self.assertIn("hits=1", out)
        self.assertIn("false_alarms=1", out)


class TestConfigOverride(unittest.TestCase):
    def test_threshold_tuning(self):
        old = fre.CONFIG["frost_risk"]["near_frost"]
        try:
            self.assertEqual(fre.frost_risk([ds(tmin=2)])[0].severity, Severity.WARNING)
            fre.CONFIG["frost_risk"]["near_frost"] = 1.0
            self.assertEqual(fre.frost_risk([ds(tmin=2)]), [])
        finally:
            fre.CONFIG["frost_risk"]["near_frost"] = old


class TestConfigFile(unittest.TestCase):
    def test_load_from_file(self):
        import io, json, os, tempfile
        from contextlib import redirect_stderr
        old = dict(fre.CONFIG["frost_risk"])
        fd, path = tempfile.mkstemp(suffix=".json")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump({"frost_risk": {"near_frost": 1.0}, "nonsense": {"x": 1}}, f)
            buf = io.StringIO()
            with redirect_stderr(buf):
                fre.load_config(path)
            self.assertEqual(fre.CONFIG["frost_risk"]["near_frost"], 1.0)
            self.assertIn("nonsense", buf.getvalue())
        finally:
            fre.CONFIG["frost_risk"] = old
            os.remove(path)


class TestSplash(unittest.TestCase):
    def test_opening_scene(self):
        out = fre.splash()
        self.assertIn("T E R R A W A R D", out)
        self.assertIn("watched over", out)


class TestInputHardening(unittest.TestCase):
    """Untrusted inputs (API response, config files) must fail safely, never crash."""
    def _good(self):
        return {"hourly": {"time": ["2026-06-20T00:00", "2026-06-20T01:00"],
                           "temperature_2m": [12.0, 11.5], "relative_humidity_2m": [88, 91],
                           "precipitation": [0.0, 0.2], "wind_speed_10m": [10, 12]}}

    def test_valid_response_parses(self):
        self.assertEqual(len(fre._parse_weather_json(self._good())), 1)

    def test_non_dict_response_rejected(self):
        with self.assertRaises(RuntimeError):
            fre._parse_weather_json(["not", "a", "dict"])

    def test_error_field_rejected(self):
        with self.assertRaises(RuntimeError):
            fre._parse_weather_json({"error": True, "reason": "bad coords"})

    def test_missing_hourly_rejected(self):
        with self.assertRaises(RuntimeError):
            fre._parse_weather_json({"hourly": None})

    def test_time_not_list_rejected(self):
        with self.assertRaises(RuntimeError):
            fre._parse_weather_json({"hourly": {"time": "nope"}})

    def test_garbage_values_skipped_not_crash(self):
        d = self._good()
        d["hourly"]["temperature_2m"] = ["NaNsense", None]   # both hours unusable
        with self.assertRaises(RuntimeError):                # clean error, not a crash
            fre._parse_weather_json(d)

    def test_config_rejects_bad_value_type(self):
        import io, json, os, tempfile
        from contextlib import redirect_stderr
        old = dict(fre.CONFIG["frost_risk"])
        fd, path = tempfile.mkstemp(suffix=".json")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump({"frost_risk": {"near_frost": "cold"}}, f)   # string, not number
            buf = io.StringIO()
            with redirect_stderr(buf):
                fre.load_config(path)
            self.assertEqual(fre.CONFIG["frost_risk"]["near_frost"], old["near_frost"])
            self.assertIn("near_frost", buf.getvalue())
        finally:
            fre.CONFIG["frost_risk"] = old
            os.remove(path)

    def test_config_non_object_rejected(self):
        import json, os, tempfile
        fd, path = tempfile.mkstemp(suffix=".json")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(["not", "an", "object"], f)
            with self.assertRaises(ValueError):
                fre.load_config(path)
        finally:
            os.remove(path)


class TestDataProtection(unittest.TestCase):
    def test_db_is_created_private(self):
        import os, tempfile, stat
        if os.name != "posix":
            self.skipTest("POSIX file permissions only")
        d = tempfile.mkdtemp()
        path = os.path.join(d, "farm.db")
        fre.Storage(path)
        mode = stat.S_IMODE(os.stat(path).st_mode)
        self.assertEqual(mode, 0o600)   # owner read/write only — no group/other access
        os.remove(path); os.rmdir(d)


class TestGeocoding(unittest.TestCase):
    def test_valid_geocode(self):
        data = {"results": [{"name": "Meise", "admin1": "Flanders", "country": "Belgium",
                             "latitude": 50.93, "longitude": 4.33}]}
        lat, lon, label = fre._parse_geocode_json(data, "Meise")
        self.assertAlmostEqual(lat, 50.93)
        self.assertAlmostEqual(lon, 4.33)
        self.assertIn("Meise", label)
        self.assertIn("Belgium", label)

    def test_no_results_helpful_error(self):
        with self.assertRaises(RuntimeError):
            fre._parse_geocode_json({"results": []}, "Nowheresville")

    def test_non_dict_rejected(self):
        with self.assertRaises(RuntimeError):
            fre._parse_geocode_json("nope", "X")

    def test_missing_coords_rejected(self):
        with self.assertRaises(RuntimeError):
            fre._parse_geocode_json({"results": [{"name": "X"}]}, "X")


class TestPollinatorSpecies(unittest.TestCase):
    def setUp(self):
        self._saved = list(fre.KEPT_POLLINATORS)

    def tearDown(self):
        fre.KEPT_POLLINATORS[:] = self._saved

    def test_bumblebee_works_when_honeybee_grounded(self):
        fre.KEPT_POLLINATORS[:] = ["honeybee", "bumblebee"]
        a = fre.pollinators([ds(tmax=10)])      # too cold for honeybees, fine for bumblebees
        self.assertEqual(len(a), 1)
        self.assertEqual(a[0].severity, Severity.WATCH)
        self.assertIn("bumblebees still foraging", a[0].message)

    def test_all_grounded_below_every_threshold(self):
        fre.KEPT_POLLINATORS[:] = ["honeybee", "bumblebee"]
        a = fre.pollinators([ds(tmax=5)])       # below bumblebee min too
        self.assertEqual(a[0].severity, Severity.WARNING)
        self.assertIn("no bee activity", a[0].message)

    def test_honeybee_only_still_warns_cold(self):
        fre.KEPT_POLLINATORS[:] = ["honeybee"]
        self.assertEqual(fre.pollinators([ds(tmax=10)])[0].severity, Severity.WARNING)

    def test_unknown_species_falls_back_to_honeybee(self):
        fre.KEPT_POLLINATORS[:] = ["nonsense"]
        self.assertEqual(fre.pollinators([ds(tmax=20)]), [])   # 20C fine for honeybee


class TestUnits(unittest.TestCase):
    def tearDown(self):
        fre._set_units("metric")

    def test_metric_is_unchanged(self):
        fre._set_units("metric")
        self.assertEqual(fre.T(0), "0.0C")
        self.assertEqual(fre.W(100), "100 km/h")
        self.assertEqual(fre.R(25.4), "25.4mm")

    def test_imperial_conversions(self):
        fre._set_units("imperial")
        self.assertEqual(fre.T(0), "32.0F")
        self.assertEqual(fre.T(100), "212.0F")
        self.assertIn("mph", fre.W(100))
        self.assertIn("in", fre.R(25.4))

    def test_imperial_flows_into_messages(self):
        fre._set_units("imperial")
        a = fre.heat_stress([ds(tmax=40)])          # 40C == 104F
        self.assertTrue(any("104" in x.message and "F" in x.message for x in a))
        self.assertFalse(any("40.0C" in x.message for x in a))


class TestLivestockSpecies(unittest.TestCase):
    def setUp(self):
        self._saved = list(fre.KEPT_LIVESTOCK)

    def tearDown(self):
        fre.KEPT_LIVESTOCK[:] = self._saved

    def test_thi_dairy_more_sensitive_than_beef(self):
        # THI ~75: dairy is into 'moderate' (>=72), beef only 'mild' (>=72,<79)
        fre.KEPT_LIVESTOCK[:] = ["dairy_cattle"]
        dairy = fre.livestock_thi([ds(tmax=27, mean_rh=70)])
        fre.KEPT_LIVESTOCK[:] = ["beef_cattle"]
        beef = fre.livestock_thi([ds(tmax=27, mean_rh=70)])
        self.assertTrue(dairy and (not beef or beef[0].severity <= dairy[0].severity))

    def test_thi_message_names_species(self):
        fre.KEPT_LIVESTOCK[:] = ["dairy_cattle", "beef_cattle"]
        a = fre.livestock_thi([ds(tmax=33, mean_rh=66)])
        self.assertIn("dairy cattle", a[0].message)
        self.assertIn("beef cattle", a[0].message)

    def test_cold_pigs_more_sensitive_than_cattle(self):
        # feels-like ~0C: a risk for pigs (warning 2), fine for dairy cattle (warning -5)
        fre.KEPT_LIVESTOCK[:] = ["pig"]
        pig = fre.cold_stress([ds(tmin=1)])
        fre.KEPT_LIVESTOCK[:] = ["dairy_cattle"]
        cattle = fre.cold_stress([ds(tmin=1)])
        self.assertTrue(pig and pig[0].severity >= Severity.WARNING)
        self.assertEqual(cattle, [])

    def test_default_dairy_unchanged(self):
        fre.KEPT_LIVESTOCK[:] = ["dairy_cattle"]
        self.assertEqual(fre.livestock_thi([ds(tmax=33, mean_rh=66)])[0].severity, Severity.DANGER)
        self.assertEqual(fre.livestock_thi([ds(tmax=18, mean_rh=50)]), [])


class TestManureSpreading(unittest.TestCase):
    def _by_date(self, alerts, date):
        return [a for a in alerts if a.date == date]

    def test_frozen_blocks(self):
        a = fre.manure_spreading([ds(tmin=-3, tmax=2)])
        self.assertEqual(a[0].severity, Severity.DANGER)
        self.assertIn("Frozen", a[0].message)

    def test_heavy_rain_ahead_blocks(self):
        days = [ds(date="2026-05-01", tmin=8, tmax=15, precip_mm=0),
                ds(date="2026-05-02", tmin=8, tmax=15, precip_mm=12),
                ds(date="2026-05-03", tmin=8, tmax=15, precip_mm=12)]
        first = self._by_date(fre.manure_spreading(days), "2026-05-01")
        self.assertEqual(first[0].severity, Severity.DANGER)   # 24mm within 48h

    def test_moderate_rain_ahead_warns(self):
        days = [ds(date="2026-05-01", tmin=8, tmax=15, precip_mm=0),
                ds(date="2026-05-02", tmin=8, tmax=15, precip_mm=6),
                ds(date="2026-05-03", tmin=8, tmax=15, precip_mm=6)]
        first = self._by_date(fre.manure_spreading(days), "2026-05-01")
        self.assertEqual(first[0].severity, Severity.WARNING)  # 12mm within 48h

    def test_saturated_from_recent_rain(self):
        days = [ds(date="2026-05-01", tmin=8, tmax=15, precip_mm=15),
                ds(date="2026-05-02", tmin=8, tmax=15, precip_mm=15),
                ds(date="2026-05-03", tmin=8, tmax=15, precip_mm=0)]
        third = self._by_date(fre.manure_spreading(days), "2026-05-03")
        self.assertEqual(third[0].severity, Severity.WARNING)
        self.assertIn("saturated", third[0].message)

    def test_good_window_with_pointer(self):
        a = fre.manure_spreading([ds(tmin=8, tmax=16, precip_mm=0)])
        self.assertEqual(a[0].severity, Severity.INFO)
        self.assertIn("Good spreading window", a[0].message)
        self.assertIn("certifier", a[0].message)   # defers legal calendar, never fakes it

    def test_cold_dry_day_is_silent(self):
        # not frozen (min 2C) and dry, but too cold for uptake -> no warning, no window
        self.assertEqual(fre.manure_spreading([ds(tmin=2, tmax=5, precip_mm=0)]), [])


class TestAquacultureSpecies(unittest.TestCase):
    def setUp(self):
        self._saved = list(fre.KEPT_AQUACULTURE)

    def tearDown(self):
        fre.KEPT_AQUACULTURE[:] = self._saved

    def _has(self, alerts, needle, minsev=Severity.WARNING):
        return any(needle in a.message.lower() and a.severity >= minsev for a in alerts)

    def test_trout_needs_more_oxygen_than_tilapia(self):
        fre.KEPT_AQUACULTURE[:] = ["trout"]
        self.assertTrue(self._has(fre.marine_conditions([ds(dissolved_oxygen=5.0)]), "oxygen"))
        fre.KEPT_AQUACULTURE[:] = ["tilapia"]
        self.assertFalse(self._has(fre.marine_conditions([ds(dissolved_oxygen=5.0)]), "oxygen"))

    def test_tilapia_cold_stress_trout_fine(self):
        fre.KEPT_AQUACULTURE[:] = ["tilapia"]
        self.assertTrue(self._has(fre.marine_conditions([ds(water_temp=13)]), "cold"))
        fre.KEPT_AQUACULTURE[:] = ["trout"]
        self.assertFalse(self._has(fre.marine_conditions([ds(water_temp=13)]), "temperature"))

    def test_trout_heat_lethal(self):
        fre.KEPT_AQUACULTURE[:] = ["trout"]
        a = fre.marine_conditions([ds(water_temp=25)])
        self.assertTrue(any("lethal" in x.message.lower() and x.severity == Severity.DANGER
                            for x in a))

    def test_ammonia_salmonid_more_sensitive(self):
        fre.KEPT_AQUACULTURE[:] = ["trout"]
        self.assertTrue(self._has(fre.marine_conditions([ds(water_ammonia=0.15)]), "ammonia"))
        fre.KEPT_AQUACULTURE[:] = ["carp"]
        self.assertFalse(self._has(fre.marine_conditions([ds(water_ammonia=0.15)]), "ammonia"))

    def test_default_mixed_unchanged(self):
        fre.KEPT_AQUACULTURE[:] = ["mixed"]
        sev = {a.severity for a in fre.marine_conditions([ds(dissolved_oxygen=1.5, chlorophyll=12)])}
        self.assertIn(Severity.DANGER, sev)
        self.assertEqual(
            fre.marine_conditions([ds(dissolved_oxygen=3.0)])[0].severity, Severity.WARNING)


class TestEvapotranspiration(unittest.TestCase):
    def test_et0_reasonable_summer(self):
        # a warm summer day at ~51N should give a few mm/day of reference ET
        et0 = fre._et0_hargreaves(15, 30, 51.0, 180)
        self.assertTrue(2.0 < et0 < 9.0, et0)

    def test_ra_higher_in_summer_than_winter(self):
        self.assertGreater(fre._ra_mm(51.0, 172), fre._ra_mm(51.0, 355))

    def test_ra_does_not_crash_at_high_latitude(self):
        # arccos clamp: polar latitudes must not raise
        self.assertGreaterEqual(fre._ra_mm(78.0, 355), 0.0)

    def test_dry_spell_triggers_irrigation_warning(self):
        days = [ds(date=f"2026-07-{d:02d}", tmin=18, tmax=33, tmean=25, precip_mm=0)
                for d in range(1, 12)]
        sev = {a.severity for a in fre.evapotranspiration(days)}
        self.assertIn(Severity.WARNING, sev)

    def test_wet_spell_no_warning(self):
        days = [ds(date=f"2026-07-{d:02d}", tmin=14, tmax=20, tmean=17, precip_mm=15)
                for d in range(1, 12)]
        sev = {a.severity for a in fre.evapotranspiration(days)}
        self.assertNotIn(Severity.WARNING, sev)

    def test_summary_info_present(self):
        a = fre.evapotranspiration([ds(date="2026-07-01", tmin=14, tmax=24, tmean=19, precip_mm=2)])
        self.assertTrue(any(x.severity == Severity.INFO and "ET0" in x.message for x in a))


class TestPestProfiles(unittest.TestCase):
    def setUp(self):
        self._pests, self._biofix = list(fre.KEPT_PESTS), fre.BIOFIX

    def tearDown(self):
        fre.KEPT_PESTS[:] = self._pests
        fre.BIOFIX = self._biofix

    def test_cpb_reaches_a_larval_stage(self):
        fre.KEPT_PESTS[:] = ["colorado_potato_beetle"]
        fre.BIOFIX = "2026-06-01"
        days = [ds(tmean=25, date=f"2026-06-{d:02d}") for d in range(1, 11)]  # ~150 DD base 10
        a = fre.insect_pests(days)
        self.assertEqual(a[0].severity, Severity.WATCH)
        self.assertIn("Colorado potato beetle", a[0].message)

    def test_lower_base_accumulates_faster(self):
        # cabbage root fly (base 6) gathers more DD than CPB (base 10) on identical weather
        days = [ds(tmean=16, date=f"2026-06-{d:02d}") for d in range(1, 11)]
        fre.BIOFIX = "2026-06-01"
        fre.KEPT_PESTS[:] = ["cabbage_root_fly"]
        crf = fre.insect_pests(days)[0].message
        fre.KEPT_PESTS[:] = ["colorado_potato_beetle"]
        cpb = fre.insect_pests(days)[0].message
        # 10 days: crf 10*(16-6)=100 DD, cpb 10*(16-10)=60 DD -> crf number is larger
        self.assertIn("100", crf)
        self.assertIn("60", cpb)

    def test_biofix_excludes_earlier_days(self):
        fre.KEPT_PESTS[:] = ["generic"]
        days = [ds(tmean=32, date=f"2026-06-{d:02d}") for d in range(1, 11)]  # full ~220 DD
        fre.BIOFIX = None
        full = fre.insect_pests(days)[0].message
        fre.BIOFIX = "2026-06-06"  # only last 5 days ~110 DD
        limited = fre.insect_pests(days)[0].message
        self.assertIn("egg hatch", full)         # full window crossed the 220 milestone
        self.assertNotIn("egg hatch", limited)   # biofix-limited did not

    def test_default_generic_unchanged(self):
        fre.KEPT_PESTS[:] = ["generic"]
        fre.BIOFIX = None
        self.assertEqual(
            fre.insect_pests([ds(tmean=20) for _ in range(10)])[0].severity, Severity.WATCH)


class TestTreatmentWindow(unittest.TestCase):
    def test_good_window_today(self):
        days = [ds(date="2026-06-01", precip_mm=0.0, max_wind=8, tmax=22),
                ds(date="2026-06-02", precip_mm=0.0, max_wind=8, tmax=22)]
        a = fre.treatment_window(days)
        self.assertTrue(any(x.severity == Severity.INFO and "evening" in x.message for x in a))

    def test_rain_blocks_then_window(self):
        days = [ds(date="2026-06-01", precip_mm=8.0, max_wind=5),
                ds(date="2026-06-02", precip_mm=0.0, max_wind=5),
                ds(date="2026-06-03", precip_mm=0.0, max_wind=5)]
        a = fre.treatment_window(days)
        self.assertTrue(any(x.severity == Severity.WATCH and "wash" in x.message for x in a))
        self.assertTrue(any(x.severity == Severity.INFO and x.date == "2026-06-02" for x in a))

    def test_wind_blocks(self):
        days = [ds(date="2026-06-01", precip_mm=0.0, max_wind=30),
                ds(date="2026-06-02", precip_mm=0.0, max_wind=8)]
        a = fre.treatment_window(days)
        self.assertTrue(any(x.severity == Severity.WATCH and "drift" in x.message for x in a))

    def test_no_window(self):
        days = [ds(date=f"2026-06-0{d}", precip_mm=10.0, max_wind=5) for d in range(1, 6)]
        a = fre.treatment_window(days)
        self.assertTrue(any(x.severity == Severity.WARNING for x in a))


class TestDigest(unittest.TestCase):
    def _days(self):
        return [ds(date="2026-06-01"), ds(date="2026-06-10")]

    def test_horizon_hides_later_and_past(self):
        days = self._days()
        alerts = [fre.Alert("m", Severity.DANGER, "hot now", date="2026-06-01"),
                  fre.Alert("m", Severity.WATCH, "way later", date="2026-06-09")]
        out = fre.render_digest("X", 0, 0, days, ["m"], alerts, demo=True)  # ref 06-01, horizon 06-03
        self.assertIn("hot now", out)
        self.assertNotIn("way later", out)
        self.assertIn("1 further out", out)

    def test_nothing_urgent(self):
        days = self._days()
        alerts = [fre.Alert("m", Severity.WATCH, "future only", date="2026-06-20")]
        out = fre.render_digest("X", 0, 0, days, ["m"], alerts, demo=True)
        self.assertIn("nothing urgent", out.lower())

    def test_severity_ranked(self):
        days = self._days()
        alerts = [fre.Alert("m", Severity.WATCH, "watchitem", date="2026-06-01"),
                  fre.Alert("m", Severity.DANGER, "dangeritem", date="2026-06-02")]
        out = fre.render_digest("X", 0, 0, days, ["m"], alerts, demo=True)
        self.assertLess(out.index("dangeritem"), out.index("watchitem"))


    def test_collapses_repeats(self):
        days = self._days()
        alerts = [fre.Alert("livestock_thi", Severity.DANGER, "heat d1", date="2026-06-01"),
                  fre.Alert("livestock_thi", Severity.DANGER, "heat d2", date="2026-06-02"),
                  fre.Alert("livestock_thi", Severity.DANGER, "heat d3", date="2026-06-03")]
        out = fre.render_digest("X", 0, 0, days, ["livestock_thi"], alerts, demo=True)
        self.assertIn("1 concern(s)", out)        # three alerts collapse to one concern
        self.assertIn("+2 more, through 2026-06-03", out)
        self.assertIn("heat d1", out)             # earliest is the representative shown
        self.assertNotIn("heat d2", out)          # repeats folded into the count

    def test_distinct_modules_stay_separate(self):
        days = self._days()
        alerts = [fre.Alert("heat_stress", Severity.DANGER, "hot", date="2026-06-01"),
                  fre.Alert("livestock_thi", Severity.DANGER, "cattle", date="2026-06-01")]
        out = fre.render_digest("X", 0, 0, days, ["heat_stress"], alerts, demo=True)
        self.assertIn("2 concern(s)", out)        # different modules are not collapsed


class TestScabRisk(unittest.TestCase):
    def test_severe_period(self):
        a = fre.scab_risk([ds(tmean=20, leaf_wet_hours=20)])  # 16-24C band: 9/13/18 -> severe
        self.assertEqual(a[0].severity, Severity.DANGER)

    def test_light_period(self):
        a = fre.scab_risk([ds(tmean=20, leaf_wet_hours=10)])  # >=9 light, <13 moderate
        self.assertEqual(a[0].severity, Severity.WATCH)

    def test_short_wet_no_infection(self):
        self.assertEqual(fre.scab_risk([ds(tmean=20, leaf_wet_hours=5)]), [])  # <9h light

    def test_cold_needs_two_days(self):
        self.assertEqual(fre.scab_risk([ds(tmean=4, leaf_wet_hours=20)]), [])  # <6C needs ~30h+

    def test_too_hot_outside_model(self):
        self.assertEqual(fre.scab_risk([ds(tmean=28, leaf_wet_hours=20)]), [])  # >=26C

    def test_dry_day_clear(self):
        self.assertEqual(fre.scab_risk([ds(tmean=20, leaf_wet_hours=0)]), [])


class TestParcels(unittest.TestCase):
    def test_load_valid(self):
        import tempfile, json as _j, os as _os
        data = {"farm": "F", "parcels": [{"name": "A", "lat": 50.9, "lon": 4.3},
                                         {"name": "B", "place": "Meise"}]}
        fd, path = tempfile.mkstemp(suffix=".json")
        with _os.fdopen(fd, "w") as f:
            _j.dump(data, f)
        try:
            farm, parcels = fre.load_parcels(path)
            self.assertEqual(farm, "F")
            self.assertEqual(len(parcels), 2)
            self.assertEqual(parcels[1]["place"], "Meise")
        finally:
            _os.remove(path)

    def test_load_rejects_no_parcels(self):
        import tempfile, json as _j, os as _os
        fd, path = tempfile.mkstemp(suffix=".json")
        with _os.fdopen(fd, "w") as f:
            _j.dump({"farm": "F"}, f)
        try:
            with self.assertRaises(ValueError):
                fre.load_parcels(path)
        finally:
            _os.remove(path)

    def test_load_rejects_bad_coords(self):
        import tempfile, json as _j, os as _os
        fd, path = tempfile.mkstemp(suffix=".json")
        with _os.fdopen(fd, "w") as f:
            _j.dump({"parcels": [{"name": "X", "lat": 999, "lon": 4}]}, f)
        try:
            with self.assertRaises(ValueError):
                fre.load_parcels(path)
        finally:
            _os.remove(path)

    def test_render_farm_rollup(self):
        days = [ds(date="2026-06-01"), ds(date="2026-06-10")]
        r1 = ("North", 50.9, 4.3, days,
              [fre.Alert("heat_stress", Severity.DANGER, "Extreme heat.", date="2026-06-01")],
              ["heat_stress"])
        r2 = ("Pond", 51.2, 2.9, days,
              [fre.Alert("marine_conditions", Severity.WATCH, "Low oxygen.", date="2026-06-01")],
              ["marine_conditions"])
        out = fre.render_farm("MyFarm", [r1, r2], demo=True, digest=True)
        self.assertIn("MyFarm", out)
        self.assertIn("North", out)
        self.assertIn("Pond", out)
        self.assertIn("DANGER - action needed", out)  # farm OVERALL = worst across parcels

    def test_load_per_parcel_modules(self):
        import tempfile, json as _j, os as _os
        data = {"parcels": [{"name": "Orchard", "lat": 50.9, "lon": 4.3,
                             "modules": ["scab_risk", "insect_pests"],
                             "pests": ["codling_moth"]}]}
        fd, path = tempfile.mkstemp(suffix=".json")
        with _os.fdopen(fd, "w") as f:
            _j.dump(data, f)
        try:
            _farm, parcels = fre.load_parcels(path)
            self.assertEqual(parcels[0]["modules"], ["scab_risk", "insect_pests"])
            self.assertEqual(parcels[0]["pests"], ["codling_moth"])
        finally:
            _os.remove(path)

    def test_load_rejects_unknown_module(self):
        import tempfile, json as _j, os as _os
        fd, path = tempfile.mkstemp(suffix=".json")
        with _os.fdopen(fd, "w") as f:
            _j.dump({"parcels": [{"name": "X", "lat": 50, "lon": 4, "modules": ["not_a_module"]}]}, f)
        try:
            with self.assertRaises(ValueError):
                fre.load_parcels(path)
        finally:
            _os.remove(path)


class TestRobustnessFixes(unittest.TestCase):
    def test_sensor_csv_skips_bad_cells(self):
        import tempfile, os as _os, io, contextlib
        fd, p = tempfile.mkstemp(suffix=".csv")
        with _os.fdopen(fd, "w") as f:
            f.write("date,soil_moisture,soil_ph\n2026-06-01,notnum,6.5\n")
        days = [ds(date="2026-06-01")]
        try:
            with contextlib.redirect_stderr(io.StringIO()):
                n = fre.apply_sensor_csv(days, p)  # must not raise on the bad cell
            self.assertEqual(n, 1)
            self.assertEqual(days[0].soil_ph, 6.5)        # good cell applied
            self.assertIsNone(days[0].soil_moisture)      # bad cell skipped, not poisoned
        finally:
            _os.remove(p)

    def test_sensor_csv_rejects_inf_nan(self):
        import tempfile, os as _os, io, contextlib
        for bad in ("inf", "nan"):
            fd, p = tempfile.mkstemp(suffix=".csv")
            with _os.fdopen(fd, "w") as f:
                f.write(f"date,soil_moisture\n2026-06-01,{bad}\n")
            days = [ds(date="2026-06-01")]
            try:
                with contextlib.redirect_stderr(io.StringIO()):
                    fre.apply_sensor_csv(days, p)
                self.assertIsNone(days[0].soil_moisture)  # inf/nan never stored
            finally:
                _os.remove(p)

    def test_treatment_window_forward_only(self):
        days = [ds(date="2026-06-01", precip_mm=0, max_wind=5),   # past, would be a window
                ds(date="2026-06-05", precip_mm=0, max_wind=5)]   # today onward
        fre.AS_OF = "2026-06-05"
        try:
            a = fre.treatment_window(days)
            info = [x for x in a if x.severity == Severity.INFO]
            self.assertTrue(info and info[0].date == "2026-06-05")  # not the past 06-01
        finally:
            fre.AS_OF = None

    def test_empty_render_does_not_crash(self):
        self.assertIn("no daily data", fre.render_report("X", 0, 0, [], ["heat_stress"], [], False))
        self.assertIn("no daily data", fre.render_digest("X", 0, 0, [], ["heat_stress"], [], False))


class TestMainIntegration(unittest.TestCase):
    """End-to-end smoke tests through main() -- the orchestration the unit tests don't reach.
    Demo mode needs no network; the parcels path mocks fetch_weather/geocode."""

    def _run(self, argv):
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = fre.main(argv)
        return rc, buf.getvalue()

    def test_demo_board(self):
        rc, out = self._run(["--demo"])
        self.assertEqual(rc, 0)
        self.assertIn("TERRAWARD", out)
        self.assertIn("OVERALL", out)

    def test_demo_digest(self):
        rc, out = self._run(["--demo", "--digest"])
        self.assertEqual(rc, 0)
        self.assertIn("DIGEST", out)

    def test_imperial_runs(self):
        rc, out = self._run(["--demo", "--units", "imperial"])
        self.assertEqual(rc, 0)

    def test_list_modules(self):
        rc, out = self._run(["--list-modules"])
        self.assertEqual(rc, 0)
        self.assertIn("scab_risk", out)

    def test_export_json_and_csv(self):
        import tempfile, os, json as _j
        for fmt, check in (("json", None), ("csv", None)):
            fd, p = tempfile.mkstemp(suffix="." + fmt)
            os.close(fd)
            try:
                rc, out = self._run(["--demo", "--export", fmt, "--out", p])
                self.assertEqual(rc, 0)
                self.assertTrue(os.path.getsize(p) > 0)
                if fmt == "json":
                    with open(p) as f:
                        _j.load(f)  # must be valid JSON
            finally:
                os.remove(p)

    def test_save_then_history(self):
        import tempfile, os
        fd, db = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            rc1, _ = self._run(["--demo", "--save", "--db", db])
            rc2, out = self._run(["--demo", "--history", "--db", db])
            self.assertEqual((rc1, rc2), (0, 0))
        finally:
            os.remove(db)

    def test_trust_loop_end_to_end(self):
        import tempfile, os
        fd, db = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            self._run(["--demo", "--save", "--db", db])  # records flagged alerts
            rc_s, out_s = self._run(["--report-sighting", "--date", "2026-06-20",
                                     "--observed", "confirmed", "--modules", "late_blight",
                                     "--db", db])
            self.assertEqual(rc_s, 0)
            self.assertIn("Recorded", out_s)
            rc_a, out_a = self._run(["--accuracy", "--db", db])
            self.assertEqual(rc_a, 0)
            self.assertIn("precision", out_a)
        finally:
            os.remove(db)

    def test_parcels_with_mocked_network(self):
        import tempfile, os, json as _j
        days = fre.demo_weather()
        orig_fetch, orig_geo = fre.fetch_weather, fre.geocode
        fre.fetch_weather = lambda lat, lon, pd, fd: days
        fre.geocode = lambda place: (50.9, 4.3, place)
        fd, pf = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w") as f:
            _j.dump({"farm": "T", "parcels": [
                {"name": "A", "lat": 50.9, "lon": 4.3, "modules": ["heat_stress"]},
                {"name": "B", "place": "Meise", "modules": ["frost_risk"]}]}, f)
        try:
            rc, out = self._run(["--parcels", pf, "--digest"])
            self.assertEqual(rc, 0)
            self.assertIn("FARM", out)
            self.assertIn("A", out)
        finally:
            fre.fetch_weather, fre.geocode = orig_fetch, orig_geo
            os.remove(pf)

    def test_parcels_save_writes_per_parcel_history(self):
        import tempfile, os, json as _j
        days = fre.demo_weather()
        orig_fetch, orig_geo = fre.fetch_weather, fre.geocode
        fre.fetch_weather = lambda lat, lon, pd, fd: days
        fre.geocode = lambda place: (50.9, 4.3, place)
        fd, pf = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w") as f:
            _j.dump({"farm": "T", "parcels": [
                {"name": "FieldA", "lat": 50.9, "lon": 4.3, "modules": ["frost_risk", "heat_stress"]},
                {"name": "FieldB", "lat": 50.9, "lon": 4.3, "modules": ["late_blight"]}]}, f)
        fd2, db = tempfile.mkstemp(suffix=".db")
        os.close(fd2)
        try:
            rc, out = self._run(["--parcels", pf, "--digest", "--save", "--db", db])
            self.assertEqual(rc, 0)
            self.assertIn("saved", out)
            import sqlite3
            c = sqlite3.connect(db)
            tbl = next(t for (t,) in c.execute("SELECT name FROM sqlite_master WHERE type='table'")
                       if "location" in [d[1] for d in c.execute(f"PRAGMA table_info({t})")])
            names = {loc for (loc,) in c.execute(f"SELECT DISTINCT location FROM {tbl}")}
            c.close()
            self.assertIn("FieldA", names)  # each parcel saved under its own name
        finally:
            fre.fetch_weather, fre.geocode = orig_fetch, orig_geo
            os.remove(pf)
            os.remove(db)

    def test_unknown_module_errors_cleanly(self):
        rc, out = self._run(["--demo", "--modules", "not_a_real_module"])
        self.assertEqual(rc, 1)  # clean non-zero exit, not a crash


class TestConsistencyGuards(unittest.TestCase):
    def test_version_matches_pyproject(self):
        import os, re
        here = os.path.dirname(os.path.abspath(fre.__file__))
        path = os.path.join(here, "pyproject.toml")
        if not os.path.exists(path):
            self.skipTest("pyproject.toml not alongside terraward.py")
        with open(path) as f:
            m = re.search(r'version\s*=\s*"([^"]+)"', f.read())
        self.assertIsNotNone(m, "no version in pyproject.toml")
        self.assertTrue(m.group(1).startswith(fre.VERSION),
                        f"pyproject {m.group(1)} != VERSION {fre.VERSION}")

    def test_engine_output_is_ascii(self):
        days = fre.demo_weather()
        enabled = [s.key for s in fre._REGISTRY]
        alerts = fre.run_modules(days, enabled)
        # all three engine renderers must stay pure ASCII (terminal-safe, matching the convention)
        fre.render_report("Farm", 50.9, 4.3, days, enabled, alerts, True).encode("ascii")
        fre.render_digest("Farm", 50.9, 4.3, days, enabled, alerts, True).encode("ascii")
        fre.render_farm("Farm", [("P", 50.9, 4.3, days, alerts, enabled)], True, True).encode("ascii")

    def test_banner_reflects_version(self):
        out = fre.render_report("X", 0, 0, fre.demo_weather(), [], [], True)
        self.assertIn(f"TERRAWARD v{fre.VERSION}", out)


if __name__ == "__main__":
    unittest.main()
