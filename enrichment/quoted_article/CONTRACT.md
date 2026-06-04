# enrichment/quoted_article

Quoted article enrichment resolves linked or quoted content referenced by social posts.

## Current State

This is a future boundary. X ingestion should preserve quote/link metadata now, and this folder will later decide whether a linked article becomes the main content.

## Inputs

- Post URL, quoted URL, title hints, and source metadata.

## Outputs

- Linked article metadata.
- Extracted article body where available.
- Failure reason when inaccessible.
- Decision payload: use post, quoted article, or both.

## Boundary

This folder does not fetch X timelines and does not write the final digest.
