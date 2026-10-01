"""Version compare (Stage 9A): what changed between two versions of a job, side by side. No AI.

A job's version goes up when it is sent back and submitted again (v1 -> v2), or reopened after it was
approved (Stage 7). Every output keeps all its texts (output_versions), each with the time it was
saved, so the text of each output "as it was in job version k" is the latest text saved before v{k}
was submitted to the reviewer (what the reviewer saw). The current version is the latest text.
Version 0 is the first draft, exactly as the AI wrote it.

For each output, the text fields (segments.py) are matched by their place in the output and compared
word by word: words only in the old version are "removed", words only in the new one "added".
The summary at the top lists numbers that changed ("42 hospitals" -> "57 hospitals"), lists that grew
or shrank (one more recommended action), and quality scores.
"""

import difflib
import re
from dataclasses import dataclass
from datetime import datetime

from app.db import Job, Output, OutputVersion, as_utc
from app.pipeline.output_types import OUTPUT_TYPES
from app.pipeline.segments import segments


class CompareError(Exception):
    """A version that does not exist."""


@dataclass
class Snapshot:
    key: int                 # 0 = first AI draft, 1, 2 ... = job versions
    label: str               # "Version 1", "First AI draft"
    status: str              # approved | sent back | in review | draft | ...
    at: datetime | None      # when it was submitted (or last changed)
    cutoff: datetime | None  # texts saved up to this time belong to it (None: the latest)


STATUS_WORDS = {"approved": "approved", "sent_back": "sent back", "submitted": "in review", "reopened": "draft"}


def snapshots(job: Job) -> list[Snapshot]:
    """Every version of the job that can be compared, oldest first."""
    found = [Snapshot(0, "First AI draft", "written by AI", _first_written(job), None)]
    for number in range(1, job.version + 1):
        reviews = [r for r in job.reviews if r.job_version == number]
        submitted = [r for r in reviews if r.decision == "submitted"]
        decided = [r for r in reviews if r.decision in ("approved", "sent_back")]
        if number < job.version:
            if not submitted:  # cannot tell what this version said (should not happen)
                continue
            cutoff = submitted[-1].created_at
            status = STATUS_WORDS[decided[-1].decision] if decided else "in review"
            found.append(Snapshot(number, f"Version {number}", status, as_utc(cutoff), cutoff))
        else:
            status = {"in_review": "in review", "sent_back": "sent back", "approved": "approved"}.get(job.status, "draft")
            found.append(Snapshot(number, f"Version {number}", status, as_utc(job.updated_at), None))
    return found


def _first_written(job: Job) -> datetime | None:
    times = [as_utc(v.created_at) for o in job.outputs for v in o.versions[:1]]
    return min(times) if times else None


def text_at(output: Output, snap: Snapshot) -> tuple[dict | None, int | None, int | None]:
    """(content, output version number, quality score) of an output in this job version."""
    if not output.versions:  # finished before Stage 5: one version only
        return output.content_json, 1 if output.content_json else None, output.quality_score
    if snap.key == 0:
        chosen: OutputVersion | None = output.versions[0]
    elif snap.cutoff is None:
        chosen = output.versions[-1]
    else:
        earlier = [v for v in output.versions if as_utc(v.created_at) <= as_utc(snap.cutoff)]
        chosen = earlier[-1] if earlier else None
    if chosen is None:
        return None, None, None
    return chosen.content_json, chosen.version, chosen.quality_score


# ---- word diff ------------------------------------------------------------------------------------

TOKEN = re.compile(r"\s+|[^\s]+")


def word_diff(old: str, new: str) -> tuple[list[dict], list[dict]]:
    """Two lists of pieces [{text, kind}] (kind: same | removed | added), for the old and the new text."""
    a, b = TOKEN.findall(old or ""), TOKEN.findall(new or "")
    left: list[dict] = []
    right: list[dict] = []
    matcher = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == "equal":
            _add(left, "".join(a[i1:i2]), "same")
            _add(right, "".join(b[j1:j2]), "same")
        else:
            _add(left, "".join(a[i1:i2]), "removed")
            _add(right, "".join(b[j1:j2]), "added")
    return left, right


def _add(pieces: list[dict], text: str, kind: str) -> None:
    if not text:
        return
    if kind != "same" and not text.strip():
        kind = "same"  # changed spaces are not worth marking
    if pieces and pieces[-1]["kind"] == kind:
        pieces[-1]["text"] += text
    else:
        pieces.append({"text": text, "kind": kind})


# ---- numbers and lists that changed -----------------------------------------------------------

NUMBER_WORDS = {w: n for n, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen "
    "seventeen eighteen nineteen twenty".split())}
MONTHS = {"january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
          "november", "december", "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec"}
AMOUNT = re.compile(r"\b(\d[\d,]*(?:\.\d+)?|" + "|".join(NUMBER_WORDS) + r")\s+([a-z][a-z-]{2,})", re.IGNORECASE)

LIST_LABELS = {
    "recommendations": "Recommended actions", "actions_needed": "Actions needed", "steps": "Steps",
    "tweets": "Posts", "slides": "Slides", "scenes": "Scenes", "key_points": "Key points",
    "paragraphs": "Paragraphs", "affected": "Affected", "key_numbers": "Key numbers",
}


def amounts(texts: list[str]) -> dict[str, set[str]]:
    """'42 hospitals in five states' -> {'hospitals': {'42'}, 'states': {'5'}} (dates and years left out)."""
    found: dict[str, set[str]] = {}
    for text in texts:
        for number, unit in AMOUNT.findall(text):
            unit = unit.lower()
            if unit in MONTHS:
                continue
            value = str(NUMBER_WORDS.get(number.lower(), number.replace(",", "")))
            found.setdefault(unit, set()).add(value)
    return found


def number_changes(old_texts: list[str], new_texts: list[str]) -> list[dict]:
    """Things counted differently in the two versions: [{label: 'Hospitals', before: '42', after: '57'}]."""
    old, new = amounts(old_texts), amounts(new_texts)
    changes = []
    for unit in old.keys() & new.keys():
        if old[unit] != new[unit] and len(old[unit]) == 1 and len(new[unit]) == 1:
            changes.append({"label": unit.capitalize(), "before": next(iter(old[unit])), "after": next(iter(new[unit]))})
    return sorted(changes, key=lambda c: c["label"])


def list_changes(old: dict | None, new: dict | None) -> list[dict]:
    changes = []
    for key, label in LIST_LABELS.items():
        before = len(old.get(key) or []) if isinstance(old, dict) and isinstance(old.get(key), list) else None
        after = len(new.get(key) or []) if isinstance(new, dict) and isinstance(new.get(key), list) else None
        if before is not None and after is not None and before != after:
            changes.append({"label": label, "before": before, "after": after})
    return changes


# ---- the whole comparison --------------------------------------------------------------------------


def compare(job: Job, left: int | None = None, right: int | None = None) -> dict:
    snaps = snapshots(job)
    by_key = {s.key: s for s in snaps}
    if right is None:
        right = job.version
    if left is None:
        left = max((s.key for s in snaps if s.key < right), default=0)
    if left not in by_key or right not in by_key:
        raise CompareError(f"This job has versions {', '.join(str(s.key) for s in snaps)} only.")
    a, b = by_key[left], by_key[right]

    outputs, numbers = [], []
    words = {"added": 0, "removed": 0}
    lists: list[dict] = []
    for output in job.outputs:
        old, old_v, old_score = text_at(output, a)
        new, new_v, new_score = text_at(output, b)
        if old is None and new is None:
            continue
        old_fields = {_key(s.path): s for s in segments(output.type, old or {}) if s.checked}
        new_fields = {_key(s.path): s for s in segments(output.type, new or {}) if s.checked}
        fields = []
        for key in list(dict.fromkeys([*old_fields, *new_fields])):
            before, after = old_fields.get(key), new_fields.get(key)
            l_pieces, r_pieces = word_diff(before.text if before else "", after.text if after else "")
            changed = any(p["kind"] != "same" for p in l_pieces + r_pieces)
            words["removed"] += sum(len(p["text"].split()) for p in l_pieces if p["kind"] == "removed")
            words["added"] += sum(len(p["text"].split()) for p in r_pieces if p["kind"] == "added")
            fields.append({"label": (after or before).label, "path": (after or before).path, "changed": changed,
                           "left": l_pieces, "right": r_pieces})
        # per output, so an output that was not changed does not hide the change in another
        for change in number_changes([s.text for s in old_fields.values()], [s.text for s in new_fields.values()]):
            if change not in numbers:
                numbers.append(change)
        label = OUTPUT_TYPES[output.type]["label"]
        lists += [c | {"output": label} for c in list_changes(old, new)]
        outputs.append({
            "output_id": output.id, "type": output.type, "label": label,
            "changed": any(f["changed"] for f in fields),
            "left": {"version": old_v, "quality_score": old_score},
            "right": {"version": new_v, "quality_score": new_score},
            "fields": fields,
        })

    return {
        "job_id": job.id,
        "versions": [_snap_json(s) for s in snaps],
        "left": _snap_json(a),
        "right": _snap_json(b),
        "outputs": outputs,
        "summary": {
            "outputs_changed": sum(o["changed"] for o in outputs),
            "outputs": len(outputs),
            "words_added": words["added"],
            "words_removed": words["removed"],
            "numbers": numbers,
            "lists": lists,
        },
    }


def _key(path: list) -> str:
    return ".".join(str(p) for p in path)


def _snap_json(s: Snapshot) -> dict:
    return {"key": s.key, "label": s.label, "status": s.status, "at": s.at.isoformat() if s.at else None}
