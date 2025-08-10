from app.services.media import MediaUtils
import os
import re
import pathlib
import time
from loguru import logger


def _ffpath(p: str) -> str:
    """Absolute path with forward slashes (safe for most ffmpeg args)."""
    return os.path.abspath(p).replace("\\", "/")


def _ffsub_path(p: str) -> str:
    """
    Path for ffmpeg subtitles filter on Windows:
    - absolute + forward slashes
    - escape drive-colon: C: -> C\:
    """
    posix = pathlib.Path(p).absolute().as_posix()
    if os.name == "nt":
        posix = re.sub(r"^([A-Za-z]):", r"\1\\:", posix)
    return posix


class VideoBuilder:
    """
    Builder class for constructing FFmpeg video commands with a fluent interface.
    """

    def __init__(self, dimensions: tuple[int, int], ffmpeg_path="ffmpeg"):
        if not isinstance(dimensions, tuple) or len(dimensions) != 2:
            raise ValueError("Dimensions must be a tuple of (width, height).")

        self.width, self.height = dimensions
        self.ffmpeg_path = ffmpeg_path

        # Components
        self.background = None
        self.audio_file = None
        self.captions = None
        self.output_path = "output.mp4"

        # Internal state
        self.media_utils: MediaUtils | None = None

    def set_media_utils(self, media_utils: MediaUtils):
        """Set the media manager for duration calculations."""
        self.media_utils = media_utils
        return self

    def set_background_image(self, file_path: str, effect_config: dict = None):
        """Set background as an image with optional visual effects.

        Args:
            file_path: Path to the image file
            effect_config: Configuration for visual effects. Supported effects:
                - Ken Burns (zoom): {"effect": "ken_burns", "zoom_factor": 0.001, "direction": "zoom-to-top-left"}
                - Pan: {"effect": "pan", "direction": "left-to-right", "speed": "normal"}
        """
        self.background = {
            "type": "image",
            "file": file_path,
            "effect_config": effect_config or {"effect": "ken_burns"},  # default
        }
        return self

    def set_background_video(self, file_path: str):
        """Set background as a video file."""
        self.background = {"type": "video", "file": file_path}
        return self

    def set_audio(self, file_path: str):
        """Set audio file."""
        self.audio_file = file_path
        return self

    def set_captions(self, file_path: str = None, config: dict = None):
        """Set caption subtitles.

        Args:
            file_path: Path to subtitle file (.ass recommended)
            config: Optional dict, supports:
                - fontsdir: directory for fonts discovery by libass
                - force_style: ASS force_style string, e.g. "FontName=Arial,FontSize=36"
        """
        self.captions = {
            "file": file_path,
            **(config or {}),
        }
        return self

    def set_output_path(self, output_path: str):
        """Set output file path and ensure directory exists."""
        self.output_path = output_path
        out_dir = os.path.dirname(os.path.abspath(output_path)) or "."
        os.makedirs(out_dir, exist_ok=True)
        return self

    def _build_subtitles_filter(self) -> tuple[str, str] | None:
        """
        Build subtitles filter string and output label.
        Returns:
            (filter_chain, out_label) or None if no captions
        """
        if not self.captions:
            return None

        subtitle_file = self.captions.get("file")
        if not subtitle_file:
            return None

        subs_path = _ffsub_path(subtitle_file)

        # subtitles filter options
        opts = [f"'{subs_path}'"]  # filename positional (quoted)
        fontsdir = self.captions.get("fontsdir")
        if fontsdir:
            opts.append(f"fontsdir='{_ffsub_path(fontsdir)}'")

        force_style = self.captions.get("force_style")
        if force_style:
            # escape commas to avoid splitting into multiple args
            safe_style = force_style.replace(",", r"\,")
            opts.append(f"force_style='{safe_style}'")

        arg = ":".join(opts)

        # Input [bg], output [v]
        chain = f"[bg]subtitles={arg}[v]"
        return chain, "[v]"

    def build_command(self):
        """Build the complete FFmpeg command."""
        if not self.background:
            raise ValueError("Background must be set (image or video).")

        if not self.audio_file and not self.captions:
            raise ValueError("At least one of audio_file or captions must be provided.")

        # Validate combinations
        if self.background["type"] == "image" and not self.audio_file:
            raise ValueError("Audio file must be provided if background is an image.")

        if (
            self.background["type"] == "video"
            and not self.audio_file
            and self.captions is None
        ):
            raise ValueError("Audio file or captions must be provided if background is a video.")

        # Get audio duration if audio file is provided
        audio_duration = None
        if self.audio_file:
            if not self.media_utils:
                raise ValueError("Media manager must be set to determine audio duration.")
            media_info = self.media_utils.get_audio_info(self.audio_file)
            audio_duration = media_info.get("duration")
            if not audio_duration:
                raise ValueError("Could not determine audio duration")

        # Ensure output directory exists
        out_dir = os.path.dirname(os.path.abspath(self.output_path)) or "."
        os.makedirs(out_dir, exist_ok=True)

        # Base command with useful logging
        cmd = [
            self.ffmpeg_path,
            "-y",
            "-hide_banner",
            "-loglevel", "level+info",
            "-report",
        ]

        filter_parts = []
        input_index = 0
        fps = 25

        # Background input
        if self.background["type"] == "image":
            if audio_duration is None:
                raise ValueError("Audio duration is required for image background.")

            cmd.extend([
                "-loop", "1",
                "-t", str(audio_duration),
                "-r", str(fps),
                "-i", self.background["file"],
            ])

            effect_config = self.background.get("effect_config", {"effect": "ken_burns"})
            if "ken_burns" in self.background and "effect_config" not in self.background:
                old_ken_burns = self.background.get("ken_burns", {})
                effect_config = {
                    "effect": "ken_burns",
                    "zoom_factor": old_ken_burns.get("zoom_factor", 0.001),
                    "direction": old_ken_burns.get("direction", "zoom-to-top-left"),
                }

            effect_type = effect_config.get("effect", "ken_burns")
            duration_frames = int(audio_duration * fps)

            if effect_type == "ken_burns":
                zoom_factor = effect_config.get("zoom_factor", 0.001)
                direction = effect_config.get("direction", "zoom-to-top-left")
                zoom_expressions = {
                    "zoom-to-top": f"z='zoom+{zoom_factor}':x=iw/2-(iw/zoom/2):y=0",
                    "zoom-to-center": f"z='zoom+{zoom_factor}':x=iw/2-(iw/zoom/2):y=ih/2-(ih/zoom/2)",
                    "zoom-to-top-left": f"z='zoom+{zoom_factor}':x=0:y=0",
                }
                zoom_expr = zoom_expressions.get(direction, zoom_expressions["zoom-to-top-left"])
                zoompan_d = duration_frames + 1
                filter_parts.append(
                    f"[{input_index}]scale={self.width}:-2,setsar=1:1,"
                    f"crop={self.width}:{self.height},"
                    f"zoompan={zoom_expr}:d={zoompan_d}:s={self.width}x{self.height}:fps={fps}[bg]"
                )

            elif effect_type == "pan":
                direction = effect_config.get("direction", "left-to-right")
                speed = effect_config.get("speed", "normal")
                speed_multipliers = {"slow": 0.5, "normal": 1.0, "fast": 2.0}
                speed_mult = speed_multipliers.get(speed, 1.0)

                scale_factor = 1.3
                scaled_width = int(self.width * scale_factor)
                scaled_height = int(self.height * scale_factor)

                if direction == "left-to-right":
                    start_x = 0
                    end_x = scaled_width - self.width
                    start_y = (scaled_height - self.height) // 2
                    end_y = start_y
                elif direction == "right-to-left":
                    start_x = scaled_width - self.width
                    end_x = 0
                    start_y = (scaled_height - self.height) // 2
                    end_y = start_y
                elif direction == "top-to-bottom":
                    start_x = (scaled_width - self.width) // 2
                    end_x = start_x
                    start_y = 0
                    end_y = scaled_height - self.height
                elif direction == "bottom-to-top":
                    start_x = (scaled_width - self.width) // 2
                    end_x = start_x
                    start_y = scaled_height - self.height
                    end_y = 0
                else:
                    start_x = 0
                    end_x = scaled_width - self.width
                    start_y = (scaled_height - self.height) // 2
                    end_y = start_y

                pan_x_expr = f"{start_x}+({end_x}-{start_x})*t/{audio_duration}*{speed_mult}"
                pan_y_expr = f"{start_y}+({end_y}-{start_y})*t/{audio_duration}*{speed_mult}"

                filter_parts.append(
                    f"[{input_index}]scale={scaled_width}:{scaled_height},setsar=1:1,"
                    f"crop={self.width}:{self.height}:{pan_x_expr}:{pan_y_expr}[bg]"
                )

            else:
                filter_parts.append(
                    f"[{input_index}]scale={self.width}:{self.height},setsar=1:1[bg]"
                )

        elif self.background["type"] == "video":
            cmd.extend(["-i", self.background["file"]])
            filter_parts.append(f"[{input_index}]scale={self.width}:{self.height},setsar=1:1[bg]")

        input_index += 1
        current_video_label = "[bg]"

        # Audio input
        audio_input_index = None
        if self.audio_file:
            cmd.extend(["-i", self.audio_file])
            audio_input_index = input_index
            input_index += 1

        # Subtitles
        sub_chain = self._build_subtitles_filter()
        if sub_chain:
            chain, out_label = sub_chain
            filter_parts.append(chain)
            current_video_label = out_label  # "[v]"

        # filter_complex
        if filter_parts:
            cmd.extend(["-filter_complex", ";".join(filter_parts)])

        # Map
        cmd.extend(["-map", current_video_label])
        if audio_input_index is not None:
            cmd.extend(["-map", f"{audio_input_index}:a"])

        # Codecs
        cmd.extend(["-c:v", "libx264", "-preset", "ultrafast", "-crf", "23", "-pix_fmt", "yuv420p"])
        if self.audio_file:
            cmd.extend(["-c:a", "aac", "-b:a", "192k"])

        # Duration
        cmd.append("-shortest")

        # Output
        cmd.append(self.output_path)
        return cmd

    def execute(self):
        """Build and execute the FFmpeg command using MediaUtils for progress tracking."""
        if not self.media_utils:
            logger.error("MediaUtils must be set before executing video build")
            return False

        # Ensure output directory exists
        try:
            out_dir = os.path.dirname(os.path.abspath(self.output_path)) or "."
            os.makedirs(out_dir, exist_ok=True)
        except Exception as e:
            logger.bind(error=str(e)).error("failed to create output directory")
            return False

        start = time.time()
        context_logger = logger.bind(
            dimensions=(self.width, self.height),
            background_type=self.background.get("type") if self.background else None,
            has_audio=bool(self.audio_file),
            has_captions=bool(self.captions),
            output_path=self.output_path,
            youtube_channel="https://www.youtube.com/@aiagentsaz",
        )

        try:
            context_logger.debug("building video with VideoBuilder")
            cmd = self.build_command()

            # Expected duration (for progress)
            expected_duration = None
            if self.audio_file:
                audio_info = self.media_utils.get_audio_info(self.audio_file)
                expected_duration = audio_info.get("duration")
            elif self.background and self.background.get("type") == "video":
                video_info = self.media_utils.get_video_info(self.background["file"])
                expected_duration = video_info.get("duration")

            context_logger.bind(
                command=" ".join(cmd),
                expected_duration=expected_duration,
            ).debug("executing video build command")

            success = self.media_utils.execute_ffmpeg_command(
                cmd,
                "build video",
                expected_duration=expected_duration,
                show_progress=True,
            )

            if success:
                context_logger.bind(execution_time=time.time() - start).info("video built successfully")
                return True
            else:
                context_logger.error("failed to build video")
                return False

        except Exception as e:
            context_logger.bind(error=str(e), execution_time=time.time() - start).error(
                "error during video rendering"
            )
            return False
