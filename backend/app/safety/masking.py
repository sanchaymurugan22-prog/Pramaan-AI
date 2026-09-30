"""Masking: hidden values never reach the AI, and never reach a public output.

How it works, for every value the operator chose to hide ("Hide in public outputs" or "Hide everywhere"):

  1. mask()     Before ANY text goes to the AI (the source for the fact sheet, the fact sheet for each
                output), the value is replaced by its placeholder: "Call 98765 43210" -> "Call [PHONE-1]".
                So the AI never sees a hidden value, whatever the output.
  2. restore()  After the AI writes, placeholders are turned back in code:
                  internal output (advisory, executive summary, presentation), "Hide in public outputs"
                    -> the real value again ("Call 98765 43210")
                  public output (LinkedIn, X thread, infographic, video), or "Hide everywhere"
                    -> a plain label ("Call [phone number]")
  3. find_leaks()  The "leak check" on every finished output (and after every human edit): if a hidden
                value still appears (written in any spacing, e.g. "9876543210"), the output is blocked
                with a red "Private data found" warning and cannot be downloaded.

"Keep" values are left alone. Attack indicators work the same way (kept in the advisory, left out of
public posts by default).
"""

import re

from app.safety.scanner import KINDS, all_findings

PLACEHOLDER = re.compile(r"\[\s*([A-Z]+(?:-[A-Z]+)*)-(\d+)\s*\]")


def finding_pattern(finding: dict) -> str:
    """A regular expression that finds this value however it is spaced or written."""
    kind = KINDS[finding["kind"]]
    if kind.compact:
        # every letter / digit, with an optional space, dot or dash between them
        body = r"[\s.\-]?".join(re.escape(c) for c in finding["value"])
        prefix = r"(?:(?:\+|00)?91[\s\-]?|0)?" if finding["kind"] == "phone" else ""
        return rf"(?i:(?<![A-Za-z0-9]){prefix}{body}(?![A-Za-z0-9]))"
    if finding["kind"] in ("private_ip", "attacker_ip"):
        body = r"(?:\.|\[\.\])".join(finding["value"].split("."))
        return rf"(?<![\d.]){body}(?!\d|\.\d)"
    if finding["kind"] in ("email", "internal_host", "cve", "hash"):
        return rf"(?i:(?<![\w.\-]){re.escape(finding['value'])}(?![\w\-]))"
    # passwords, keys, markings, GPS: exactly as written (markings are case-sensitive: "RESTRICTED",
    # not the word "restricted" in a normal sentence)
    written = sorted({o["text"] for o in finding.get("occurrences", [])} | {finding["text"]}, key=len, reverse=True)
    return "|".join(rf"(?<!\w){re.escape(w)}(?!\w)" if w[:1].isalnum() else re.escape(w) for w in written)


class Masker:
    """Built from a job's safety report (jobs.safety_json). With no report it changes nothing."""

    def __init__(self, report: dict | None):
        self.findings = all_findings(report)
        self.hidden = [f for f in self.findings if f.get("choice") in ("hide_public", "hide_all")]
        self.by_placeholder = {f["placeholder"]: f for f in self.findings}
        # One pattern for all hidden values; longer values first, so "+91 98765 43210" wins over a part of it
        ordered = sorted(self.hidden, key=lambda f: len(f["text"]), reverse=True)
        self._groups = ordered
        self._pattern = re.compile("|".join(f"({finding_pattern(f)})" for f in ordered)) if ordered else None

    # ---- 1. before the AI ----

    def mask(self, text: str) -> str:
        """Every hidden value -> its placeholder, e.g. [PHONE-1]."""
        if not self._pattern or not text:
            return text

        def swap(match: re.Match) -> str:
            finding = self._groups[match.lastindex - 1] if match.lastindex else None
            return f"[{finding['placeholder']}]" if finding else match.group()

        return self._pattern.sub(swap, text)

    # ---- 2. after the AI ----

    def restore(self, text: str, public: bool) -> str:
        """Placeholders -> the real value (internal outputs, "Hide in public outputs") or a label."""
        if not text or "[" not in text:
            return text

        def swap(match: re.Match) -> str:
            finding = self.by_placeholder.get(f"{match.group(1)}-{match.group(2)}")
            if finding is None:
                return match.group()  # not one of ours: leave it
            if finding.get("choice") == "keep" or (not public and finding.get("choice") == "hide_public"):
                return finding["text"]
            return finding["redaction"]

        return PLACEHOLDER.sub(swap, text)

    def unmask(self, text: str) -> str:
        """Placeholders -> the original values, always. Only used to find a quote in the source."""
        if not text or "[" not in text:
            return text

        def swap(match: re.Match) -> str:
            finding = self.by_placeholder.get(f"{match.group(1)}-{match.group(2)}")
            return finding["text"] if finding else match.group()

        return PLACEHOLDER.sub(swap, text)

    def internal_view(self, text: str) -> str:
        """How internal documents show a text: "Hide everywhere" values become labels, the rest stays."""
        return self.restore(self.mask(text), public=False)

    def restore_json(self, value, public: bool):
        """restore() on every text inside an output's JSON (fact ids are left alone)."""
        if isinstance(value, str):
            return self.restore(value, public)
        if isinstance(value, list):
            return [self.restore_json(item, public) for item in value]
        if isinstance(value, dict):
            return {k: (v if k == "fact_ids" else self.restore_json(v, public)) for k, v in value.items()}
        return value

    def view_json(self, value):
        """internal_view() on every text inside a JSON value (used for the fact sheet)."""
        if isinstance(value, str):
            return self.internal_view(value)
        if isinstance(value, list):
            return [self.view_json(item) for item in value]
        if isinstance(value, dict):
            return {k: (v if k in ("id", "fact_ids", "source_id") else self.view_json(v)) for k, v in value.items()}
        return value

    def indicators_for(self, indicators: dict, public: bool) -> dict:
        """The fact sheet's indicator lists without the ones hidden from this kind of output."""
        hidden = {f["value"].lower() for f in self._hidden_from(public) if f["group"] == "indicator"}
        return {key: [v for v in values if v.lower() not in hidden] for key, values in (indicators or {}).items()}

    # ---- 3. the leak check ----

    def _hidden_from(self, public: bool) -> list[dict]:
        """Values that must not appear in this kind of output."""
        return [f for f in self.hidden if public or f["choice"] == "hide_all"]

    def find_leaks(self, parts: list[tuple[str, str]], public: bool) -> list[dict]:
        """parts: [(where, text)] of one output. Every hidden value found in them."""
        leaks, seen = [], set()
        for finding in self._hidden_from(public):
            pattern = re.compile(finding_pattern(finding))
            for where, text in parts:
                for m in pattern.finditer(text or ""):
                    key = (finding["id"], where, m.group())
                    if key in seen:
                        continue
                    seen.add(key)
                    leaks.append({
                        "finding_id": finding["id"], "kind": finding["kind"], "label": finding["label"],
                        "found": m.group(), "where": where,
                        "choice": finding["choice"],
                    })
        return leaks
