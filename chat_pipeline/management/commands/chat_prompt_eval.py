import json
import math
import time
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from chat_pipeline import prompts
from chat_pipeline.generation import LLMGenerator
from chat_pipeline.llm import FakeLLMClient, LLMUnavailable

CASES = Path(__file__).resolve().parents[2] / "config" / "prompt_eval_cases.json"


class Command(BaseCommand):
    help = ("CHAT-08: run the prompt against a REAL model with fixed cases (costs a few tokens). "
            "Use --fake to check the command itself without an API key.")

    def add_arguments(self, parser):
        parser.add_argument("--fake", action="store_true")
        parser.add_argument("--interval", type=float, default=10.0,
                            help="Seconds between real-model cases (default: 10; increase for lower rate limits).")
        parser.add_argument("--case", action="append", dest="case_names",
                            help="Run only this case name; repeat to select several cases.")

    def handle(self, *args, **opts):
        interval = opts["interval"]
        if not math.isfinite(interval) or interval < 0:
            raise CommandError("--interval must be a finite, non-negative number.")
        cases = json.loads(CASES.read_text(encoding="utf-8"))
        if opts["case_names"]:
            unknown = set(opts["case_names"]) - {case["name"] for case in cases}
            if unknown:
                raise CommandError(f"Unknown case(s): {', '.join(sorted(unknown))}")
            cases = [case for case in cases if case["name"] in opts["case_names"]]
        generator = LLMGenerator(FakeLLMClient()) if opts["fake"] else LLMGenerator()
        failures = 0
        for index, case in enumerate(cases):
            if index and not opts["fake"]:
                time.sleep(interval)
            hits = [{"text": text} for text in case["context"]]
            try:
                answer = generator.generate(case["question"], hits, case["language"])
            except LLMUnavailable as exc:
                raise CommandError(
                    f"Evaluation interrupted at {case['name']}: {exc} "
                    f"Completed {index} of {len(cases)} cases; {failures} prompt checks failed. "
                    "Provider errors are not prompt failures. For HTTP 429, check the provider's "
                    "quota/billing and request limits, then rerun with a larger --interval. "
                    f"Use --case {case['name']} to retry this case."
                ) from exc
            problems = []
            lowered = answer.lower()
            if case.get("expect_no_answer") and not prompts.is_no_answer(answer):
                problems.append("expected NO_ANSWER")
            if not case.get("expect_no_answer") and prompts.is_no_answer(answer):
                problems.append("unexpected NO_ANSWER")
            if case.get("must_contain_any") and not any(t.lower() in lowered for t in case["must_contain_any"]):
                problems.append(f"none of {case['must_contain_any']} found")
            problems += [f"contains forbidden '{t}'" for t in case.get("must_not_contain", []) if t.lower() in lowered]
            if case.get("expect_language") and not prompts.language_matches(answer, case["expect_language"]):
                problems.append(f"not written in {case['expect_language']}")
            failures += bool(problems)
            self.stdout.write(f"{'FAIL' if problems else 'PASS'} {case['name']}: " + ("; ".join(problems) or answer[:80].replace("\n", " ")))
            if problems:
                self.stdout.write(f"  Actual answer: {answer!r}")
        self.stdout.write(f"{len(cases) - failures} passed, {failures} failed")
        if failures:
            raise CommandError("Prompt evaluation failed. Read the FAIL lines above.")
