"""Small audio and video helpers (Stage 8), all offline.

ffmpeg comes inside the imageio-ffmpeg Python package (a ready-made binary for Intel Macs, no Homebrew).
It is used to read any audio or video file for speech-to-text, to make MP3 copies of narration, and to
put storyboard frames and narration together into an MP4.
"""

import io
import subprocess
import tempfile
import wave
from pathlib import Path

import numpy as np


class AudioError(Exception):
    """A friendly message when an audio or video file cannot be read or made."""


def ffmpeg() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:  # the package is missing or has no binary for this computer
        raise AudioError(f"ffmpeg is not available ({exc}). Install the backend packages again.") from exc


def _run(args: list[str], data: bytes | None = None, timeout: float = 600) -> bytes:
    result = subprocess.run([ffmpeg(), "-hide_banner", "-loglevel", "error", *args], input=data,
                            capture_output=True, timeout=timeout)
    if result.returncode != 0:
        raise AudioError("ffmpeg could not process the file: " + result.stderr.decode(errors="replace")[-300:].strip())
    return result.stdout


def wav_bytes(samples, sample_rate: int) -> bytes:
    """Float samples (-1..1) -> a 16-bit mono WAV file."""
    pcm = (np.clip(np.asarray(samples, dtype=np.float32), -1, 1) * 32767).astype("<i2")
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm.tobytes())
    return buffer.getvalue()


def wav_seconds(data: bytes) -> float:
    with wave.open(io.BytesIO(data)) as w:
        return w.getnframes() / w.getframerate()


def join_wavs(parts: list[bytes], pause: float = 0.4) -> bytes:
    """Several WAV files one after another, with a short pause between them (all at the first one's rate)."""
    if not parts:
        raise AudioError("There is no audio to join.")
    with wave.open(io.BytesIO(parts[0])) as w:
        rate = w.getframerate()
    chunks = []
    for part in parts:
        with wave.open(io.BytesIO(part)) as w:
            if w.getframerate() != rate or w.getnchannels() != 1:
                part = to_wav(part, sample_rate=rate)
        with wave.open(io.BytesIO(part)) as w:
            chunks.append(np.frombuffer(w.readframes(w.getnframes()), dtype="<i2"))
        chunks.append(np.zeros(int(rate * pause), dtype="<i2"))
    return wav_bytes(np.concatenate(chunks[:-1]).astype(np.float32) / 32767, rate)


def to_wav(data: bytes, sample_rate: int = 16000) -> bytes:
    """Any audio or video file (mp3, m4a, ogg, wav, mp4 ...) -> 16-bit mono WAV, e.g. for speech-to-text."""
    with tempfile.TemporaryDirectory(prefix="pramaan-audio-") as folder:
        source = Path(folder) / "in"
        source.write_bytes(data)
        return _run(["-i", str(source), "-vn", "-ac", "1", "-ar", str(sample_rate), "-f", "wav", "-"])


def read_samples(data: bytes, sample_rate: int = 16000) -> np.ndarray:
    """Any audio file -> float32 samples at `sample_rate`, mono."""
    with wave.open(io.BytesIO(to_wav(data, sample_rate))) as w:
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")
    return pcm.astype(np.float32) / 32768


def mp3_from_wav(data: bytes) -> bytes:
    return _run(["-f", "wav", "-i", "-", "-codec:a", "libmp3lame", "-q:a", "4", "-f", "mp3", "-"], data)


def make_mp4(frames: list[tuple[bytes, float]], narration_wav: bytes | None, subtitles_srt: str | None = None) -> bytes:
    """frames: [(PNG image, seconds to show it)] -> an H.264 MP4 with the narration as AAC sound.
    The subtitles (optional) are added as a soft subtitle track that players can switch on."""
    if not frames:
        raise AudioError("The video has no frames.")
    with tempfile.TemporaryDirectory(prefix="pramaan-video-") as folder:
        folder = Path(folder)
        listing = []
        for n, (png, seconds) in enumerate(frames):
            (folder / f"f{n}.png").write_bytes(png)
            listing += [f"file 'f{n}.png'", f"duration {max(0.5, seconds):.3f}"]
        listing.append(f"file 'f{len(frames) - 1}.png'")  # the concat demuxer needs the last frame twice
        (folder / "frames.txt").write_text("\n".join(listing) + "\n")
        args = ["-f", "concat", "-safe", "0", "-i", str(folder / "frames.txt")]
        if narration_wav:
            (folder / "voice.wav").write_bytes(narration_wav)
            args += ["-i", str(folder / "voice.wav")]
        if subtitles_srt:
            (folder / "subs.srt").write_text(subtitles_srt, encoding="utf-8")
            args += ["-i", str(folder / "subs.srt")]
        args += ["-map", "0:v"]
        if narration_wav:
            args += ["-map", "1:a", "-c:a", "aac", "-b:a", "96k"]
        if subtitles_srt:
            args += ["-map", f"{2 if narration_wav else 1}:s", "-c:s", "mov_text"]
        # yuv420p + even size: plays everywhere (phones, PowerPoint, browsers); 1 frame per second is enough
        args += ["-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage", "-r", "10", "-pix_fmt", "yuv420p",
                 "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", "-movflags", "+faststart",
                 str(folder / "out.mp4")]
        _run(["-y", *args], timeout=900)
        return (folder / "out.mp4").read_bytes()
