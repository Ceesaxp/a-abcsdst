# A-ABCDST (Automated Audiobook Chapter Detection and Segmentation Tool)

A-ABCDST is a Python tool for automatically detecting chapters in audiobooks and creating properly tagged MP3 files with optional M4B creation. The system uses Vosk speech recognition with phrase-only grammar to detect chapter markers, applies silence gating to reduce false positives, and outputs properly tagged MP3 files.

> 💡 So — you've found a bunch of tape cassettes or CDs with the audiobooks you used to listen to way before Audible. You ripped them into MP3s. But they are just blobs of sound a few hours long. You need to get them into _some kind of order_ for real listening pleasure: add cover art, tag with chapter marks, compile into an actual audiobook to use with a mobile device. That's what A-ABCDST does.

## 📋 Features

- **Automatic Chapter Detection**: Uses Vosk speech recognition with phrase-only grammar
- **Multi-language Support**: English and Russian chapter detection
- **Silence Gating**: Reduces false positives by requiring silence around chapter markers
- **Configurable Parameters**: Adjustable thresholds for confidence, silence detection, and chapter spacing
- **Audio Processing**: Handles MP3 concatenation, segmentation, and format conversion
- **Metadata Tagging**: Full ID3 tagging with cover art support
- **M4B Creation**: Optional audiobook format with embedded chapter markers
- **Sequential Chapter Enforcement**: Optional sequential chapter numbering validation
- **Back Matter Detection**: Supports detection of epilogues and appendices
- **Custom Phrase Support**: Ability to use custom chapter detection phrases

## 💻 System Requirements

### Required System Binaries
- **Python 3.12+**
- **ffmpeg** and **ffprobe** (for audio processing)
  - macOS: `brew install ffmpeg`
  - Ubuntu/Debian: `sudo apt install ffmpeg`
  - Windows: Download from [ffmpeg.org](https://ffmpeg.org/download.html)

### Vosk Model Files
- Download appropriate Vosk model for your language:
  - English: [vosk-model-small-en-us-0.15](https://alphacephei.com/vosk/models)
  - Russian: [vosk-model-small-ru-0.22](https://alphacephei.com/vosk/models)

... or any other language Vosk supports.

## 🗜️ Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd a-abcdst
```

2. Create and activate virtual environment:
```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -e .
```

## 🐍 Python Dependencies

The following Python packages are required (automatically installed with `pip install -e .`):

- **vosk** (>=0.3.42): Speech recognition engine for chapter detection
- **mutagen** (>=1.46.0): Audio metadata handling and ID3 tagging
- **requests** (>=2.31.0): HTTP client for downloading audio files
- **beautifulsoup4** (>=4.12.0): HTML parsing for the web scraper utility

## ⛩️ Project Structure

```
AATAOMM/
  main.py              # Main chapter detection script
  get_mp3s.py          # Utility script for downloading MP3 files
  mp3/                 # Input directory for numbered MP3 files
  book/                # Output directory for chapter-segmented MP3s
  covers/              # Optional cover art directory
  pyproject.toml       # Project configuration and dependencies
  README.md           # This file
```

## 🏃‍♂ Usage

### Basic Usage

Place your numbered MP3 files (01.mp3, 02.mp3, etc.) in the `mp3/` directory, then run:

```bash
python3 main.py \
  --model-path /path/to/vosk-model-small-en-us-0.15 \
  --album "Book Title" \
  --artist "Author Name (read by Narrator Name)"
```

### Advanced Example with All Options

```bash
python3 main.py \
  --model-path /models/vosk-model-small-en-us-0.15 \
  --album "Book Title" \
  --artist "Author Name (read by Narrator Name)" \
  --year "2001" \
  --genre "Philosophy" \
  --cover covers/cover.jpg \
  --language en \
  --min-chapter-gap 90 \
  --min-chapter-duration 180 \
  --silence-threshold -38 \
  --silence-pre 0.6 \
  --silence-post 0.8 \
  --sequential-chapters \
  --back-trigger "this concludes the reading of" \
  --make-m4b \
  --m4b-bitrate 128k
```

### M4B-Only Mode (Skip Chapter Detection)

Create M4B from existing chapter-segmented MP3s:

```bash
python3 main.py \
  --m4b-only /path/to/chapter/mp3s \
  --album "Book Title" \
  --artist "Author" \
  --cover cover.jpg
```

### Web Scraper Utility

Download MP3s from supported audiobook websites:

```bash
python3 get_mp3s.py
```

## 📺 Command Line Options

### Required Arguments
- `--album`: Album/book title for metadata
- `--artist`: Author and narrator information
- `--model-path`: Path to Vosk model directory (required for chapter detection)

### Language and Grammar Options
- `--language {en,ru}`: Language for chapter detection (default: en)
- `--trigger TEXT`: Custom chapter trigger word (default: "chapter" for en, "3;020" for ru)
- `--max-chapters INT`: Maximum chapters to detect (default: 120)
- `--include-ordinals`: Include ordinal numbers ("first chapter", "second chapter")
- `--phrases-file FILE`: Custom phrases file (one phrase per line)
- `--sequential-chapters`: Enforce sequential chapter numbering (1, 2, 3, ...)

### Audio Processing Options
- `--mp3-dir PATH`: Input MP3 directory (default: "mp3")
- `--out-dir PATH`: Output directory (default: "book")
- `--sample-rate INT`: Audio sample rate for analysis (default: 16000)

### Detection Tuning
- `--conf-min FLOAT`: Minimum confidence score (default: 0.35)
- `--min-chapter-gap FLOAT`: Minimum seconds between chapters (default: 90)
- `--min-chapter-duration FLOAT`: Minimum chapter length in seconds (default: 120)

### Silence Detection
- `--silence-threshold FLOAT`: dB threshold for silence (default: -38)
- `--silence-min FLOAT`: Minimum silence duration (default: 0.35)
- `--silence-pre FLOAT`: Required silence before chapter (default: 0.6)
- `--silence-post FLOAT`: Required silence after chapter (default: 0.8)

### Metadata and Output
- `--year TEXT`: Publication year
- `--genre TEXT`: Genre (default: "Audiobook")
- `--cover FILE`: Cover art image file
- `--make-m4b`: Create M4B audiobook format
- `--m4b-bitrate TEXT`: M4B audio bitrate (default: "80k")

### Special Features
- `--back-trigger TEXT`: Phrase marking start of back matter (e.g., "this concludes")
- `--m4b-only PATH`: Skip detection, create M4B from existing MP3s

## 🕵🏻‍♂️ How It Works

1. **Audio Preparation**: Concatenates all MP3s into a single file for analysis
2. **Silence Map Generation**: Uses ffmpeg to detect silence patterns throughout the audio
3. **Speech Recognition**: Uses Vosk with phrase-only grammar to detect chapter markers
4. **Silence Gating**: Filters detections that don't have appropriate silence patterns
5. **Chapter Validation**: Applies minimum gap and duration requirements
6. **Segmentation**: Creates individual MP3 files for each detected chapter
7. **Metadata Tagging**: Adds ID3 tags with album, artist, track numbers, and cover art
8. **M4B Creation**: Optionally creates audiobook format with embedded chapter markers

## 🎩 Supported Chapter Formats

### English
- Cardinal numbers: "chapter one", "chapter two", etc.
- Ordinal numbers (optional): "first chapter", "second chapter", etc.
- Bare trigger: "chapter" (ignored to reduce false positives)

### Russian
- Cardinal numbers: "глава один", "глава два", etc.
- Ordinal numbers (optional): "первая глава", "вторая глава", etc.
- Bare trigger: "глава" (ignored to reduce false positives)

## File Naming Conventions

### Input Files
- MP3 files must be numbered sequentially: `01.mp3`, `02.mp3`, etc.
- Files are sorted by name, so zero-padding is important for proper ordering

### Output Files
- Preface: `00_preface.mp3`
- Chapters: `01_chapter_1.mp3`, `02_chapter_2.mp3`, etc.
- Back matter: `XX_back_matter.mp3`
- M4B file: `{Album Title}.m4b`

## ✅ Configuration Tips

### Silence Threshold Tuning
- Start with default `-38dB` threshold
- For noisy audio: try `-35dB` or `-32dB`
- For very clean audio: try `-42dB` or `-45dB`
- Monitor the silence detection output to verify appropriate silence intervals

### Chapter Gap Settings
- `min-chapter-gap`: Prevents duplicate detections (default: 90 seconds)
- `min-chapter-duration`: Prevents tiny segments (default: 120 seconds)
- Adjust based on your audiobook's pacing and structure

### Confidence Levels
- `conf-min`: Speech recognition confidence threshold (default: 0.35)
- Lower values detect more chapters but may increase false positives
- Higher values reduce false positives but may miss valid chapters

## 😵‍💫 Troubleshooting

### Common Issues

**No chapters detected:**
- Verify Vosk model path is correct
- Check if silence detection found appropriate intervals
- Try adjusting `--silence-threshold` and `--conf-min`
- Enable `--include-ordinals` if the book uses "first chapter", etc.

**Too many false positives:**
- Increase `--conf-min` confidence threshold
- Increase `--min-chapter-gap` to space out detections
- Adjust silence gating parameters (`--silence-pre`, `--silence-post`)

**Missing dependencies:**
- Install ffmpeg system-wide
- Ensure Python 3.12+ is installed
- Run `pip install -e .` to install Python dependencies

**Audio format issues:**
- Ensure input files are valid MP3 format
- Check that files are named with zero-padded numbers (01.mp3, not 1.mp3)

### Debug Output
The tool provides verbose output showing:
- Silence intervals detected
- Chapter candidates found
- Filtering results at each stage
- Final segment boundaries

## 🪪 License

MIT License - see LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit issues and pull requests.
