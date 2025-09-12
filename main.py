#!/usr/bin/env python3
# make_chapters.py
#
# Detects "chapter N" with Vosk PHRASE-ONLY grammar, confirms with SILENCE-GATING,
# enforces MIN-GAP and MIN-DURATION to avoid false positives / tiny chunks,
# tags MP3s (ID3), optional .m4b with chapters, and supports a "back matter" trigger.
#
# Example:
#   python3 make_chapters.py \
#     --model-path /models/vosk-model-small-en-us-0.15 \
#     --album "War and Peace" --artist "Leo Tolstoy (read by X)" \
#     --back-trigger "this concludes the reading of" \
#     --min-chapter-gap 90 --min-chapter-duration 180 \
#     --silence-threshold -38 --silence-min 0.35 --silence-pre 0.6 --silence-post 0.8 \
#     --make-m4b

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


# ----------------------------
# Subprocess helpers
# ----------------------------
def check_binary(name):
    path = shutil.which(name)
    if not path:
        print(f"ERROR: '{name}' not found in PATH. Please install it.", file=sys.stderr)
        sys.exit(1)
    return path


def run(cmd, check=True, capture=False, text=True, stderr_to_stdout=False):
    try:
        if capture:
            if stderr_to_stdout:
                res = subprocess.run(
                    cmd,
                    check=check,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=text,
                )
                return res.stdout
            else:
                res = subprocess.run(
                    cmd,
                    check=check,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=text,
                )
                return res.stdout, res.stderr
        else:
            subprocess.run(cmd, check=check)
    except subprocess.CalledProcessError as e:
        print(f"Command failed: {' '.join(cmd)}", file=sys.stderr)
        sys.exit(e.returncode)


def ffprobe_duration(path: Path) -> float:
    out = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=nw=1:nk=1",
            str(path),
        ],
        check=True,
        capture=True,
        text=True,
        stderr_to_stdout=True,
    )
    try:
        return float(out.strip())
    except:
        return 0.0


def build_concat_list(mp3_dir: Path) -> str:
    files = sorted(mp3_dir.glob("*.mp3"))
    files = sorted(files, key=lambda p: p.stem.zfill(3))
    if not files:
        print("No MP3 files found in mp3/ . Expected NN.mp3.", file=sys.stderr)
        sys.exit(1)
    return "\n".join([f"file '{str(p.resolve())}'" for p in files])


# ----------------------------
# ID3 & ffmetadata
# ----------------------------
def tag_mp3(
    path: Path,
    album: str,
    artist: str,
    title: str,
    track_no: int,
    total_tracks: int,
    genre: str,
    year: str | None,
    cover_path: Path | None,
):
    from mutagen.easyid3 import EasyID3
    from mutagen.id3 import ID3, APIC, error
    from mutagen.mp3 import MP3

    try:
        audio = EasyID3(str(path))
    except Exception:
        audio_raw = MP3(str(path))
        audio_raw.add_tags()
        audio = EasyID3(str(path))
    audio["album"] = album
    audio["artist"] = artist
    audio["title"] = title
    audio["tracknumber"] = f"{track_no}/{total_tracks}"
    audio["genre"] = genre
    if year:
        audio["date"] = year
    audio.save()
    if cover_path and cover_path.exists():
        try:
            audio2 = ID3(str(path))
            img = cover_path.read_bytes()
            mime = (
                "image/jpeg"
                if cover_path.suffix.lower() in [".jpg", ".jpeg"]
                else "image/png"
            )
            audio2.add(APIC(encoding=3, mime=mime, type=3, desc="Cover", data=img))
            audio2.save(v2_version=3)
        except error:
            pass


def write_ffmetadata(
    ffmeta_path: Path,
    album: str,
    artist: str,
    genre: str,
    year: str | None,
    chapters: list,
):
    lines = [";FFMETADATA1"]
    if album:
        lines.append(f"title={album}")
    if artist:
        lines.append(f"artist={artist}")
    if genre:
        lines.append(f"genre={genre}")
    if year:
        lines.append(f"date={year}")
    for ch in chapters:
        lines.append("[CHAPTER]")
        lines.append("TIMEBASE=1/1000")
        lines.append(f"START={int(ch['start_ms'])}")
        lines.append(f"END={int(ch['end_ms'])}")
        lines.append(f"title={ch['title'].replace('=', r'\\=')}")
    ffmeta_path.write_text("\n".join(lines), encoding="utf-8")


# ----------------------------
# Phrase generators (EN/RU)
# ----------------------------
def english_cardinal(n: int) -> str:
    units = ["", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]
    teens = [
        "ten",
        "eleven",
        "twelve",
        "thirteen",
        "fourteen",
        "fifteen",
        "sixteen",
        "seventeen",
        "eighteen",
        "nineteen",
    ]
    tens = [
        "",
        "",
        "twenty",
        "thirty",
        "forty",
        "fifty",
        "sixty",
        "seventy",
        "eighty",
        "ninety",
    ]
    if n == 0:
        return "zero"
    if n < 10:
        return units[n]
    if 10 <= n < 20:
        return teens[n - 10]
    if n < 100:
        t = n // 10
        u = n % 10
        return tens[t] if u == 0 else f"{tens[t]} {units[u]}"
    if n < 1000:
        h = n // 100
        rem = n % 100
        if rem == 0:
            return f"{units[h]} hundred"
        return f"{units[h]} hundred {english_cardinal(rem)}"
    return str(n)


def english_ordinal_basic(n: int) -> str | None:
    base = {
        1: "first",
        2: "second",
        3: "third",
        4: "fourth",
        5: "fifth",
        6: "sixth",
        7: "seventh",
        8: "eighth",
        9: "ninth",
        10: "tenth",
        11: "eleventh",
        12: "twelfth",
        13: "thirteenth",
        14: "fourteenth",
        15: "fifteenth",
        16: "sixteenth",
        17: "seventeenth",
        18: "eighteenth",
        19: "nineteenth",
        20: "twentieth",
        30: "thirtieth",
        40: "fortieth",
        50: "fiftieth",
        60: "sixtieth",
        70: "seventieth",
        80: "eightieth",
        90: "ninetieth",
        100: "hundredth",
    }
    if n in base:
        return base[n]
    if n < 100:
        t = (n // 10) * 10
        u = n % 10
        tail = english_ordinal_basic(u)
        if t in base and tail:
            return f"{english_cardinal(t)} {tail}"
    if n < 1000:
        h = (n // 100) * 100
        rem = n % 100
        if rem == 0 and h in base:
            return base[h]
        if h:
            tail = english_ordinal_basic(rem) or english_cardinal(rem)
            return f"{english_cardinal(h)} {tail}"
    return None


def russian_cardinal(n: int) -> str:
    units = [
        "",
        "один",
        "два",
        "три",
        "четыре",
        "пять",
        "шесть",
        "семь",
        "восемь",
        "девять",
    ]
    teens = [
        "десять",
        "одиннадцать",
        "двенадцать",
        "тринадцать",
        "четырнадцать",
        "пятнадцать",
        "шестнадцать",
        "семнадцать",
        "восемнадцать",
        "девятнадцать",
    ]
    tens = [
        "",
        "десять",
        "двадцать",
        "тридцать",
        "сорок",
        "пятьдесят",
        "шестьдесят",
        "семьдесят",
        "восемьдесят",
        "девяносто",
    ]
    hundreds = [
        "",
        "сто",
        "двести",
        "триста",
        "четыреста",
        "пятьсот",
        "шестьсот",
        "семьсот",
        "восемьсот",
        "девятьсот",
    ]
    if n == 0:
        return "ноль"
    if n < 10:
        return units[n]
    if 10 <= n < 20:
        return teens[n - 10]
    if n < 100:
        t = n // 10
        u = n % 10
        return tens[t] if u == 0 else f"{tens[t]} {units[u]}".strip()
    if n < 1000:
        h = n // 100
        rem = n % 100
        return (
            hundreds[h]
            if rem == 0
            else f"{hundreds[h]} {russian_cardinal(rem)}".strip()
        )
    return str(n)


def russian_ordinal_basic(n: int) -> str | None:
    base = {
        1: "первая",
        2: "вторая",
        3: "третья",
        4: "четвертая",
        5: "пятая",
        6: "шестая",
        7: "седьмая",
        8: "восьмая",
        9: "девятая",
        10: "десятая",
    }
    return base.get(n)


def build_phrase_map(
    language: str, trigger: str, max_chapters: int, include_ordinals: bool
):
    phrases = []
    spoken_to_int = {}
    if language == "ru":
        for n in range(1, max_chapters + 1):
            spoken = russian_cardinal(n)
            phrases.append(f"{trigger} {spoken}")
            spoken_to_int[spoken] = n
            if include_ordinals:
                ordw = russian_ordinal_basic(n)
                if ordw:
                    phrases.append(f"{trigger} {ordw}")
                    spoken_to_int[ordw] = n
    else:
        for n in range(1, max_chapters + 1):
            spoken = english_cardinal(n)
            phrases.append(f"{trigger} {spoken}")
            spoken_to_int[spoken] = n
            if include_ordinals:
                ordw = english_ordinal_basic(n)
                if ordw:
                    phrases.append(f"{trigger} {ordw}")
                    spoken_to_int[ordw] = n
    phrases.append(trigger)  # bare "chapter"/"глава"
    return phrases, spoken_to_int


# ----------------------------
# Silence detection & gating
# ----------------------------
def detect_silences(ffmpeg_bin, audio_path: Path, noise_db: float, min_dur: float):
    """
    Returns list of (start, end) silence intervals using ffmpeg silencedetect.
    """
    cmd = [
        ffmpeg_bin,
        "-hide_banner",
        "-nostats",
        "-i",
        str(audio_path),
        "-af",
        f"silencedetect=noise={noise_db}dB:d={min_dur}",
        "-f",
        "null",
        "-",
    ]
    out = run(cmd, check=True, capture=True, text=True, stderr_to_stdout=True)
    silences = []
    last_start = None
    for line in out.splitlines():
        line = line.strip()
        if "silence_start:" in line:
            try:
                last_start = float(line.split("silence_start:")[1].strip())
            except:
                pass
        elif "silence_end:" in line and "silence_duration:" in line:
            try:
                parts = line.split()
                # formats like: "silence_end: 12.345 | silence_duration: 1.234"
                end = float(parts[1])
                # duration = float(parts[4])  # not needed
                if last_start is None:
                    # sometimes ffmpeg emits silence_end first; guard
                    start = end  # degenerate
                else:
                    start = last_start
                silences.append((start, end))
                last_start = None
            except:
                pass
    # Normalize & sort
    silences = [(max(0.0, s), max(s, e)) for s, e in silences]
    silences.sort(key=lambda x: x[0])
    return silences


def build_silence_index(silences):
    """
    Build arrays of starts and ends for binary search.
    """
    starts = [s for s, _ in silences]
    ends = [e for _, e in silences]
    return starts, ends


def nearest_silence_bounds(t_start, t_end, silences, starts, ends):
    """
    Find nearest preceding silence end and nearest following silence start
    around [t_start, t_end]. Returns (prev_end, next_start).
    """
    import bisect

    # previous silence end: max end <= t_start
    idx_end = bisect.bisect_right(ends, t_start) - 1
    prev_end = ends[idx_end] if 0 <= idx_end < len(ends) else None
    # next silence start: min start >= t_end
    idx_start = bisect.bisect_left(starts, t_end)
    next_start = starts[idx_start] if 0 <= idx_start < len(starts) else None
    return prev_end, next_start


def passes_silence_gate(t_start, t_end, silences, starts, ends, pre_win, post_win):
    """
    Accept if a silence ends within pre_win before t_start AND
    a silence starts within post_win after t_end.
    """
    prev_end, next_start = nearest_silence_bounds(
        t_start, t_end, silences, starts, ends
    )
    pre_ok = (prev_end is not None) and ((t_start - prev_end) <= pre_win)
    post_ok = (next_start is not None) and ((next_start - t_end) <= post_win)
    return pre_ok and post_ok


# ----------------------------
# M4B-only mode
# ----------------------------
def m4b_only_mode(args):
    """Create M4B from existing MP3 collection without chapter detection."""
    mp3_dir = Path(args.m4b_only)
    if not mp3_dir.exists():
        print(f"ERROR: Directory '{mp3_dir}' does not exist.", file=sys.stderr)
        sys.exit(1)

    # Find all MP3 files and sort them
    mp3_files = list(mp3_dir.glob("*.mp3"))
    if not mp3_files:
        print(f"ERROR: No MP3 files found in '{mp3_dir}'.", file=sys.stderr)
        sys.exit(1)

    # Sort by filename (assuming numbered files)
    mp3_files.sort(key=lambda p: p.stem)

    cover_path = Path(args.cover) if args.cover else None

    # Extract chapter information from filenames
    chapters = []
    current_time_ms = 0

    for mp3_file in mp3_files:
        duration = ffprobe_duration(mp3_file)
        if duration <= 0:
            print(f"WARNING: Could not get duration for {mp3_file}", file=sys.stderr)
            continue

        duration_ms = int(duration * 1000)

        # Extract chapter title from filename (remove numbers and extension)
        title = mp3_file.stem
        # Clean up common patterns like "01_chapter_1" -> "Chapter 1"
        title = re.sub(r'^\d+_', '', title)  # Remove leading numbers
        title = title.replace('_', ' ').title()

        chapters.append({
            "start_ms": current_time_ms,
            "end_ms": current_time_ms + duration_ms,
            "title": title
        })

        current_time_ms += duration_ms

    if not chapters:
        print("ERROR: No valid MP3 files with duration found.", file=sys.stderr)
        sys.exit(1)

    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)

        # Create concat file for all MP3s
        concat_file = td_path / "concat.txt"
        concat_list = "\n".join([f"file '{str(p.resolve())}'" for p in mp3_files])
        concat_file.write_text(concat_list, encoding="utf-8")

        # Concatenate all MP3s
        concat_mp3 = td_path / "concat.mp3"
        run([
            "ffmpeg", "-hide_banner", "-y", "-f", "concat", "-safe", "0",
            "-i", str(concat_file), "-c", "copy", str(concat_mp3)
        ])

        # Write ffmetadata
        ffmeta = td_path / "ffmetadata.txt"
        write_ffmetadata(ffmeta, args.album, args.artist, args.genre, args.year, chapters)

        # Create output M4B
        output_file = f"{args.album}.m4b"
        cmd = [
            "ffmpeg", "-hide_banner", "-y",
            "-i", str(concat_mp3),
            "-i", str(ffmeta),
            "-map_metadata", "1",
            "-c:a", "aac",
            "-b:a", args.m4b_bitrate,
            "-f", "ipod"
        ]

        if cover_path and cover_path.exists():
            cmd = [
                "ffmpeg", "-hide_banner", "-y",
                "-i", str(concat_mp3),
                "-i", str(ffmeta),
                "-i", str(cover_path),
                "-map_metadata", "1",
                "-map", "0:a:0",
                "-map", "2:v:0",
                "-c:a", "aac",
                "-b:a", args.m4b_bitrate,
                "-disposition:v:0", "attached_pic",
                "-metadata:s:v", "title=cover",
                "-metadata:s:v", "comment=Cover (front)",
                "-vn",
                "-f", "ipod"
            ]

        run(cmd + [output_file])
        print(f"Created M4B audiobook: {output_file}")
        print(f"Chapters: {len(chapters)}")


# ----------------------------
# Main
# ----------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Detect chapters with phrase-only grammar + silence gating; split & tag MP3s; optional .m4b; back-matter trigger."
    )
    # IO
    parser.add_argument("--model-path", required=False)
    parser.add_argument("--mp3-dir", default="mp3")
    parser.add_argument("--out-dir", default="book")
    # Language / grammar
    parser.add_argument("--language", choices=["en", "ru"], default="en")
    parser.add_argument(
        "--trigger",
        default=None,
        help="Chapter trigger (default en:'chapter', ru:'глава').",
    )
    parser.add_argument(
        "--max-chapters",
        type=int,
        default=120,
        help="Maximum number of chapters to detect.",
    )
    parser.add_argument(
        "--include-ordinals",
        action="store_true",
        help="Include ordinal numbers in chapter detection.",
    )
    parser.add_argument(
        "--phrases-file", default=None, help="Custom phrases (one per line)."
    )
    parser.add_argument(
        "--conf-min",
        type=float,
        default=0.35,
        help="Minimum confidence score for chapter detection.",
    )
    parser.add_argument(
        "--sequential-chapters",
        action="store_true",
        help="Enforce sequential chapter numbering (1, 2, 3, ...) and filter out non-sequential detections.",
    )
    # False-positive controls
    parser.add_argument(
        "--min-chapter-gap",
        type=float,
        default=90.0,
        help="Seconds between chapter detections (debounce).",
    )
    parser.add_argument(
        "--min-chapter-duration",
        type=float,
        default=120.0,
        help="Minimum seconds per chapter segment. Shorter segments are merged/dropped.",
    )
    # Silence detector tuning
    parser.add_argument(
        "--silence-threshold",
        type=float,
        default=-38.0,
        help="dB threshold for silencedetect (e.g., -35 .. -45).",
    )
    parser.add_argument(
        "--silence-min",
        type=float,
        default=0.35,
        help="Minimum silence duration (sec) for detector.",
    )
    parser.add_argument(
        "--silence-pre",
        type=float,
        default=0.6,
        help="Require a silence end within this many seconds BEFORE the trigger.",
    )
    parser.add_argument(
        "--silence-post",
        type=float,
        default=0.8,
        help="Require a silence start within this many seconds AFTER the phrase end.",
    )
    # Back matter
    parser.add_argument(
        "--back-trigger", default=None, help="Phrase marking start of back matter."
    )
    # Tagging
    parser.add_argument("--album", required=True)
    parser.add_argument("--artist", required=True)
    parser.add_argument("--year", default=None)
    parser.add_argument("--genre", default="Audiobook")
    parser.add_argument("--cover", default=None)
    # Output
    parser.add_argument("--make-m4b", action="store_true")
    parser.add_argument("--m4b-bitrate", default="80k")
    parser.add_argument(
        "--m4b-only",
        help="Create M4B from existing MP3 collection (path to directory with numbered MP3s). Skips chapter detection.",
    )
    # Analysis
    parser.add_argument("--sample-rate", type=int, default=16000)
    args = parser.parse_args()

    ffmpeg = check_binary("ffmpeg")
    check_binary("ffprobe")

    # M4B-only mode: create M4B from existing MP3 collection
    if args.m4b_only:
        m4b_only_mode(args)
        return

    # Validate required arguments for normal mode
    if not args.model_path:
        print("ERROR: --model-path is required for chapter detection mode.", file=sys.stderr)
        sys.exit(1)

    mp3_dir = Path(args.mp3_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cover_path = Path(args.cover) if args.cover else None
    trigger = (
        args.trigger
        if args.trigger
        else ("глава" if args.language == "ru" else "chapter")
    )
    back_trigger = args.back_trigger.strip().lower() if args.back_trigger else None

    # 1) Concat inputs and create analysis WAV
    concat_list = build_concat_list(mp3_dir)
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        concat_file = td_path / "concat.txt"
        concat_file.write_text(concat_list, encoding="utf-8")
        analysis_wav = td_path / "analysis.wav"
        concat_mp3 = td_path / "concat.mp3"

        run(
            [
                ffmpeg,
                "-hide_banner",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_file),
                "-c",
                "copy",
                str(concat_mp3),
            ]
        )
        run(
            [
                ffmpeg,
                "-hide_banner",
                "-y",
                "-i",
                str(concat_mp3),
                "-ac",
                "1",
                "-ar",
                str(args.sample_rate),
                str(analysis_wav),
            ]
        )

        total_duration = ffprobe_duration(concat_mp3)
        if total_duration <= 0:
            print(
                "ERROR: Could not probe duration of concatenated audio.",
                file=sys.stderr,
            )
            sys.exit(1)

        # 2) Silence map (once) for gating
        silences = detect_silences(
            ffmpeg, concat_mp3, args.silence_threshold, args.silence_min
        )
        s_starts, s_ends = build_silence_index(silences)
        print(f">>> Detected {len(silences)} silence intervals")
        if len(silences) > 0:
            print(">>> First few silences:")
            for i, (start, end) in enumerate(silences[:5]):
                print(f"    {i+1}. {start:.1f}s - {end:.1f}s ({end-start:.1f}s duration)")
        else:
            print(">>> ⚠️  No silences detected! Try adjusting --silence-threshold and --silence-min")

        # 3) Grammar phrases
        if args.phrases_file:
            lines = [
                ln.strip().lower()
                for ln in Path(args.phrases_file)
                .read_text(encoding="utf-8")
                .splitlines()
                if ln.strip()
            ]
            grammar_phrases = list(dict.fromkeys(lines))
            grammar_phrases.append(trigger)
            if back_trigger:
                grammar_phrases.append(back_trigger)
            spoken_to_int = {}
        else:
            grammar_phrases, spoken_to_int = build_phrase_map(
                args.language, trigger, args.max_chapters, args.include_ordinals
            )
            if back_trigger:
                grammar_phrases.append(back_trigger)

        grammar_json = json.dumps(grammar_phrases)

        # 4) Vosk recognition (phrase-only)
        try:
            from vosk import Model, KaldiRecognizer
        except ImportError:
            print("Please 'pip install vosk' first.", file=sys.stderr)
            sys.exit(1)
        model = Model(args.model_path)
        rec = KaldiRecognizer(model, args.sample_rate, grammar_json)
        rec.SetWords(True)

        import wave

        wf = wave.open(str(analysis_wav), "rb")
        if wf.getnchannels() != 1 or wf.getframerate() != args.sample_rate:
            print("Internal error: analysis WAV format mismatch.", file=sys.stderr)
            sys.exit(1)

        def parse_phrase(res_obj):
            """
            Returns tuple:
              kind: "chapter" | "back" | None
              t_start: float (start of trigger word)
              t_end:   float (end of last token in phrase)
              chapter_n: int | None
              conf_ok: bool
            """
            text = res_obj.get("text", "").strip().lower()
            words = res_obj.get("result", [])
            if not text or not words:
                return None, None, None, None, True
            conf_ok = all(w.get("conf", 1.0) >= args.conf_min for w in words)
            # phrase time bounds
            t_start = words[0].get("start", None)
            t_end = max((w.get("end", 0.0) for w in words), default=None)
            if not conf_ok or t_start is None or t_end is None:
                return None, None, None, None, conf_ok

            # back trigger exact match
            if back_trigger and text == back_trigger:
                return "back", t_start, t_end, None, conf_ok

            # chapter phrases
            if text == trigger:
                return None, None, None, None, conf_ok  # bare "chapter", ignore
            if text.startswith(trigger + " "):
                tail = text[len(trigger) + 1 :].strip()
                n = spoken_to_int.get(tail)
                if n is None and tail.isdigit():
                    n = int(tail)
                if n:
                    return "chapter", t_start, t_end, n, conf_ok
            return None, None, None, None, conf_ok

        raw_candidates = []  # list of ('chapter'|'back', t_start, t_end, n_or_None)

        while True:
            data = wf.readframes(4000)
            if not data:
                break
            if rec.AcceptWaveform(data):
                res = json.loads(rec.Result())
                kind, ts, te, n, ok = parse_phrase(res)
                if kind and ok:
                    raw_candidates.append((kind, ts, te, n))

        # flush
        res = json.loads(rec.FinalResult())
        kind, ts, te, n, ok = parse_phrase(res)
        if kind and ok:
            raw_candidates.append((kind, ts, te, n))

        # 5) Apply gating & spacing to chapter candidates
        #    - must pass silence gate
        #    - must be at least min-chapter-gap from previous kept mark
        chapters = []
        last_keep_t = -1e12
        chapter_candidates = sorted([c for c in raw_candidates if c[0] == "chapter"], key=lambda x: x[1])

        for kind, ts, te, n in chapter_candidates:
            # Check silence gating
            if len(silences) > 0:
                silence_ok = passes_silence_gate(
                    ts, te, silences, s_starts, s_ends, args.silence_pre, args.silence_post
                )
                if not silence_ok:
                    continue

            # Check minimum gap
            gap = ts - last_keep_t
            if gap < args.min_chapter_gap:
                continue

            chapters.append((ts, te, n))
            last_keep_t = ts

        # Handle duplicate chapter numbers
        if args.sequential_chapters:
            # For sequential chapters, keep all occurrences for now - sequential filtering will choose the right ones
            marks = chapters[:]
            marks.sort(key=lambda x: x[0])
        else:
            # Keep first occurrence per chapter number (earliest timestamp), still sorted by time
            seen_nums = set()
            marks = []
            for ts, te, n in chapters:
                if n not in seen_nums:
                    marks.append((ts, te, n))
                    seen_nums.add(n)
            marks.sort(key=lambda x: x[0])

        # Apply sequential chapter filtering if requested
        if args.sequential_chapters:
            sequential_marks = []
            expected_chapter = 1

            # Sort by timestamp to process in chronological order
            time_sorted_marks = sorted(marks, key=lambda x: x[0])

            for ts, te, n in time_sorted_marks:
                if n == expected_chapter:
                    sequential_marks.append((ts, te, n))
                    expected_chapter += 1

            marks = sequential_marks

        # Back trigger (take first valid one that passes silence gate)
        back_start = None
        for kind, ts, te, _ in sorted(
            [c for c in raw_candidates if c[0] == "back"], key=lambda x: x[1]
        ):
            if passes_silence_gate(
                ts, te, silences, s_starts, s_ends, args.silence_pre, args.silence_post
            ):
                back_start = ts
                break

        # 6) Build segments (preface, chapters, optional back_matter)
        segments = []
        if marks:
            first_t = marks[0][0]
            if first_t > 0.2:
                segments.append((0.0, first_t, "preface"))

            for i in range(len(marks)):
                s = marks[i][0]
                e = marks[i + 1][0] if i + 1 < len(marks) else total_duration
                label = f"chapter_{marks[i][2]}"
                segments.append((s, e, label))

            if back_start is not None:
                # truncate any segment that overlaps back_start and append back_matter
                new_segs = []
                for ss, ee, lab in segments:
                    if back_start <= ss:
                        # drop tail chapters that start after back_start
                        continue
                    if ss < back_start < ee:
                        new_segs.append((ss, back_start, lab))
                    else:
                        new_segs.append((ss, ee, lab))
                segments = new_segs
                if total_duration - back_start >= 1.0:
                    segments.append((back_start, total_duration, "back_matter"))
        else:
            if back_start and back_start > 1.0:
                segments.append((0.0, back_start, "preface"))
                segments.append((back_start, total_duration, "back_matter"))
            else:
                segments.append((0.0, total_duration, "preface"))

        # 7) Enforce minimum chapter duration: drop/merge short slices
        # Strategy: if a segment (other than 'preface' and 'back_matter') is shorter than threshold,
        # drop its boundary by merging it into the previous kept segment.
        cleaned = []
        for seg in segments:
            ss, ee, lab = seg
            dur = ee - ss
            if lab.startswith("chapter_") and dur < args.min_chapter_duration:
                # merge: extend previous if exists, else skip (will be absorbed by following)
                if cleaned:
                    pss, pee, plab = cleaned[-1]
                    cleaned[-1] = (
                        pss,
                        ee,
                        plab,
                    )  # absorb short chapter into previous segment
                else:
                    # no previous: defer to next (skip adding now; next will start from same ss)
                    continue
            else:
                cleaned.append(seg)
        # Optional second pass: if first kept after merge is still shorter (edge cases), drop it
        segments = []
        for seg in cleaned:
            ss, ee, lab = seg
            if lab.startswith("chapter_") and (ee - ss) < max(
                1.0, args.min_chapter_duration * 0.5
            ):
                # absorb forward if possible
                continue
            segments.append(seg)

        # Drop microscopic fragments
        segments = [s for s in segments if (s[1] - s[0]) >= 1.0]

        # 8) Export MP3s + ID3
        out_dir.mkdir(parents=True, exist_ok=True)
        total_tracks = len(segments)
        for idx, (ss, ee, label) in enumerate(segments, start=1):
            out_name = f"{idx-1:02d}_{label}.mp3"
            out_path = out_dir / out_name
            run(
                [
                    "ffmpeg",
                    "-hide_banner",
                    "-y",
                    "-ss",
                    f"{ss:.3f}",
                    "-to",
                    f"{ee:.3f}",
                    "-i",
                    str(concat_mp3),
                    "-c:a",
                    "libmp3lame",
                    "-q:a",
                    "2",
                    str(out_path),
                ]
            )
            human = label.replace("_", " ").title()
            title = f"{args.album} — {human}"
            try:
                tag_mp3(
                    out_path,
                    args.album,
                    args.artist,
                    title,
                    idx,
                    total_tracks,
                    args.genre,
                    args.year,
                    cover_path,
                )
            except Exception as e:
                print(f"Tagging warning for {out_name}: {e}", file=sys.stderr)

        # 9) Optional: .m4b with chapters
        if args.make_m4b:
            chaps = [
                {
                    "start_ms": int(round(ss * 1000)),
                    "end_ms": int(round(ee * 1000)),
                    "title": label.replace("_", " ").title(),
                }
                for ss, ee, label in segments
            ]
            ffmeta = (
                (Path(td) / "ffmetadata.txt")
                if isinstance(td, str)
                else Path(td_path) / "ffmetadata.txt"
            )
            write_ffmetadata(
                ffmeta, args.album, args.artist, args.genre, args.year, chaps
            )
            m4b_path = out_dir / f"{args.album}.m4b"
            cmd = [
                "ffmpeg",
                "-hide_banner",
                "-y",
                "-i",
                str(concat_mp3),
                "-i",
                str(ffmeta),
                "-map_metadata",
                "1",
                "-c:a",
                "aac",
                "-b:a",
                args.m4b_bitrate,
                "-f",
                "ipod",
            ]
            if cover_path and cover_path.exists():
                cmd = [
                    "ffmpeg",
                    "-hide_banner",
                    "-y",
                    "-i",
                    str(concat_mp3),
                    "-i",
                    str(ffmeta),
                    "-i",
                    str(cover_path),
                    "-map_metadata",
                    "1",
                    "-map",
                    "0:a:0",
                    "-map",
                    "2:v:0",
                    "-c:a",
                    "aac",
                    "-b:a",
                    args.m4b_bitrate,
                    "-disposition:v:0",
                    "attached_pic",
                    "-metadata:s:v",
                    "title=cover",
                    "-metadata:s:v",
                    "comment=Cover (front)",
                    "-vn",
                    "-f",
                    "ipod",
                ]
            run(cmd + [str(m4b_path)])
            print(f"Created .m4b with chapters: {m4b_path}")

        print(f"Done. Wrote {total_tracks} MP3 files to: {out_dir.resolve()}")


if __name__ == "__main__":
    main()
