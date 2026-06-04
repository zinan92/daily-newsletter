# enrichment/media

Media enrichment turns discovered video/audio items into reader-ready media summaries.

## Current Root Entrypoint

- `fetch-media-transcripts.py`

## Inputs

- Media candidate URL, title, source, and metadata from YouTube, podcast, or Douyin ingestion.
- Runtime download/transcription dependencies such as cookies, yt-dlp, MLX Whisper, or content-toolkit.

## Outputs

- Transcript or failure reason.
- Cleaned transcript when available.
- Deep Chinese summary.
- `publishable` flag and reason.

## Boundary

This folder owns no source discovery. It owns cross-channel media processing and the promo/no-transcript/too-short rejection contract.
