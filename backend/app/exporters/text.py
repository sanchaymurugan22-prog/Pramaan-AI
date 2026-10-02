"""Plain text (.txt) for the social posts: the LinkedIn post and the X thread (numbered 1/5, 2/5 ...).

The post itself sits between two lines of dashes, so it is easy to copy. Above it: the job
details (and TLP label if set); below it: "AI-assisted · pending human approval" and a
placeholder line for the verification link / QR code (added in Stage 7).
"""

from pathlib import Path

from typing import BinaryIO

from app.exporters.common import ExportInfo, save_text, text_of, texts

RULE = "-" * 60


def write_txt(info: ExportInfo, content: dict, path: Path | BinaryIO) -> Path | BinaryIO:
    save_text(path, post_text(info, content))
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
        f"{info.office_name} · {info.output_label}",
        f"{info.job_label}: {info.job_title}",
        info.label("Prepared: {date}", date=info.date),
    ]
    if info.tlp_label:
        header.append(info.label("Sharing label: {tlp}", tlp=info.tlp_label))
    if info.signed:
        footer = [info.footer, info.label("Check it is genuine: {url}", url=info.verify_url)]
    elif info.language == "en":
        footer = [info.footer, "[QR code / verification link: added when signed]"]
    else:
        footer = [info.footer, f"[{' '.join(info.qr_placeholder)}]"]
    return "\n".join([*header, RULE, body, RULE, *footer]) + "\n"
