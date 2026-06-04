# Context: Phase 13 n8n Export Adapter

Phase 12 made `workflow/diagram/daily-newsletter.graph.json` the canonical executable workflow graph. Phase 13 exports that graph into n8n workflow JSON so n8n can become a visual editor/runtime layer without becoming the hidden source of truth.

This phase does not import the workflow into a running n8n instance and does not enable production schedules.

