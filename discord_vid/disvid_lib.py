"""
A bunch of useful library functions
"""
from datetime import timedelta, datetime
import os
import subprocess
import sys
from enum import Enum
from install.install_ffmpeg import FFPROBE_EXE
from discord_vid import disvid_nvenc
from discord_vid import disvid_libx264


class Encoder(Enum):
    """Enum representing which encoder to use"""

    NVIDIA = 1
    CPU = 2
    INTEL = 3
    AMD = 4


def get_audio_rate(output_options):
    """
    Gets the audio rate from output optoins
    assumes its already specified in k (e.g: 64k, 128k)
    """
    audio_index = output_options.index("-b:a") + 1
    return int(output_options[audio_index].lower().replace("k", "")) * 1000


def get_encoder_lib(encoder: Encoder):
    """Converts from encoder enum to encoder library"""
    if encoder == Encoder.NVIDIA:
        return disvid_nvenc

    return disvid_libx264


def guess_encoder():
    """Checks if you have an nvidia gpu installed."""

    args = "wmic path win32_VideoController get name"
    result = subprocess.run(args.split(), capture_output=True, check=True)
    items = result.stdout.lower().split()
    items = [item.decode("utf-8") for item in items]

    if "nvidia" in items:
        return Encoder.NVIDIA

    return Encoder.CPU


def get_length(filename):
    """
    returns length of file in seconds
    """
    # fmt: off
    result = subprocess.run(
        [
            FFPROBE_EXE, "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            filename,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=True
    )
    # fmt: on

    return float(result.stdout)


def get_index(strings, array):
    """
    gets index of any of the strings in *strings* inside array *array*
    """
    for string in strings:
        try:
            return array.index(string)
        except ValueError:
            pass
    return None


def get_bitrate(target_size, length, audio_rate):
    """
    Returns target video bitrate based on target size, its length in seconds,
    and the audio bitrate in Kbps
    @target_size: Size in KByte
    @length: length in seconds
    @audio_rate: Rate in Kbits/s
    return: bitrate in Kbit/s
    """
    audio_size = audio_rate * length
    target_size_kbits = target_size * 8
    bitrate = (target_size_kbits - audio_size) / length
    return bitrate


def generate_file_loop(generate_file_func, task):
    """
    Used by each encoder type;
    they run this loop, supplying their file generation function
    and starting target file size.
    """

    length = get_length(task.filename)
    task.set_video_length(length)

    min_size, target_size, max_size = task.size
    actual_size = file_loop_iter(target_size, generate_file_func, task)

    if actual_size < min_size:
        task.on_encoder_finish(actual_size, target_size, False)
        target_size *= float(max_size) / (actual_size * 1.02)
        actual_size = file_loop_iter(target_size, generate_file_func, task)

    while actual_size > max_size:
        task.on_encoder_finish(actual_size, target_size, False)
        target_size -= int(0.01 * max_size)
        actual_size = file_loop_iter(target_size, generate_file_func, task)

    task.on_encoder_finish(actual_size, target_size, True)


def kb_to_mb(value):
    """
    Converts KibiBytes to MebiBytes
    """
    return value / 1024.0


def bytes_to_mb(value):
    """
    Converts bytes to Mebibytes
    """
    return value / 1024.0 / 1024.0


def file_loop_iter(target_size, ffmpeg_command_gen, task):
    """
    Generates ffmpeg commands and cleanup functions to run, then runs them.
    """
    commands, output_file, cleanup = generate_file_loop_iter(
        target_size, ffmpeg_command_gen, task
    )
    return execute_file_loop_iter(commands, output_file, cleanup, task.on_update_cb)


def generate_file_loop_iter(target_size, ffmpeg_command_gen, task):
    """
    one loop of the file generation process
    """
    audio_rate = get_audio_rate(task.current_options[1])
    bitrate = get_bitrate(target_size, task.video_length, audio_rate)

    if bitrate < 0:
        raise ValueError("Not enough bits for video")

    return ffmpeg_command_gen(bitrate, audio_rate, task.current_options)


def execute_file_loop_iter(commands, output_file, cleanup, on_update):
    """
    Executes a set of ffmpeg commands, and the cleanup functions.
    Calls on_update while ffmpeg is running
    """
    for command in commands:
        run_ffmpeg_with_status(command, on_update)

    if cleanup is not None:
        cleanup(output_file)

    return os.path.getsize(output_file)


def run_ffmpeg_with_status(command, callback):
    """Runs ffmpeg, calling callback with the percentage"""
    with subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
    ) as process:
        print(command)
        for line in process.stdout:
            if not line.startswith("frame") or callback is None:
                continue
            pairs = line.split()
            time_str = [pair for pair in pairs if pair.startswith("time")][0]
            time_str = time_str.split("=")[1]  # 00:00:00.000
            if time_str.startswith("-"):  # negative time fix
                continue
            date_time = datetime.strptime(time_str.split(".")[0], "%H:%M:%S")
            milliseconds = float(time_str.split(".")[1]) * 10
            delta = timedelta(
                hours=date_time.hour,
                minutes=date_time.minute,
                seconds=date_time.second,
                milliseconds=milliseconds,
            )
            callback(delta)

        process.wait()


def main():
    """
    main function for this program
    """
    if "--guess_encoder" in sys.argv:
        has_nvidia = guess_encoder()
        print("We have NVIDIA!")
        sys.exit(0 if has_nvidia else 1)

    sys.exit(0)


if __name__ == "__main__":
    main()
