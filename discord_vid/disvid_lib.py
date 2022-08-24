"""
A bunch of useful library functions
"""
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


def generate_file_loop(generate_file_func, task, options):
    """
    Used by each encoder type;
    they run this loop, supplying their file generation function
    and starting target file size.
    """

    filename = task.filename
    audio_rate = get_audio_rate(options[1])

    print(f"Getting file:{filename}")
    length = get_length(filename)
    print(f"File length:{length} seconds")
    print(f"Estimated audio size: {audio_rate*length/8/1024:.0f}KB")

    min_size, target_size, max_size = task.size
    actual_size = generate_file_loop_iter(
        target_size, length, generate_file_func, options
    )

    if actual_size < min_size:
        task.on_encoder_finish(actual_size, False)
        target_size *= float(max_size) / (actual_size * 1.02)
        actual_size = generate_file_loop_iter(
            target_size, length, generate_file_func, options
        )

    while actual_size > max_size:
        task.on_encoder_finish(actual_size, False)
        target_size -= int(0.01 * max_size)
        actual_size = generate_file_loop_iter(
            target_size, length, generate_file_func, options
        )

    task.on_encoder_finish(actual_size, True)


def kb_to_mb(value):
    """
    Converts KibiBytes to MebiBytes
    """
    return value / 1024.0


def bytes_to_mb(value):
    """
    Converts bytes to Mebibytes
    """
    return value / 1024 / 1024.0


def generate_file_loop_iter(target_size, length, func, options):
    """
    one loop of the file generation process
    """
    audio_rate = get_audio_rate(options[1])
    bitrate = get_bitrate(target_size, length, audio_rate)

    if bitrate < 0:
        print("Unfortunately there is not enough bits for video!")
        print(f"Bitrate: {bitrate}, Target: {target_size}mb")
        sys.exit()

    commands, output_file, cleanup = func(bitrate, audio_rate, options)
    for command in commands:
        subprocess.run(command, check=True)

    if cleanup is not None:
        cleanup(output_file)

    return os.path.getsize(output_file)


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
