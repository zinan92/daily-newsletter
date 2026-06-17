# enrichment/media

Media enrichment turns discovered video/audio items into reader-ready media summaries.

## Current Root Entrypoint

- `fetch-media-transcripts.py`

## Implementation

- `enrichment/media/run.py`

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

## Long Media Policy

- YouTube / podcast items should not be dropped merely because they exceed the normal 90-minute ASR window.
- Long YouTube audio is downloaded once, split into configurable segments, transcribed segment-by-segment with MLX Whisper, then concatenated into one transcript.
- Douyin keeps the 90-minute cap because these sources are short-video channels; an over-90-minute Douyin item is treated as abnormal long media and skipped.
- Failed YouTube downloads and segment transcriptions use retry logic; durable failures stay in `media-summaries.json` / status, not in the consumer newsletter.
