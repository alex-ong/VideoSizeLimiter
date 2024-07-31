"""
Helpers for installing ffmpeg
"""
import os
import subprocess

from install.helpers import download_file

FFMPEG_PATH = "./ffmpeg/"
FFMPEG_EXE = "ffmpeg/ffmpeg.exe"
FFPROBE_EXE = "ffmpeg/ffprobe.exe"
URL = "https://www.gyan.dev/ffmpeg/builds/packages/ffmpeg-6.1.1-full_build.7z"
OUT_ZIP = "./ffmpeg/ffmpeg.7z"


def ffmpeg_installed():
    """returns whether ffmpeg is installed"""
    return os.path.exists(FFMPEG_EXE)


def install_ffmpeg(on_update, force=False):
    """installs ffmpeg if it doesn't exist"""
    if not os.path.exists(FFMPEG_EXE) or force:
        download_ffmpeg(on_update)


def download_ffmpeg(on_update):
    """Download and unzip ffmpeg"""
    os.makedirs(FFMPEG_PATH, exist_ok=True)
    download_file(URL, OUT_ZIP, on_update)
    on_update("Unzipping ffmpeg")
    subprocess.call("./7z/7za e ffmpeg/ffmpeg.7z *.exe -r -aoa -offmpeg")
    on_update("Cleaning up download")
    os.remove(OUT_ZIP)
    on_update(None)  # Finish
