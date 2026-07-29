#!/usr/bin/env python3
"""Turn a piano performance video/audio file into sheet music (MusicXML).

Usage:
    python transcribe.py input.mp4 output.musicxml
    python transcribe.py input.wav output.musicxml
"""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

from basic_pitch.inference import predict
from basic_pitch import ICASSP_2022_MODEL_PATH
import pretty_midi
from music21 import converter

AUDIO_EXTS = {".wav", ".mp3", ".flac", ".ogg", ".m4a"}


def extract_audio(input_path: Path, wav_path: Path) -> None:
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(input_path),
            "-ar", "22050", "-ac", "1", "-vn",
            str(wav_path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def transcribe_to_midi(wav_path: Path, midi_path: Path) -> None:
    _, midi_data, _ = predict(str(wav_path), ICASSP_2022_MODEL_PATH)
    midi_data.write(str(midi_path))


def clean_midi(midi_path: Path, min_note_duration: float = 0.05) -> pretty_midi.PrettyMIDI:
    pm = pretty_midi.PrettyMIDI(str(midi_path))
    for instrument in pm.instruments:
        instrument.notes = [
            n for n in instrument.notes if (n.end - n.start) >= min_note_duration
        ]
    return pm


def midi_to_musicxml(pm: pretty_midi.PrettyMIDI, cleaned_midi_path: Path, output_path: Path) -> None:
    pm.write(str(cleaned_midi_path))
    score = converter.parse(str(cleaned_midi_path))
    score.write("musicxml", fp=str(output_path))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Input video or audio file")
    parser.add_argument("output", type=Path, help="Output .musicxml file")
    parser.add_argument(
        "--keep-midi", action="store_true",
        help="Also keep the intermediate .mid file next to the output",
    )
    args = parser.parse_args()

    if not args.input.exists():
        sys.exit(f"Input file not found: {args.input}")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        wav_path = tmp_dir / "audio.wav"
        raw_midi_path = tmp_dir / "raw.mid"

        if args.input.suffix.lower() in AUDIO_EXTS:
            wav_path = args.input
        else:
            print("Extracting audio...")
            extract_audio(args.input, wav_path)

        print("Transcribing pitch (this can take a minute)...")
        transcribe_to_midi(wav_path, raw_midi_path)

        print("Cleaning up short/noise notes...")
        pm = clean_midi(raw_midi_path)

        cleaned_midi_path = (
            args.output.with_suffix(".mid") if args.keep_midi else tmp_dir / "cleaned.mid"
        )

        print("Rendering sheet music...")
        midi_to_musicxml(pm, cleaned_midi_path, args.output)

    print(f"Done. Sheet music written to {args.output}")
    if args.keep_midi:
        print(f"MIDI written to {cleaned_midi_path}")


if __name__ == "__main__":
    main()
