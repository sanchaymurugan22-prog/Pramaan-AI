"""The video package as sound and moving picture (Stage 8): narration audio (.mp3) and a video (.mp4).

Narration   every sentence of every scene's narration is read aloud (app/lang/tts.py: Piper voices, macOS
            voices, or "audio not available" for languages without a voice), so the length of each sentence
            is known exactly. The .mp3 is all of it, with short pauses.
Video       one 1280 x 720 picture per sentence: the scene's on-screen text, the picture description as a
            storyboard note, and the sentence as a caption burned into the picture (it can be watched with the
            sound off, as most social media videos are). A soft subtitle track is added as well. Then a closing
            picture with the QR code (or its empty box until signed). ffmpeg (imageio-ffmpeg) puts the pictures
            and the narration together. Without a voice the video is silent, timed at 2.5 words a second.

Nothing here needs the AI. The sound of each sentence is kept in memory for a while, so downloading the
.mp3 and then the .mp4 reads the narration only once.
"""

import hashlib
import io
import re
from collections import OrderedDict
from dataclasses import dataclass

from PIL import Image, ImageDraw

from app.exporters.common import TLP_TEXT_COLOURS, ExportInfo, rgb
from app.exporters.infographic import _fit_font, _font, _shorten, _wrap
from app.exporters.shaped import ShapedDraw
from app.lang import audio, tts

W, H = 1280, 720
PAD = 64
WORDS_PER_SECOND = 2.5   # the same reading speed as the storyboard times (generate.py)
PAUSE = 0.35             # seconds of silence between sentences
SCENE_PAUSE = 0.6        # ... and between scenes

_cache: "OrderedDict[str, bytes]" = OrderedDict()  # sentence audio by (voice, language, text)


@dataclass
class Line:
    scene: int           # 0-based scene number
    text: str            # the sentence (the caption)
    seconds: float       # how long it is shown (and read)


def sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?।۔])\s+", text or "") if s.strip()]


def _speak(text: str, language: str) -> bytes:
    voice = tts.voice_for(language)
    key = hashlib.sha256(f"{voice}|{language}|{text}".encode()).hexdigest()
    if key in _cache:
        _cache.move_to_end(key)
        return _cache[key]
    data, _ = tts.speak(text, language)
    _cache[key] = data
    while len(_cache) > 300:
        _cache.popitem(last=False)
    return data


def narration(info: ExportInfo, content: dict) -> tuple[list[Line], bytes | None]:
    """The lines of the video and (if a voice exists for the language) the whole narration as one WAV."""
    voice = tts.voice_for(info.language)
    lines: list[Line] = []
    parts: list[bytes] = []
    for number, scene in enumerate(content.get("scenes") or []):
        said = sentences(scene.get("narration", "")) or [""]
        for index, sentence in enumerate(said):
            if voice and sentence:
                wav = _speak(sentence, info.language)
                pause = SCENE_PAUSE if index == len(said) - 1 else PAUSE
                parts.append(wav)
                parts.append(audio.wav_bytes([0.0] * int(16000 * pause), 16000))
                seconds = audio.wav_seconds(wav) + pause
            else:
                seconds = max(1.5, len(sentence.split()) / WORDS_PER_SECOND) if sentence else 3.0
            lines.append(Line(number, sentence, seconds))
    if not lines:
        raise ValueError("The video package has no scenes.")
    return lines, (audio.join_wavs(parts, pause=0) if parts else None)


def write_mp3(info: ExportInfo, content: dict, target) -> None:
    if tts.voice_for(info.language) is None:
        raise ValueError(tts.not_available(info.language))
    _, wav = narration(info, content)
    target.write(audio.mp3_from_wav(wav))


def write_mp4(info: ExportInfo, content: dict, target) -> None:
    lines, wav = narration(info, content)
    scenes = content.get("scenes") or []
    frames = [(_frame(info, content, scenes[line.scene], line, len(scenes)), line.seconds) for line in lines]
    frames.append((_closing_frame(info, content), 3.0))
    srt = _subtitles(lines)
    target.write(audio.make_mp4(frames, wav, srt))


def _subtitles(lines: list[Line]) -> str:
    def stamp(seconds: float) -> str:
        ms = round(seconds * 1000)
        return f"{ms // 3_600_000:02d}:{ms // 60_000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"

    out, clock, n = [], 0.0, 0
    for line in lines:
        if line.text:
            n += 1
            out.append(f"{n}\n{stamp(clock)} --> {stamp(clock + line.seconds - 0.1)}\n{line.text}\n")
        clock += line.seconds
    return "\n".join(out)


# ---- pictures ------------------------------------------------------------------------------------------------

def _canvas(info: ExportInfo) -> tuple[Image.Image, ShapedDraw]:
    image = Image.new("RGB", (W, H), rgb("bg"))
    draw = ShapedDraw(ImageDraw.Draw(image), image)
    draw.rectangle((0, 0, W // 3, 8), fill=rgb("saffron"))
    draw.rectangle((2 * W // 3, 0, W, 8), fill=rgb("green"))
    lang = info.language
    office = _shorten(draw, info.office_name, _font("heading", "semibold", 22, lang), W - 2 * PAD - 220)
    draw.text((PAD, 44), office, font=_font("heading", "semibold", 22, lang), fill=rgb("navy"), anchor="lm")
    if info.tlp_label:
        font = _font("heading", "semibold", 20, lang)
        width = draw.textlength(info.tlp_label, font=font) + 24
        draw.rounded_rectangle((W - PAD - width, 28, W - PAD, 60), radius=6, fill=rgb("black"))
        draw.text((W - PAD - width + 12, 44), info.tlp_label, font=font, fill=rgb(TLP_TEXT_COLOURS.get(info.tlp, "FFFFFF")),
                  anchor="lm")
    half = W // 2 - PAD - 12  # the footer on the left half, the job on the right half (translations are longer)
    footer = _fit_font(draw, info.footer, "heading", "semibold", 18, half, lang, smallest=12)
    draw.text((PAD, H - 30), info.footer, font=footer, fill=rgb("saffron_dark"), anchor="lm")
    job = _shorten(draw, f"{info.job_label} · {info.job_title}", _font("body", "regular", 18, lang), half)
    draw.text((W - PAD - draw.textlength(job, font=_font("body", "regular", 18, lang)), H - 30), job,
              font=_font("body", "regular", 18, lang), fill=rgb("muted"), anchor="lm")
    return image, draw


def _centred(draw, text: str, font, y: int, colour: str, width: int, line_height: int, max_lines: int) -> int:
    lines = _wrap(draw, text, font, width)[:max_lines]
    for line in lines:
        draw.text(((W - draw.textlength(line, font=font)) / 2, y), line, font=font, fill=rgb(colour))
        y += line_height
    return y


def _frame(info: ExportInfo, content: dict, scene: dict, line: Line, total: int) -> bytes:
    image, draw = _canvas(info)
    lang = info.language
    label = info.label("Scene {number}", number=line.scene + 1) + f" / {total}"
    draw.text((PAD, 96), label.upper(), font=_font("heading", "semibold", 20, lang), fill=rgb("saffron_dark"))
    if line.scene == 0 and content.get("title"):
        _centred(draw, content["title"], _font("body", "medium", 26, lang), 150, "muted", W - 2 * PAD, 34, 1)
    on_screen = scene.get("on_screen_text", "")
    font = _fit_font(draw, on_screen, "heading", "bold", 64, W - 2 * PAD, lang, smallest=40)
    _centred(draw, on_screen, font, 200, "navy", W - 2 * PAD, 76, 2)
    visual = scene.get("visual", "")
    if visual:  # the picture the video maker should show (a storyboard note)
        box = (PAD + 120, 380, W - PAD - 120, 470)
        draw.rounded_rectangle(box, radius=14, outline=rgb("line_2"), width=2, fill=rgb("card"))
        _centred(draw, visual, _font("body", "regular", 22, lang), 398, "muted", box[2] - box[0] - 40, 28, 2)
    if line.text:  # the caption: the sentence being read now (smaller when it is long, at most 3 lines)
        for size in (30, 27, 24, 22):
            caption_font = _font("body", "semibold", size, lang)
            rows = _wrap(draw, line.text, caption_font, W - 2 * PAD - 60)
            if len(rows) <= (2 if size == 30 else 3):
                break
        rows, step = rows[:3], round(size * 1.45)
        top = H - 70 - step * len(rows) - 16
        draw.rounded_rectangle((PAD, top, W - PAD, H - 62), radius=14, fill=(27, 29, 38))
        y = top + 12
        for row in rows:
            draw.text(((W - draw.textlength(row, font=caption_font)) / 2, y), row, font=caption_font, fill=(255, 255, 255))
            y += step
    return _png(image)


def _closing_frame(info: ExportInfo, content: dict) -> bytes:
    image, draw = _canvas(info)
    lang = info.language
    _centred(draw, content.get("title") or info.output_label, _font("heading", "bold", 44, lang), 150, "navy",
             W - 2 * PAD, 56, 2)
    box = (W // 2 - 110, 290, W // 2 + 110, 510)
    if info.signed:
        qr = Image.open(io.BytesIO(info.qr_png(8))).convert("RGB").resize((box[2] - box[0], box[3] - box[1]), Image.NEAREST)
        image.paste(qr, box[:2])
    else:
        draw.rounded_rectangle(box, radius=16, outline=rgb("line_2"), width=3)
        first, second = info.qr_placeholder
        draw.text((W // 2, 390), first, font=_font("heading", "semibold", 24, lang), fill=rgb("muted"), anchor="mm")
        draw.text((W // 2, 424), second, font=_font("body", "regular", 20, lang), fill=rgb("muted"), anchor="mm")
    scan = info.label("Scan to check this is genuine.")
    _centred(draw, scan, _font("body", "medium", 28, lang), 540, "ink", W - 2 * PAD, 36, 1)
    return _png(image)


def _png(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()
