import os
import subprocess
import shutil
from datetime import datetime
from typing import List, Optional

from loguru import logger

from app.services.media import MediaUtils


class MultiImageVideoBuilder:
    """
    Render per-image VIDEO-ONLY segments (no audio), concatenate them,
    then add the single audio track and burn captions at the final step.
    """

    def __init__(
        self,
        dimensions: tuple[int, int],
        ffmpeg_path: str = "ffmpeg",
        fps: int = 25,
        workdir: Optional[str] = None,
    ):
        self.width, self.height = dimensions
        self.ffmpeg_path = ffmpeg_path
        self.fps = fps
        self.media = MediaUtils(ffmpeg_path=ffmpeg_path)
        self.workdir = workdir  # created in build() if not provided

    # ---------------------------
    # Utilities
    # ---------------------------

    def _make_workdir(self, base_dir: Optional[str]) -> str:
        if base_dir:
            os.makedirs(base_dir, exist_ok=True)
            return base_dir
        root = os.path.join("output", "tmp", f"slideshow_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        os.makedirs(root, exist_ok=True)
        return root

    def _run_ffmpeg(self, cmd: List[str], description: str) -> bool:
        if hasattr(self.media, "execute_ffmpeg_command"):
            return self.media.execute_ffmpeg_command(cmd, description)
        try:
            logger.debug(f"{description}: {' '.join(cmd)}")
            subprocess.run(cmd, check=True)
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"ffmpeg failed ({description}): {e}")
            return False

    def _get_audio_duration(self, audio_path: str) -> float:
        info = self.media.get_audio_info(audio_path)
        dur = info.get("duration")
        if not dur:
            raise ValueError("Could not read audio duration")
        return float(dur)

    def _compute_durations(self, n: int, audio_path: str, image_durations: Optional[List[float]]) -> List[float]:
        if image_durations is not None:
            if len(image_durations) != n:
                raise ValueError("image_durations length must match number of images")
            if any(d <= 0 for d in image_durations):
                raise ValueError("All image_durations must be positive")
            return [float(d) for d in image_durations]

        total = self._get_audio_duration(audio_path)
        base = total / max(1, n)
        durations = [base] * n
        # fix rounding drift so total matches audio length
        durations[-1] = max(0.01, total - sum(durations[:-1]))
        return durations

    def _concat_videos(self, segments: List[str], output_path: str) -> bool:
        """
        Concatenate segments using ffmpeg concat demuxer. All segments share same
        codec/params so -c copy should work; fallback to re-encode if needed.
        """
        list_file = os.path.join(self.workdir, "concat_list.txt")
        with open(list_file, "w", encoding="utf-8") as f:
            for p in segments:
                ap = os.path.abspath(p).replace("\\", "/")
                f.write(f"file '{ap}'\n")

        # Try stream copy first
        cmd = [
            self.ffmpeg_path, "-y",
            "-f", "concat", "-safe", "0",
            "-i", list_file,
            "-c", "copy",
            output_path,
        ]
        ok = self._run_ffmpeg(cmd, "concat segments")
        if not ok:
            # Fallback: re-encode
            cmd = [
                self.ffmpeg_path, "-y",
                "-f", "concat", "-safe", "0",
                "-i", list_file,
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23", "-pix_fmt", "yuv420p",
                output_path,
            ]
            ok = self._run_ffmpeg(cmd, "concat segments (re-encode fallback)")
        return ok

    # ---------------------------
    # Segment rendering (VIDEO-ONLY)
    # ---------------------------

    def _render_image_segment_video_only(
        self,
        image_path: str,
        duration: float,
        effect_config: Optional[dict],
        out_path: str,
    ) -> bool:
        """
        Render one image to a VIDEO-ONLY segment of `duration` seconds.
        Bounded by filter-side trim so it cannot run away with -loop 1.
        """
        eff = effect_config or {"effect": "ken_burns"}
        effect_type = eff.get("effect", "ken_burns")
        fps = self.fps
        W, H = self.width, self.height
        duration_frames = max(1, int(round(duration * fps)))
    
        if effect_type == "ken_burns":
            zoom_factor = eff.get("zoom_factor", 0.001)
            direction = eff.get("direction", "zoom-to-top-left")
            zoom_expressions = {
                "zoom-to-top":      f"z='zoom+{zoom_factor}':x=iw/2-(iw/zoom/2):y=0",
                "zoom-to-center":   f"z='zoom+{zoom_factor}':x=iw/2-(iw/zoom/2):y=ih/2-(ih/zoom/2)",
                "zoom-to-top-left": f"z='zoom+{zoom_factor}':x=0:y=0",
            }
            zoom_expr = zoom_expressions.get(direction, zoom_expressions["zoom-to-top-left"])
    
            filter_str = (
                f"[0]scale={W}:-2,setsar=1:1,"
                f"crop={W}:{H},"
                # produce exactly duration_frames at fps
                f"zoompan={zoom_expr}:d={duration_frames}:s={W}x{H}:fps={fps},"
                # hard bound the segment length
                f"trim=duration={duration:.6f},setpts=PTS-STARTPTS[v]"
            )
    
        elif effect_type == "pan":
            direction = eff.get("direction", "left-to-right")
            speed = eff.get("speed", "normal")
            speed_mult = {"slow": 0.5, "normal": 1.0, "fast": 2.0}.get(speed, 1.0)
    
            scale_factor = eff.get("scale_factor", 1.3)
            scaled_w = int(W * scale_factor)
            scaled_h = int(H * scale_factor)
    
            if direction == "left-to-right":
                start_x, end_x = 0, scaled_w - W
                start_y = end_y = (scaled_h - H) // 2
            elif direction == "right-to-left":
                start_x, end_x = scaled_w - W, 0
                start_y = end_y = (scaled_h - H) // 2
            elif direction == "top-to-bottom":
                start_x = end_x = (scaled_w - W) // 2
                start_y, end_y = 0, scaled_h - H
            elif direction == "bottom-to-top":
                start_x = end_x = (scaled_w - W) // 2
                start_y, end_y = scaled_h - H, 0
            else:
                start_x, end_x = 0, scaled_w - W
                start_y = end_y = (scaled_h - H) // 2
    
            pan_x_expr = f"{start_x}+({end_x}-{start_x})*t/{duration}*{speed_mult}"
            pan_y_expr = f"{start_y}+({end_y}-{start_y})*t/{duration}*{speed_mult}"
    
            filter_str = (
                f"[0]scale={scaled_w}:{scaled_h},setsar=1:1,"
                f"crop={W}:{H}:{pan_x_expr}:{pan_y_expr},"
                # normalize to target fps and bound duration
                f"fps={fps},trim=duration={duration:.6f},setpts=PTS-STARTPTS[v]"
            )
    
        else:
            filter_str = (
                f"[0]scale={W}:{H},setsar=1:1,"
                f"fps={fps},trim=duration={duration:.6f},setpts=PTS-STARTPTS[v]"
            )
    
        cmd = [
            self.ffmpeg_path, "-y",
            "-loop", "1",
            "-i", image_path,                     # no input-side -t or -r
            "-filter_complex", filter_str,
            "-map", "[v]",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23", "-pix_fmt", "yuv420p",
            "-an",                                 # video-only
            out_path,
        ]
        return self._run_ffmpeg(cmd, f"render image->video-only {os.path.basename(image_path)} ({duration:.3f}s)")

    # ---------------------------
    # Final mux: add audio + (optionally) burn captions
    # ---------------------------

    def _escape_for_filter_path(self, p: str) -> str:
        # ffmpeg filter args: escape \  :  '
        return p.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")

    def _mux_audio_and_optional_captions(
        self,
        video_only_path: str,
        audio_path: Optional[str],
        captions_path: Optional[str],
        out_path: str,
    ) -> bool:
        """
        If captions provided: burn onto video; map audio from file.
        If no captions: just mux audio (no re-encode for video).
        """

        os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)

        if audio_path and captions_path:
            sub_abs = os.path.abspath(captions_path).replace("\\", "/")
            sub_esc = self._escape_for_filter_path(sub_abs)
            filter_str = f"[0:v]subtitles=filename='{sub_esc}'[v]"  # key + escaped path

            cmd = [
                self.ffmpeg_path, "-y",
                "-i", video_only_path,
                "-i", audio_path,
                "-filter_complex", filter_str,
                "-map", "[v]", "-map", "1:a",
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k",
                "-shortest",
                out_path,
            ]
            return self._run_ffmpeg(cmd, "burn captions + mux audio")


        if audio_path and not captions_path:
            # Mux audio only; keep video as-is
            cmd = [
                self.ffmpeg_path, "-y",
                "-i", video_only_path,
                "-i", audio_path,
                "-map", "0:v", "-map", "1:a",
                "-c:v", "copy",
                "-c:a", "aac", "-b:a", "192k",
                "-shortest",
                out_path,
            ]
            return self._run_ffmpeg(cmd, "mux audio")

        if (not audio_path) and captions_path:
            # Burn subs only
            sub = os.path.abspath(captions_path).replace("\\", "/")
            cmd = [
                self.ffmpeg_path, "-y",
                "-i", video_only_path,
                "-vf", f"subtitles='{sub}'",
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23", "-pix_fmt", "yuv420p",
                out_path,
            ]
            return self._run_ffmpeg(cmd, "burn captions (no audio)")

        # Neither audio nor captions: just copy
        shutil.copy2(video_only_path, out_path)
        return True

    # ---------------------------
    # Public API
    # ---------------------------

    def build(
        self,
        images: List[str],
        audio_file: Optional[str],
        captions_file: Optional[str],
        output_file: str,
        image_durations: Optional[List[float]] = None,
        effect_config: Optional[dict] = None,
        effect_configs: Optional[List[Optional[dict]]] = None,
        temp_dir: Optional[str] = None,
        keep_temps: bool = False,
    ) -> bool:
        """
        1) Render each image -> VIDEO-ONLY segment (no audio).
        2) Concatenate segments to one video-only file.
        3) Add the full audio and burn captions in the final mux step.
        """
        if not images:
            logger.error("No images provided")
            return False

        if image_durations is None and not audio_file:
            logger.error("audio_file must be provided when image_durations is None")
            return False

        workdir = self._make_workdir(temp_dir)
        self.workdir = workdir
        logger.bind(workdir=workdir).debug("working directory prepared")

        try:
            # durations
            durations = self._compute_durations(len(images), audio_file, image_durations) \
                        if audio_file else image_durations

            # effects
            if effect_configs is not None:
                if len(effect_configs) != len(images):
                    logger.error("effect_configs length must match images")
                    return False
                effects = effect_configs
            else:
                effects = [effect_config] * len(images)

            # render segments (VIDEO-ONLY)
            segment_paths: List[str] = []
            for idx, (img, dur, eff) in enumerate(zip(images, durations, effects)):
                seg_video = os.path.join(workdir, f"seg_{idx:03d}.mp4")
                if not self._render_image_segment_video_only(img, float(dur), eff or {"effect": "ken_burns"}, seg_video):
                    logger.error(f"segment {idx} render failed")
                    return False
                segment_paths.append(seg_video)

            # merge segments into one VIDEO-ONLY file
            merged_vonly = os.path.join(workdir, "merged_vonly.mp4")
            if not self._concat_videos(segment_paths, merged_vonly):
                logger.error("concat of segments failed")
                return False

            # final mux: add audio + burn captions
            ok = self._mux_audio_and_optional_captions(
                video_only_path=merged_vonly,
                audio_path=audio_file,
                captions_path=captions_file,
                out_path=output_file,
            )
            if not ok:
                return False

            logger.info(f"video saved: {output_file}")
            return True

        finally:
            if not keep_temps and self.workdir and os.path.isdir(self.workdir):
                try:
                    shutil.rmtree(self.workdir, ignore_errors=True)
                except Exception:
                    pass