"""The sharing label (TLP, Traffic Light Protocol 2.0), chosen in the Safety check.

  RED    named people only       public outputs switched off
  AMBER  your organisation       public outputs switched off
  GREEN  wider community         all outputs allowed (hidden values are masked in public ones)
  CLEAR  anyone                  all outputs allowed

Public outputs: LinkedIn post, X thread, infographic, video package (see output_types.py, "public").
Internal outputs (advisory, executive summary, presentation) are allowed with every label.
The label is printed on every exported file.
"""

from app.pipeline.output_types import OUTPUT_TYPES

LEVELS = ["RED", "AMBER", "GREEN", "CLEAR"]

LEVEL_INFO = {
    "RED": {"title": "Named people only", "description": "Public formats are switched off."},
    "AMBER": {"title": "Your organisation", "description": "Shared inside your organisation. Public formats are switched off."},
    "GREEN": {"title": "Wider community", "description": "All formats. Hidden details are masked in public ones."},
    "CLEAR": {"title": "Anyone", "description": "For fully public material."},
}

HIGH_RISK_KINDS = {"aadhaar", "pan", "passport", "bank_account", "password", "api_key", "token", "private_key"}


def public_outputs() -> list[str]:
    return [key for key, spec in OUTPUT_TYPES.items() if spec["public"]]


def switched_off(tlp: str | None) -> dict[str, str]:
    """Public outputs a label does not allow, each with the reason in plain words. {} = all allowed."""
    if tlp == "RED":
        reason = "TLP:RED means only the named people may see this, so public posts are switched off."
    elif tlp == "AMBER":
        reason = "TLP:AMBER means this stays inside your organisation, so public posts are switched off."
    else:
        return {}
    return {key: reason for key in public_outputs()}


def suggest_tlp(findings: list[dict], indicators: list[dict]) -> tuple[str, str]:
    """A label to start from, and why. The operator can always choose another one."""
    markings = sorted({f["value"] for f in findings if f["kind"] == "classification"})
    top = [m for m in markings if m in ("TOP SECRET", "SECRET")]
    if top:
        return "RED", f"The source is marked {top[0]}. Only the named people should see it."

    reasons = []
    if markings:
        reasons.append(f"it is marked {_join(markings)}")
    sensitive = _labels(f for f in findings if f["kind"] in HIGH_RISK_KINDS)
    if sensitive:
        reasons.append(f"it contains {_join(sensitive)}")
    network = _labels(f for f in findings if f["group"] == "network")
    if network:
        reasons.append(f"it shows your internal network ({_join(network)})")
    if reasons:
        return "AMBER", f"Suggested because {'; '.join(reasons)}."

    if findings:
        return "GREEN", (f"Only contact or location details were found ({_join(_labels(findings))}). "
                         "They are hidden in public outputs, so it can be shared more widely.")
    if indicators:
        return "GREEN", ("No private data was found. The attack indicators (addresses, CVE ids, file hashes) "
                         "are meant for the security community.")
    return "CLEAR", "No private data, markings or attack indicators were found."


KEEP_CAPITAL = ("Aadhaar", "PAN", "IFSC", "API", "GPS", "CVE")


def _labels(findings) -> list[str]:
    """Kinds found, as plural words for a sentence, without repeats: ["Aadhaar numbers", "passwords"]."""
    labels = []
    for f in findings:
        label = f["label"]
        label = label + ("es" if label.endswith("ss") else "" if label.endswith("s") else "s")
        if not label.startswith(KEEP_CAPITAL):
            label = label[0].lower() + label[1:]
        if label not in labels:
            labels.append(label)
    return labels


def _join(words: list[str]) -> str:
    """["a", "b", "c"] -> "a, b and c" """
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]
