import re
import string
import unicodedata
from typing import List, Dict, Tuple
from loguru import logger


class Caption:
    # --- NEW: broader punctuation detection (ASCII + CJK + Unicode P* categories)
    def is_punctuation(self, text: str) -> bool:
        """
        Treat a token as punctuation if every non-space char is punctuation.
        Covers ASCII punctuation, CJK full-width punctuation, and any Unicode
        char with category starting with 'P' (Punctuation).
        """
        if not text:
            return False

        extra_cjk = set("，。、！？；：【】《》（）——…“”‘’、～·「」『』〔〕￥＄％＠＃＊—－‥︰︱︳︴︵︶︷︸︹︺︻︼︽︾︿﹀﹁﹂﹃﹄")
        for ch in text:
            if ch.isspace():
                return False  # token-level: we don't expect spaces inside punctuation tokens
            cat = unicodedata.category(ch)
            if cat.startswith("P") or ch in string.punctuation or ch in extra_cjk:
                continue
            return False
        return True

    
    def create_subtitle_segments_english(
        self, captions: List[Dict], max_length=80, lines=2
    ):
        """
        Breaks up the captions into segments of max_length characters
        on two lines and merge punctuation with the last word
        """

        if not captions:
            return []

        segments = []
        current_segment_texts = ["" for _ in range(lines)]
        current_line = 0
        segment_start_ts = captions[0]["start_ts"]
        segment_end_ts = captions[0]["end_ts"]

        for caption in captions:
            text = caption["text"]
            start_ts = caption["start_ts"]
            end_ts = caption["end_ts"]

            # Update the segment end timestamp
            segment_end_ts = end_ts

            # If the caption is a punctuation, merge it with the current line
            if self.is_punctuation(text):
                if current_line < lines and current_segment_texts[current_line]:
                    current_segment_texts[current_line] += text
                continue

            # If the line is too long, move to the next one
            if (
                current_line < lines
                and len(current_segment_texts[current_line] + text) > max_length
            ):
                current_line += 1

            # If we've filled all lines, save the current segment and start a new one
            if current_line >= lines:
                segments.append(
                    {
                        "text": current_segment_texts,
                        "start_ts": segment_start_ts,
                        "end_ts": segment_end_ts,
                    }
                )

                # Reset for next segment
                current_segment_texts = ["" for _ in range(lines)]
                current_line = 0
                # Add a small gap (0.05s) between segments to prevent overlap
                segment_start_ts = start_ts + 0.05

            # Add the text to the current segment
            if current_line < lines:
                current_segment_texts[current_line] += (
                    " " if current_segment_texts[current_line] else ""
                )
                current_segment_texts[current_line] += text

        # Add the last segment if there's any content
        if any(current_segment_texts):
            segments.append(
                {
                    "text": current_segment_texts,
                    "start_ts": segment_start_ts,
                    "end_ts": segment_end_ts,
                }
            )

        # Post-processing to ensure no overlaps by adjusting end times if needed
        for i in range(len(segments) - 1):
            if segments[i]["end_ts"] >= segments[i + 1]["start_ts"]:
                segments[i]["end_ts"] = segments[i + 1]["start_ts"] - 0.05

        return segments

    def create_subtitle_segments_international(
        self, captions: List[Dict], max_length=80, lines=2
    ):
        """
        Breaks up international captions (full sentences) into smaller segments that fit
        within max_length characters per line, with proper timing distribution.

        Handles both space-delimited languages like English and character-based languages like Chinese.

        Args:
            captions: List of caption dictionaries with text, start_ts, and end_ts
            max_length: Maximum number of characters per line
            lines: Number of lines per segment

        Returns:
            List of subtitle segments
        """
        if not captions:
            return []

        segments = []

        for caption in captions:
            text = caption["text"].strip()
            start_ts = caption["start_ts"]
            end_ts = caption["end_ts"]
            duration = end_ts - start_ts

            # Check if text is using Chinese/Japanese/Korean characters (CJK)
            # For CJK, we'll split by characters rather than words
            is_cjk = any("\u4e00" <= char <= "\u9fff" for char in text)

            parts = []
            if is_cjk:
                # For CJK languages, process character by character
                current_part = ""
                for char in text:
                    if len(current_part + char) > max_length:
                        parts.append(current_part)
                        current_part = char
                    else:
                        current_part += char

                # Add the last part if not empty
                if current_part:
                    parts.append(current_part)
            else:
                # Original word-based splitting for languages with spaces
                words = text.split()
                current_part = ""

                for word in words:
                    # If adding this word would exceed max_length, start a new part
                    if len(current_part + " " + word) > max_length and current_part:
                        parts.append(current_part.strip())
                        current_part = word
                    else:
                        # Add space if not the first word in the part
                        if current_part:
                            current_part += " "
                        current_part += word

                # Add the last part if not empty
                if current_part:
                    parts.append(current_part.strip())

            # Group parts into segments with 'lines' number of lines per segment
            segment_parts = []
            for i in range(0, len(parts), lines):
                segment_parts.append(parts[i : i + lines])

            # Calculate time proportionally based on segment text length
            total_chars = sum(len("".join(part_group)) for part_group in segment_parts)

            current_time = start_ts
            for i, part_group in enumerate(segment_parts):
                # Get character count for this segment group
                segment_chars = len("".join(part_group))

                # Calculate time proportionally, but ensure at least a minimum duration
                if total_chars > 0:
                    segment_duration = (segment_chars / total_chars) * duration
                    segment_duration = max(
                        segment_duration, 0.5
                    )  # Ensure minimum duration of 0.5s
                else:
                    segment_duration = duration / len(segment_parts)

                segment_start = current_time
                segment_end = segment_start + segment_duration

                # Move current time forward for next segment
                current_time = segment_end

                # Create segment with proper text array format for the subtitle renderer
                segment_text = part_group + [""] * (lines - len(part_group))

                segments.append(
                    {
                        "text": segment_text,
                        "start_ts": segment_start,
                        "end_ts": segment_end,
                    }
                )

        # Ensure no overlaps between segments by adjusting end times if needed
        for i in range(len(segments) - 1):
            if segments[i]["end_ts"] >= segments[i + 1]["start_ts"]:
                segments[i]["end_ts"] = segments[i + 1]["start_ts"] - 0.05

        return segments


    # --- FIX: make hex_to_ass intuitive: alpha=0.0 opaque -> &H00BBGGRR&, alpha=1.0 -> &HFF...
    @staticmethod
    def hex_to_ass(hex_color: str, alpha: float = 0.0) -> str:
        """
        Convert a hex color + transparency to ASS &HaaBBGGRR& format.

        :param hex_color: "#RRGGBB" or "RRGGBB" or short "RGB"
        :param alpha: transparency from 0.0 (opaque) to 1.0 (fully transparent)
        :return: "&HaaBBGGRR&"
        """
        hex_color = hex_color.lstrip("#")
        if len(hex_color) == 3:
            hex_color = "".join([c * 2 for c in hex_color])
        if len(hex_color) != 6:
            raise ValueError("hex_color must be 'RRGGBB' or 'RGB'")

        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)

        # ASS alpha: 00=opaque, FF=transparent (we map alpha directly)
        a = int(round(max(0.0, min(1.0, alpha)) * 255))

        aa = f"{a:02X}"
        bb = f"{b:02X}"
        gg = f"{g:02X}"
        rr = f"{r:02X}"
        return f"&H{aa}{bb}{gg}{rr}"

    # --- NEW: helper that returns &HBBGGRR& (no alpha) for override tags like \1c
    @staticmethod
    def hex_to_ass_no_alpha(hex_color: str) -> str:
        hex_color = hex_color.lstrip("#")
        if len(hex_color) == 3:
            hex_color = "".join([c * 2 for c in hex_color])
        if len(hex_color) != 6:
            raise ValueError("hex_color must be 'RRGGBB' or 'RGB'")
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        return f"&H{b:02X}{g:02X}{r:02X}&"

    def create_subtitle(
        self,
        segments,
        dimensions: Tuple[int, int],
        output_path: str,
        font_size=24,
        font_color="#fff",
        shadow_color="#000",
        shadow_transparency=0.1,  # 0 opaque → 1 fully transparent
        shadow_blur=0,
        stroke_color="#000",
        stroke_size=0,
        font_name="Arial",
        font_bold=True,
        font_italic=False,
        subtitle_position="center",
        fade_ms: int = 0,  # --- NEW: optional \fad fade-in/out in milliseconds
    ):
        width, height = dimensions
        bold_value = -1 if font_bold else 0
        italic_value = -1 if font_italic else 0

        position_from_top = 0.2
        if subtitle_position == "center":
            position_from_top = 0.45
        if subtitle_position == "bottom":
            position_from_top = 0.75

        ass_content = """[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{font_size},{font_color},&H000000FF,{stroke_color},&H00000000,{bold},{italic},0,0,100,100,0,0,1,{stroke_size},0,8,20,20,20,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""".format(
            width=width,
            height=height,
            font_size=font_size,
            # Style colors: &HaaBBGGRR& is valid here, so include alpha if desired (we use opaque)
            font_color=self.hex_to_ass(font_color, alpha=0.0),
            stroke_color=self.hex_to_ass(stroke_color, alpha=0.0),
            stroke_size=stroke_size,
            font_name=font_name,
            bold=bold_value,
            italic=italic_value,
        )

        pos_x = int(width / 2)
        pos_y = int(height * position_from_top)

        for segment in segments:
            start_time = self.format_time(segment["start_ts"])
            end_time = self.format_time(segment["end_ts"])

            text_lines = segment["text"]
            formatted_text = ""
            for i, line in enumerate(text_lines):
                if line:
                    if i > 0:
                        formatted_text += "\\N"
                    formatted_text += line

            # --- Build override tags shared by shadow/main
            fad_tag = f"\\fad({fade_ms},{fade_ms})" if fade_ms and fade_ms > 0 else ""
            main_override_tags = f"\\pos({pos_x},{pos_y}){fad_tag}"

            # --- SHADOW: use \1c with NO alpha (&HBBGGRR&) and \1a for transparency
            if shadow_blur > 0 or shadow_transparency > 0.0:
                shadow_pos_x = pos_x + 2
                shadow_pos_y = pos_y + 2
                shadow_color_no_a = self.hex_to_ass_no_alpha(shadow_color)
                # ASS alpha is 00 opaque..FF transparent; shadow_transparency maps directly
                alpha_byte = int(round(max(0.0, min(1.0, shadow_transparency)) * 255))
                alpha_hex = f"{alpha_byte:02X}"

                shadow_override_tags = (
                    f"\\pos({shadow_pos_x},{shadow_pos_y}){fad_tag}"
                    f"\\1c{shadow_color_no_a}\\1a&H{alpha_hex}&\\bord0"
                )
                if shadow_blur > 0:
                    shadow_override_tags += f"\\blur{shadow_blur}"

                shadow_text = f"{{{shadow_override_tags}}}" + formatted_text
                ass_content += f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{shadow_text}\n"

            # --- MAIN text (no color override here; style carries color)
            main_text = f"{{{main_override_tags}}}" + formatted_text
            ass_content += f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{main_text}\n"

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(ass_content)

        logger.debug("subtitle (ass) was created with drop shadow and overrides")

    def format_time(self, seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        centisecs = int(round((seconds % 1) * 100))
        return f"{hours}:{minutes:02d}:{secs:02d}.{centisecs:02d}"

def _parse_vtt_timestamp(ts: str) -> float:
    # Supports "HH:MM:SS.mmm" or "MM:SS.mmm"
    m = re.match(r"(?:(\d{1,2}):)?(\d{2}):(\d{2}\.\d{1,3})$", ts.strip())
    if not m:
        raise ValueError(f"Invalid VTT timestamp: {ts}")
    h = int(m.group(1) or 0)
    mnt = int(m.group(2))
    s = float(m.group(3))
    return h * 3600 + mnt * 60 + s


def parse_webvtt_to_captions(vtt_text: str) -> List[Dict]:
    """
    Parse a simple WebVTT string into caption items of:
    {"text": "...", "start_ts": float, "end_ts": float}

    - Combines multi-line block text into a single string separated by spaces.
    - Ignores cue numbers, blank lines, 'WEBVTT' header.
    """
    lines = [ln.rstrip("\n") for ln in vtt_text.splitlines()]
    captions: List[Dict] = []
    i = 0
    while i < len(lines):
        ln = lines[i].strip()
        i += 1
        if not ln or ln.upper().startswith("WEBVTT"):
            continue
        # Optional numeric cue id
        if ln.isdigit():
            if i >= len(lines):
                break
            ln = lines[i].strip()
            i += 1
        # Expect timing line
        if "-->" in ln:
            start_s, end_s = [x.strip() for x in ln.split("-->")[:2]]
            start_ts = _parse_vtt_timestamp(start_s.replace(",", "."))
            end_ts = _parse_vtt_timestamp(end_s.split()[0].replace(",", "."))
            # Collect text lines until blank
            buff = []
            while i < len(lines) and lines[i].strip():
                buff.append(lines[i].strip())
                i += 1
            text = " ".join(buff).strip()
            if text:
                captions.append({"text": text, "start_ts": start_ts, "end_ts": end_ts})
        # Skip until next blank
        while i < len(lines) and lines[i].strip():
            i += 1
    return captions


def convert_webvtt_to_ass(
    vtt_text: str,
    output_path: str,
    dimensions=(1920, 1080),
    *,
    language_hint: str = "auto",   # "auto" | "en" | "cjk"
    max_length_per_line: int = 22, # smaller for CJK; larger for spaced languages
    lines_per_segment: int = 2,    # 2–3 lines looks good
    font_name="Arial",
    font_size=42,
    font_color="#FFFFFF",
    stroke_color="#000000",
    stroke_size=2,
    shadow_color="#000000",
    shadow_transparency=0.5,
    shadow_blur=2,
    subtitle_position="bottom",
    fade_ms: int = 120,            # gentle fade
) -> str:
    """
    Convert a WebVTT string to an ASS file with nicer splitting and effects.
    """
    cp = Caption()
    captions = parse_webvtt_to_captions(vtt_text)

    # Heuristic language choice
    if language_hint == "auto":
        sample = "".join(c["text"] for c in captions[:3])
        is_cjk = any("\u4e00" <= ch <= "\u9fff" or "\u3040" <= ch <= "\u30ff" for ch in sample)
        lang = "cjk" if is_cjk else "en"
    else:
        lang = language_hint

    if lang == "cjk":
        segs = cp.create_subtitle_segments_international(
            captions=captions,
            max_length=max_length_per_line,
            lines=lines_per_segment,
        )
    else:
        # For English/space-delimited, we already have sentence-level text in VTT;
        # Using international splitter still gives balanced distribution across lines.
        segs = cp.create_subtitle_segments_international(
            captions=captions,
            max_length=max_length_per_line * 1,  # bump or tune as desired
            lines=lines_per_segment,
        )

    cp.create_subtitle(
        segs,
        dimensions=dimensions,
        output_path=output_path,
        font_name=font_name,
        font_size=font_size,
        font_color=font_color,
        stroke_color=stroke_color,
        stroke_size=stroke_size,
        shadow_color=shadow_color,
        shadow_transparency=shadow_transparency,
        shadow_blur=shadow_blur,
        subtitle_position=subtitle_position,
        fade_ms=fade_ms,
    )
    return output_path


if __name__ == "__main__":
    vtt = """WEBVTT

1
00:00:00.050 --> 00:00:12.087
美国人没来日本的时候， 日本没有民主选举， 民众吃不饱穿不暖， 农家子弟男要当兵女要当妓， 农民没有土地， 武士阶级高人一等。

2
00:00:12.250 --> 00:00:16.250
整个日本配给制， 吃点好的都要被举报。

4
00:00:16.412 --> 00:00:21.462
日本节节败退， 但新闻报道却一直是大获全胜。
"""

    out_path = convert_webvtt_to_ass(
        vtt,
        output_path="out.ass",
        dimensions=(1920, 1080),
        language_hint="cjk",          # force CJK splitting
        max_length_per_line=16,       # allow more characters per line (CJK)
        lines_per_segment=2,          # 2 or 3 lines works well
        font_name="Noto Sans CJK SC", # good CJK font
        font_size=56,
        stroke_size=3,
        shadow_transparency=0.55,
        shadow_blur=3,
        subtitle_position="bottom",
        fade_ms=120,
    )
    print("Wrote:", out_path)
