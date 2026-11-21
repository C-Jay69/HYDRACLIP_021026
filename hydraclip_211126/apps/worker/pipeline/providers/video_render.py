"""Video Render Provider: FFmpeg + MoviePy."""

import logging
import os
import subprocess
from typing import Optional

from app.pipeline.providers.base import BaseVideoRenderProvider

logger = logging.getLogger(__name__)


class FFmpegVideoRenderProvider(BaseVideoRenderProvider):
    """FFmpeg-based video render provider."""
    
    def __init__(self, ffmpeg_path: str = "ffmpeg"):
        self.ffmpeg_path = ffmpeg_path
    
    async def render_short_form(self, script: str, audio_file: str, subtitles: str, **kwargs) -> str:
        """Render short-form video (9:16)."""
        try:
            output_path = kwargs.get("output_path", "/tmp/output.mp4")
            width = kwargs.get("width", 1080)
            height = kwargs.get("height", 1920)
            bg_color = kwargs.get("bg_color", "000000")
            
            # Create background
            cmd = [
                self.ffmpeg_path,
                "-f", "lavfi",
                "-i", f"color=c=#{bg_color}:s={width}x{height}:d=60",
                "-i", audio_file,
                "-vf", f"subtitles={subtitles}",
                "-c:v", "libx264",
                "-c:a", "aac",
                "-shortest",
                output_path,
            ]
            
            subprocess.run(cmd, capture_output=True, check=True)
            return output_path
        except Exception as e:
            logger.error(f"Short-form render failed: {e}")
            raise
    
    async def render_long_form(self, script: str, audio_file: str, subtitles: str, **kwargs) -> str:
        """Render long-form video (16:9)."""
        try:
            output_path = kwargs.get("output_path", "/tmp/output.mp4")
            width = kwargs.get("width", 1920)
            height = kwargs.get("height", 1080)
            bg_color = kwargs.get("bg_color", "000000")
            
            cmd = [
                self.ffmpeg_path,
                "-f", "lavfi",
                "-i", f"color=c=#{bg_color}:s={width}x{height}:d=300",
                "-i", audio_file,
                "-vf", f"subtitles={subtitles}",
                "-c:v", "libx264",
                "-c:a", "aac",
                "-shortest",
                output_path,
            ]
            
            subprocess.run(cmd, capture_output=True, check=True)
            return output_path
        except Exception as e:
            logger.error(f"Long-form render failed: {e}")
            raise
    
    async def add_captions(self, video_path: str, subtitles: str, style: str, **kwargs) -> str:
        """Add captions to video."""
        try:
            output_path = kwargs.get("output_path", video_path.replace(".mp4", "_captioned.mp4"))
            
            cmd = [
                self.ffmpeg_path,
                "-i", video_path,
                "-vf", f"subtitles={subtitles}",
                "-c:a", "copy",
                output_path,
            ]
            
            subprocess.run(cmd, capture_output=True, check=True)
            return output_path
        except Exception as e:
            logger.error(f"Add captions failed: {e}")
            raise
    
    async def add_intro_outro(self, video_path: str, intro: str, outro: str, **kwargs) -> str:
        """Add intro/outro to video."""
        try:
            output_path = kwargs.get("output_path", video_path.replace(".mp4", "_intro_outro.mp4"))
            
            # Concatenate intro + video + outro
            with open("/tmp/concat_list.txt", "w") as f:
                f.write(f"file '{intro}'\n")
                f.write(f"file '{video_path}'\n")
                f.write(f"file '{outro}'\n")
            
            cmd = [
                self.ffmpeg_path,
                "-f", "concat",
                "-safe", "0",
                "-i", "/tmp/concat_list.txt",
                "-c", "copy",
                output_path,
            ]
            
            subprocess.run(cmd, capture_output=True, check=True)
            return output_path
        except Exception as e:
            logger.error(f"Add intro/outro failed: {e}")
            raise
    
    async def add_music(self, video_path: str, music_file: str, **kwargs) -> str:
        """Add music to video."""
        try:
            output_path = kwargs.get("output_path", video_path.replace(".mp4", "_music.mp4"))
            
            cmd = [
                self.ffmpeg_path,
                "-i", video_path,
                "-i", music_file,
                "-filter_complex", "[0:a][1:a]amix=inputs=2:duration=first:dropout_transition=2",
                "-c:v", "copy",
                "-c:a", "aac",
                output_path,
            ]
            
            subprocess.run(cmd, capture_output=True, check=True)
            return output_path
        except Exception as e:
            logger.error(f"Add music failed: {e}")
            raise
    
    async def add_logo_overlay(self, video_path: str, logo_file: str, **kwargs) -> str:
        """Add logo overlay to video."""
        try:
            output_path = kwargs.get("output_path", video_path.replace(".mp4", "_logo.mp4"))
            
            cmd = [
                self.ffmpeg_path,
                "-i", video_path,
                "-i", logo_file,
                "-filter_complex", "[0:v][1:v]overlay=W-w-10:H-h-10",
                "-c:a", "copy",
                output_path,
            ]
            
            subprocess.run(cmd, capture_output=True, check=True)
            return output_path
        except Exception as e:
            logger.error(f"Add logo overlay failed: {e}")
            raise
    
    async def export_for_platform(self, video_path: str, platform: str, **kwargs) -> str:
        """Export video for specific platform."""
        try:
            output_path = kwargs.get("output_path", video_path.replace(".mp4", f"_{platform}.mp4"))
            
            # Platform-specific settings
            if platform == "youtube":
                cmd = [
                    self.ffmpeg_path,
                    "-i", video_path,
                    "-c:v", "libx264",
                    "-preset", "medium",
                    "-crf", "23",
                    "-c:a", "aac",
                    "-b:a", "128k",
                    output_path,
                ]
            elif platform == "instagram":
                cmd = [
                    self.ffmpeg_path,
                    "-i", video_path,
                    "-c:v", "libx264",
                    "-preset", "fast",
                    "-crf", "28",
                    "-c:a", "aac",
                    "-b:a", "128k",
                    "-vf", "scale=1080:1920",
                    output_path,
                ]
            elif platform == "tiktok":
                cmd = [
                    self.ffmpeg_path,
                    "-i", video_path,
                    "-c:v", "libx264",
                    "-preset", "fast",
                    "-crf", "28",
                    "-c:a", "aac",
                    "-b:a", "128k",
                    "-vf", "scale=1080:1920",
                    output_path,
                ]
            else:
                cmd = [
                    self.ffmpeg_path,
                    "-i", video_path,
                    "-c:v", "libx264",
                    "-preset", "medium",
                    "-crf", "23",
                    "-c:a", "aac",
                    output_path,
                ]
            
            subprocess.run(cmd, capture_output=True, check=True)
            return output_path
        except Exception as e:
            logger.error(f"Export for platform failed: {e}")
            raise