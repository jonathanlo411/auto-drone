"""Repeat an M4A voice recording on a schedule."""

from __future__ import annotations

import argparse
import math
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path


DEFAULT_INTERVAL_SECONDS = 15 * 60         # 15 minutes
DEFAULT_DURATION_SECONDS = 4 * 60 * 60     # 4 hours


def parse_time(value: str) -> float:
	"""Parse a duration such as ``15m``, ``4h``, or ``30s``."""
	units = {"s": 1, "m": 60, "h": 60 * 60}
	suffix = value[-1].lower() if value else ""
	if suffix in units:
		number = value[:-1]
		multiplier = units[suffix]
	else:
		number = value
		multiplier = 60

	try:
		seconds = float(number) * multiplier
	except ValueError as error:
		raise argparse.ArgumentTypeError(
			f"invalid duration {value!r}; use a number followed by s, m, or h"
		) from error

	if not math.isfinite(seconds) or seconds <= 0:
		raise argparse.ArgumentTypeError("duration must be greater than zero")
	return seconds


def get_play_command(audio_file: Path, system_name: str | None = None) -> list[str]:
	"""Return the command needed to play an M4A file on the current operating system."""
	system_name = (system_name or platform.system()).lower()

	if system_name == "darwin":
		return ["afplay", str(audio_file)]

	if system_name.startswith("win"):
		powershell_script = r"""
Add-Type -AssemblyName PresentationCore
$player = New-Object System.Windows.Media.MediaPlayer
$path = (Resolve-Path -LiteralPath $env:AUTO_DRONE_AUDIO_FILE).Path
$player.Open([Uri]::new($path))
while (-not $player.NaturalDuration.HasTimeSpan) {
	Start-Sleep -Milliseconds 100
}
$player.Play()
Start-Sleep -Milliseconds ([int]($player.NaturalDuration.TimeSpan.TotalMilliseconds + 250))
$player.Stop()
$player.Close()
"""
		return [
			"powershell.exe",
			"-NoProfile",
			"-NonInteractive",
			"-ExecutionPolicy",
			"Bypass",
			"-Command",
			powershell_script,
		]

	if system_name.startswith("linux"):
		for exe in ("ffplay", "mpg123", "play"):
			if shutil.which(exe):
				if exe == "ffplay":
					return [exe, "-nodisp", "-autoexit", "-loglevel", "quiet", str(audio_file)]
				if exe == "mpg123":
					return [exe, "-q", str(audio_file)]
				return [exe, "-q", str(audio_file)]

	raise RuntimeError(
		f"Unsupported operating system: {platform.system()}. "
		"This script supports macOS, Windows, and Linux with common M4A-capable players."
	)


def play_audio(audio_file: Path) -> None:
	"""Play one recording and wait for the configured platform to finish."""
	command = get_play_command(audio_file)
	if command[0].lower() == "powershell.exe":
		subprocess.run(
			command,
			check=True,
			env={**os.environ, "AUTO_DRONE_AUDIO_FILE": str(audio_file)},
		)
		return

	subprocess.run(command, check=True)


def run_schedule(audio_file: Path, interval: float, duration: float, dry_run: bool) -> None:
	start_time = time.monotonic()
	next_play_time = start_time
	play_count = 0

	while next_play_time < start_time + duration:
		wait_seconds = next_play_time - time.monotonic()
		if wait_seconds > 0:
			time.sleep(wait_seconds)

		if time.monotonic() >= start_time + duration:
			break

		play_count += 1
		print(f"Playing {audio_file} (#{play_count})", flush=True)
		if not dry_run:
			play_audio(audio_file)
		next_play_time += interval

	print(f"Finished after {duration:g} seconds ({play_count} playback(s)).")


def main() -> int:
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument(
		"file",
		nargs="?",
		type=Path,
		default=Path(__file__).with_name("voice.m4a"),
		help="M4A file to play (default: voice.m4a beside this script)",
	)
	parser.add_argument(
		"--interval",
		type=parse_time,
		default=DEFAULT_INTERVAL_SECONDS,
		help="time between playback starts, e.g. 15m (default: 15m)",
	)
	parser.add_argument(
		"--duration",
		type=parse_time,
		default=DEFAULT_DURATION_SECONDS,
		help="total schedule duration, e.g. 4h (default: 4h)",
	)
	parser.add_argument(
		"--dry-run",
		action="store_true",
		help="show playback times without playing audio",
	)
	args = parser.parse_args()

	audio_file = args.file.resolve()
	if not audio_file.is_file():
		print(f"Audio file not found: {audio_file}", file=sys.stderr)
		return 1

	try:
		run_schedule(audio_file, args.interval, args.duration, args.dry_run)
	except KeyboardInterrupt:
		print("\nStopped.")
	except FileNotFoundError:
		print("No supported audio player was found for this system.", file=sys.stderr)
		return 1
	except RuntimeError as error:
		print(str(error), file=sys.stderr)
		return 1
	except subprocess.CalledProcessError as error:
		print(f"Playback failed with exit code {error.returncode}.", file=sys.stderr)
		return error.returncode or 1
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
