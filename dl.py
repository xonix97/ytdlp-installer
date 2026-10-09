#!/usr/bin/env python3

import json
import re
import shutil
import subprocess
import sys
from difflib import SequenceMatcher
from pathlib import Path

MAX_RESULTS = 10
MIN_MATCH = 50


def run_capture(args):
    return subprocess.run(
        args,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def normalize(text):
    text = (text or "").lower()
    text = re.sub(r"\([^)]*\)|\[[^]]*\]", " ", text)
    text = re.sub(
        r"\b(official|audio|video|lyrics?|visualizer|hd|4k)\b",
        " ",
        text,
    )
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def split_song_artist(request):
    if " - " in request:
        song, artist = request.split(" - ", 1)
        return song.strip(), artist.strip()
    return request.strip(), ""


def title_match(request, video):
    song, artist = split_song_artist(request)

    title = normalize(video.get("title", ""))
    channel = normalize(
        video.get("channel") or video.get("uploader") or ""
    )

    requested_song = normalize(song)
    requested_artist = normalize(artist)

    song_words = set(requested_song.split())
    title_words = set(title.split())

    song_score = SequenceMatcher(
        None, requested_song, title
    ).ratio()

    if song_words:
        song_score = max(
            song_score,
            len(song_words & title_words) / len(song_words),
        )

    if not requested_artist:
        return 100 * song_score

    artist_words = set(requested_artist.split())

    artist_score = SequenceMatcher(
        None, requested_artist, title
    ).ratio()

    if artist_words:
        artist_score = max(
            artist_score,
            len(artist_words & title_words) / len(artist_words),
        )

    if channel:
        channel_words = set(channel.split())

        artist_score = max(
            artist_score,
            SequenceMatcher(
                None, requested_artist, channel
            ).ratio(),
            len(artist_words & channel_words)
            / max(len(artist_words), 1),
        )

    return 100 * (0.7 * song_score + 0.3 * artist_score)


def upload_date(video):
    date = video.get("upload_date") or "Unknown date"

    if len(date) == 8 and date.isdigit():
        return f"{date[:4]}-{date[4:6]}-{date[6:]}"

    return date


def get_channel(video):
    return (
        video.get("channel")
        or video.get("uploader")
        or "Unknown channel"
    )


def display_result(index, video, request):
    title = video.get("title") or "Unknown title"
    channel = get_channel(video)
    date = upload_date(video)
    match = title_match(request, video)

    print(
        f"{index:>2}. "
        f"{channel[:22]:<22} "
        f"{title[:48]:<48} "
        f"{date:<12} "
        f"[match: {match:.0f}%]"
    )


def search_youtube(request):
    print(f"\nSearching YouTube: {request}")

    result = run_capture([
        "yt-dlp",
        "--flat-playlist",
        "--dump-single-json",
        f"ytsearch{MAX_RESULTS}:{request}",
    ])

    if result.returncode != 0:
        print("Search failed:")
        print((result.stderr or "Unknown yt-dlp error")[-800:])
        return []

    try:
        data = json.loads(result.stdout)
        return [
            item for item in data.get("entries", [])
            if item
        ]
    except (json.JSONDecodeError, AttributeError):
        print("Could not parse YouTube search results.")
        return []


def video_url(video):
    url = video.get("webpage_url") or video.get("url")

    if url and url.startswith("http"):
        return url

    video_id = video.get("id")

    if video_id:
        return f"https://www.youtube.com/watch?v={video_id}"

    return None


def download_video(video, request, output_dir):
    title = video.get("title") or "Unknown title"
    channel = get_channel(video)
    match = title_match(request, video)

    if match < MIN_MATCH:
        print(
            f"Rejected: match is {match:.0f}%, "
            f"below {MIN_MATCH}%."
        )
        return False

    url = video_url(video)

    if not url:
        print("Could not determine this video's URL.")
        return False

    print("\n" + "+" * 60)
    print(f"Installing from: {title}")
    print(f"Channel:          {channel}")
    print(f"Requested song:   {request}")
    print(f"Match:            {match:.0f}%")
    print(f"Output folder:    {output_dir}")
    print("+" * 60 + "\n")

    command = [
        "yt-dlp",
        "--no-playlist",
        "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", "0",
        "--progress",
        "--no-overwrites",
        "-o",
        str(output_dir / "%(title)s [%(id)s].%(ext)s"),
        url,
    ]

    result = subprocess.run(command)

    if result.returncode == 0:
        print(f"\nDownloaded: {title}")
        return True

    print("Download failed.")
    return False


def choose_result(results, request):
    print("\nSearch results:\n")
    print(
        f"{'#':>2}  "
        f"{'CHANNEL':<22} "
        f"{'TITLE':<48} "
        f"{'DATE':<12} MATCH"
    )
    print("-" * 100)

    for index, video in enumerate(results, 1):
        display_result(index, video, request)

    while True:
        choice = input(
            "\nEnter result number (Enter to cancel): "
        ).strip()

        if not choice:
            return None

        if choice.isdigit() and 1 <= int(choice) <= len(results):
            return int(choice) - 1

        print(f"Enter a number from 1 to {len(results)}.")


def process_song(request, output_dir):
    results = search_youtube(request)

    if not results:
        print("No results found; skipping.")
        return

    print("\n" + "=" * 100)
    print(f" SONG: {request}")
    print("=" * 100)
    print(
        f"{'#':>2}  "
        f"{'CHANNEL':<22} "
        f"{'TITLE':<48} "
        f"{'DATE':<12} MATCH"
    )
    print("-" * 100)

    for index, video in enumerate(results, 1):
        display_result(index, video, request)

    selected = 0

    while True:
        choice = input("\ninstall (y/n/ls): ").strip().lower()

        if choice == "n":
            print("Skipped.")
            return

        if choice == "ls":
            picked = choose_result(results, request)

            if picked is None:
                return

            selected = picked
            video = results[selected]

            print(f"\nSelected: {video.get('title', 'Unknown title')}")
            print(f"Channel:  {get_channel(video)}")
            print(f"Date:     {upload_date(video)}")
            print(f"Match:    {title_match(request, video):.0f}%")
            continue

        if choice != "y":
            print("Use y, n, or ls.")
            continue

        video = results[selected]

        if title_match(request, video) < MIN_MATCH:
            print(
                f"Match below {MIN_MATCH}%. "
                "Use ls to choose another result."
            )
            continue

        if download_video(video, request, output_dir):
            return

        print("\nDownload failed. Trying later matching results...")

        for index, candidate in enumerate(results):
            if index <= selected:
                continue

            if title_match(request, candidate) >= MIN_MATCH:
                display_result(index + 1, candidate, request)

                if download_video(candidate, request, output_dir):
                    return

        print("No further matching result downloaded.")
        return


def load_songs():
    print("=" * 60)
    print("           INTERACTIVE YOUTUBE DOWNLOADER")
    print("=" * 60)
    print("Format: SONG - ARTIST")
    print("Enter a TXT path, or press Enter for manual input.\n")

    path_text = input("INPUT TXT FILE PATH: ").strip().strip("'\"")

    if path_text:
        path = Path(path_text).expanduser()

        if not path.is_file():
            print(f"File not found: {path}")
            return []

        try:
            lines = path.read_text(
                encoding="utf-8-sig"
            ).splitlines()
        except OSError as error:
            print(f"Could not read file: {error}")
            return []

        return [
            line.strip()
            for line in lines
            if line.strip() and not line.strip().startswith("#")
        ]

    print("\nEnter one SONG - ARTIST per line.")
    print("Type DONE on its own line when finished.\n")

    songs = []

    while True:
        line = input("> ").strip()

        if line.upper() == "DONE":
            break

        if line:
            songs.append(line)

    return songs


def choose_output_folder():
    default_folder = Path.home() / "Music" / "Downloads"

    print("\nChoose where downloads should be saved.")
    folder_text = input(
        f"OUTPUT FOLDER (Enter for {default_folder}): "
    ).strip().strip("'\"")

    output_dir = (
        Path(folder_text).expanduser()
        if folder_text
        else default_folder
    )

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        print(f"Cannot create output folder: {error}")
        return None

    return output_dir


def main():
    if not shutil.which("yt-dlp"):
        print("yt-dlp is missing.")
        print("Install with: sudo pacman -S yt-dlp ffmpeg")
        sys.exit(1)

    if not shutil.which("ffmpeg"):
        print("ffmpeg is missing.")
        print("Install with: sudo pacman -S yt-dlp ffmpeg")
        sys.exit(1)

    songs = load_songs()

    if not songs:
        print("No songs provided.")
        return

    output_dir = choose_output_folder()

    if output_dir is None:
        return

    print(f"\nLoaded {len(songs)} songs.")
    print(f"Output directory: {output_dir}")

    for index, song in enumerate(songs, 1):
        print("\n" + "=" * 48)
        print(f"[{index}/{len(songs)}] {song}")
        print("=" * 48)

        try:
            process_song(song, output_dir)
        except KeyboardInterrupt:
            print("\nCancelled.")
            return

    print("\nFinished processing all songs.")


if __name__ == "__main__":
    main()
