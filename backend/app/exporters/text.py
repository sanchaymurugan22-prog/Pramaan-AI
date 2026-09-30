"""Plain text (.txt) for the social posts: the LinkedIn post and the X thread (numbered 1/5, 2/5 ...).

The post itself sits between two lines of dashes, so it is easy to copy. Above it: the job
details (and TLP label if set); below it: "AI-assisted · pending human approval" and a
placeholder line for the verification link / QR code (added in Stage 7).
"""

from pathlib import Path

from app.exporters.common import FOOTER, ExportInfo, text_of, texts

RULE = "-" * 60


def write_txt(info: ExportInfo, content: dict, path: Path) -> Path:
    path.write_text(post_text(info, content), encoding="utf-8")
    return path


def post_text(info: ExportInfo, content: dict) -> str:
    if info.output_type == "x_thread":
        tweets = [text_of(t) for t in content.get("tweets", []) if text_of(t)]
        body = "\n\n".join(f"{number}/{len(tweets)} {tweet}" for number, tweet in enumerate(tweets, start=1))
    else:
        body = "\n\n".join(texts(content.get("paragraphs")))
        hashtags = " ".join(f"#{tag.lstrip('#')}" for tag in content.get("hashtags", []) if tag)
        if hashtags:
            body += "\n\n" + hashtags

    header = [
        f"Pramaan AI · {info.output_label}",
        f"Job #{info.job_id}: {info.job_title}",
        f"Prepared: {info.date}",
    ]
    if info.tlp_label:
        header.append(f"Sharing label: {info.tlp_label}")
    footer = [FOOTER, "[QR code / verification link: added when signed]"]
    return "\n".join([*header, RULE, body, RULE, *footer]) + "\n"
