# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AATAOMM is a Python tool for automatically detecting chapters in audiobooks and creating tagged MP3 files. The system uses Vosk speech recognition with phrase-only grammar to detect chapter markers, applies silence gating to reduce false positives, and outputs properly tagged MP3 files with optional M4B creation.

## Architecture

### Core Components

- **main.py**: The primary script (`make_chapters.py`) that handles the complete chapter detection and audio processing pipeline
- **get_mp3s.py**: Web scraper utility to download MP3 files from audiobook websites
- **mp3/**: Input directory containing numbered MP3 files (01.mp3, 02.mp3, etc.)
- **book/**: Output directory where chapter-segmented MP3 files are written
- **concat.mp3**: Temporary concatenated audio file used for analysis

### Processing Pipeline

1. **Audio Concatenation**: Combines all MP3s from `mp3/` directory into a single file for analysis
2. **Silence Detection**: Uses ffmpeg silencedetect to build a silence map for gating
3. **Speech Recognition**: Uses Vosk with phrase-only grammar to detect chapter triggers
4. **Silence Gating**: Filters detections that don't have surrounding silence patterns
5. **Chapter Validation**: Applies minimum gap and duration requirements
6. **Audio Segmentation**: Creates individual MP3 files for each chapter
7. **ID3 Tagging**: Tags output files with metadata using mutagen
8. **Optional M4B Creation**: Builds M4B audiobook file with embedded chapters

### Language Support

Supports both English and Russian chapter detection with:
- Cardinal numbers ("chapter one", "chapter two", "глава один", "глава два")
- Optional ordinal numbers ("first chapter", "second chapter")
- Custom phrase files for specialized triggers
- Back matter detection ("this concludes the reading of...")

## Commands

### Environment Setup
```bash
# Activate virtual environment
source .venv/bin/activate

# Install dependencies (if needed)
pip install vosk mutagen requests beautifulsoup4
```

### Basic Usage
```bash
# Run chapter detection with basic settings
python3 main.py \
  --model-path /path/to/vosk-model \
  --album "Book Title" \
  --artist "Author Name (read by Narrator)"

# Example with all common options
python3 main.py \
  --model-path /models/vosk-model-small-en-us-0.15 \
  --album "Zen and the Art of Motorcycle Maintenance" \
  --artist "Robert M. Pirsig (read by Michael Kramer)" \
  --year "1974" \
  --min-chapter-gap 90 \
  --min-chapter-duration 180 \
  --silence-threshold -38 \
  --make-m4b \
  --cover covers/cover.jpg
```

### Utility Scripts
```bash
# Download MP3s from audiobook site
python3 get_mp3s.py
```

## Dependencies

### System Requirements
- Python 3.12+
- ffmpeg and ffprobe (for audio processing)
- Vosk model files (for speech recognition)

### Python Packages
- vosk: Speech recognition engine
- mutagen: Audio metadata handling
- requests: HTTP client for downloading
- beautifulsoup4: HTML parsing

## File Structure

- Input MP3s must be named numerically (01.mp3, 02.mp3, etc.) in `mp3/` directory
- Output files are written to `book/` directory with format: `00_preface.mp3`, `01_chapter_1.mp3`, etc.
- Temporary files (concat.mp3, analysis.wav) are created during processing
- Optional cover art can be placed in `covers/` directory

## Configuration Parameters

Key tunable parameters in main.py:
- `--min-chapter-gap`: Minimum seconds between chapter detections (default: 90)
- `--min-chapter-duration`: Minimum chapter length to avoid tiny segments (default: 120)
- `--silence-threshold`: dB threshold for silence detection (default: -38)
- `--silence-pre/post`: Silence gating window requirements (default: 0.6/0.8s)
- `--conf-min`: Minimum confidence for speech recognition matches (default: 0.35)