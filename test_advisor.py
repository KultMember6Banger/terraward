"""Tests for the TerraWard advisor (Layer 1 + grounding + languages)."""
import unittest
import terraward as tw
from terraward import Severity, Alert
import advisor


def A(mod, sev, msg, date="2026-06-20", conf=None):
    return Alert(mod, sev, msg, date=date, confidence=conf)


class TestBriefing(unittest.TestCase):
    def test_prioritization(self):
        alerts = [A("frost_risk", Severity.WATCH, "watch"),
                  A("late_blight", Severity.DANGER, "danger", conf="HIGH"),
                  A("heat_stress", Severity.WARNING, "warn"),
                  A("growing_degree_days", Severity.INFO, "info", date=None)]
        b = advisor.build_briefing("X", tw.demo_weather(), alerts)
        self.assertEqual([a.severity for a in b.urgent], [Severity.DANGER, Severity.WARNING])
        self.assertEqual([a.module for a in b.watch], ["frost_risk"])
        self.assertEqual([a.module for a in b.facts], ["growing_degree_days"])

    def test_all_clear(self):
        b = advisor.build_briefing("X", tw.demo_weather(), [A("gdd", Severity.INFO, "i", date=None)])
        self.assertIn("All clear", b.headline)

    def test_render_contains_actions(self):
        text = advisor.render_briefing(advisor.build_briefing(
            "X", tw.demo_weather(), [A("late_blight", Severity.DANGER, "scout now", conf="HIGH")]))
        self.assertIn("DO SOMETHING", text)
        self.assertIn("Potato late blight", text)


class TestLanguages(unittest.TestCase):
    def test_ui_string_translation_and_fallback(self):
        self.assertEqual(advisor._t("do", "nl"), "ONDERNEEM ACTIE:")     # translated
        self.assertEqual(advisor._t("do", "xx"), "DO SOMETHING:")        # unknown lang -> English

    def test_render_uses_language(self):
        b = advisor.build_briefing("X", tw.demo_weather(),
                                   [A("late_blight", Severity.DANGER, "scout now")])
        self.assertIn("ONDERNEEM ACTIE", advisor.render_briefing(b, "nl"))

    def test_system_prompt_carries_language(self):
        self.assertIn("Dutch", advisor.build_system_prompt("Dutch"))

    def test_ask_passes_language_to_model(self):
        out = advisor.ask("q", "ctx", runner=lambda s, c, q: s, language="Ukrainian")
        self.assertIn("Ukrainian", out)


class TestGrounding(unittest.TestCase):
    def test_context_contains_verified_facts(self):
        b = advisor.build_briefing("X", tw.demo_weather(),
                                   [A("late_blight", Severity.DANGER, "scout now", conf="HIGH")])
        ctx = advisor.build_grounding_context(b, tw.demo_weather(), tw.CONFIG)
        self.assertIn("scout now", ctx)
        self.assertIn("ACTIVE THRESHOLDS", ctx)

    def test_ask_falls_back_without_model(self):
        self.assertIn("not configured", advisor.ask("why?", "ctx", runner=None))


class TestAdvisorFixes(unittest.TestCase):
    def test_all_engine_modules_have_labels(self):
        missing = [s.key for s in tw._REGISTRY if s.key not in advisor.LABELS]
        self.assertEqual(missing, [], f"modules missing advisor labels: {missing}")

    def test_grounding_none_not_duplicated(self):
        b = advisor.build_briefing("X", tw.demo_weather(), [])  # no alerts, no facts
        ctx = advisor.build_grounding_context(b, tw.demo_weather(), {})
        self.assertEqual(ctx.count("- none"), 2)  # exactly one per empty section

    def test_output_is_ascii(self):
        b = advisor.build_briefing("X", tw.demo_weather(),
                                   [A("scab_risk", Severity.WATCH, "watch scab")])
        advisor.render_briefing(b).encode("ascii")  # raises if any non-ASCII slipped in

    def test_empty_days_safe(self):
        b = advisor.build_briefing("X", [], [])
        self.assertEqual(b.window, ("n/a", "n/a"))


class TestAdvisorCli(unittest.TestCase):
    """Smoke tests through advisor._cli() in offline demo mode."""

    def _run(self, argv):
        import io, contextlib, sys
        old = sys.argv
        sys.argv = ["advisor.py"] + argv
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                rc = advisor._cli()
        finally:
            sys.argv = old
        return rc, buf.getvalue()

    def test_demo_briefing(self):
        rc, out = self._run(["--demo"])
        self.assertEqual(rc, 0)
        self.assertIn("BRIEFING", out)
        self.assertIn("Hayward", out)

    def test_demo_dutch(self):
        rc, out = self._run(["--demo", "--lang", "nl"])
        self.assertEqual(rc, 0)
        self.assertIn("ONDERNEEM ACTIE", out)

    def test_unknown_language_falls_back(self):
        rc, out = self._run(["--demo", "--lang", "xx"])
        self.assertEqual(rc, 0)
        self.assertIn("DO SOMETHING", out)  # English fallback

    def test_show_grounding(self):
        rc, out = self._run(["--demo", "--show-grounding"])
        self.assertEqual(rc, 0)
        self.assertIn("GROUNDING CONTEXT", out)
        self.assertIn("ACTIVE THRESHOLDS", out)

    def test_ask_without_model_defers(self):
        rc, out = self._run(["--demo", "--ask", "why?"])
        self.assertEqual(rc, 0)
        self.assertIn("not configured", out)


if __name__ == "__main__":
    unittest.main()
