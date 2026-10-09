# ytdlp-installer

An interactive terminal tool that searches YouTube for a list of songs and
downloads each one as an MP3 using [`yt-dlp`](https://github.com/yt-dlp/yt-dlp).

Give it a TXT file of songs (or type them in), and it will search, score how
well each result matches your request, let you approve or pick a result, and
save the audio to a folder of your choice.

## Requirements

- Python 3.8+
- [`yt-dlp`](https://github.com/yt-dlp/yt-dlp)
- [`ffmpeg`](https://ffmpeg.org/)

The script checks for both on startup and tells you how to install them if
they are missing. On Arch Linux:

```bash
sudo pacman -S yt-dlp ffmpeg
```

Other platforms: `pip install yt-dlp` (or your package manager) plus any
`ffmpeg` package.

## Usage

```bash
python3 dl.py
```

1. **Song list** — paste the path to a TXT file, or press Enter to type songs
   manually (one per line, `DONE` when finished).
2. **Output folder** — press Enter to use `~/Music/Downloads`, or type a path.
3. For each song, review the results and answer the prompt:
   - `y` — download the top match (if it scores at least 50%)
   - `n` — skip this song
   - `ls` — pick a different result by number

### Song list format

One song per line, using `SONG - ARTIST`:

```text
# comments and blank lines are ignored
Yellow - Coldplay
Smells Like Teen Spirit - Nirvana
Take On Me - a-ha
Bohemian Rhapsody - Queen
```

Plain titles without an artist (`Wonderwall`) also work, but adding the artist
makes matching much more accurate.

A UTF-8 BOM (as written by some Windows editors) is handled automatically.

## How matching works

Each search result gets a score from 0–100% comparing your request against
the video's title and channel:

- Text is normalized (lowercased, punctuation and noise words like
  `official`, `lyrics`, `hd`, `4k` removed)
- Similarity is measured with `difflib.SequenceMatcher` plus a word-overlap
  check
- When you specify `SONG - ARTIST`, the score is weighted **70% song /
  30% artist**

Results below `MIN_MATCH` (50%) are refused until you pick a different result
with `ls`, so the tool won't silently download the wrong track. If a download
fails, it automatically tries the next matching result in the list.

## Output

Audio is extracted to MP3 at the highest quality (`--audio-quality 0`) into
your chosen folder, named `Title [video-id].mp3`. Existing files are never
overwritten (`--no-overwrites`).

## Configuration

Constants at the top of `dl.py`:

| Constant      | Default | Meaning                                  |
| ------------- | ------- | ---------------------------------------- |
| `MAX_RESULTS` | `10`    | Number of YouTube search results to fetch |
| `MIN_MATCH`   | `50`    | Minimum match score (%) required to download |

## Notes

- Press `Ctrl+C` at any point to cancel the current song and stop.
- Respect the terms of service of the sites you download from, and only
  download content you have the right to use.

## License

Use and modify freely.
