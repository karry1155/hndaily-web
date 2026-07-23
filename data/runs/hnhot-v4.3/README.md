# hnhot-v4.3 production run

- `source/`: crawler output, one immutable newspaper issue per date.
- `input/`: deterministic semantic inputs with location candidates and topics.
- `enrichment/`: schema 13 first-pass responses awaiting or passing validation.
- `audit/`: deterministic prefilter and publication audits.

This run is selected by `../../active-run.json`. Public validated content is
written to `../../../content/` only after the complete response passes.

