# Research and scope

Sources retrieved on 2026-11-03. No upstream implementation was copied.

## Facts from sources

- [HAR 1.2 maintainer transcription](https://raw.githubusercontent.com/ahmadnassri/har-spec/master/versions/1.2.md): UTF-8/BOM handling; entry time in milliseconds; response bodySize and content.size have different meanings when compressed. This is a maintained transcription of the original creator documentation, not an official current W3C standard. The original creator blog was unavailable in the batch source check. The abandoned W3C HAR draft is not treated as a current standard.
- [Chrome DevTools network reference](https://developer.chrome.com/docs/devtools/network/reference#save-as-har): supports HAR export/import, with sanitized and sensitive-data export options. Sanitized export excludes selected sensitive headers; this tool does not certify or sanitize the source archive.
- [Browsertime](https://github.com/sitespeedio/browsertime): a Node.js browser performance measurement tool with scripting and broader page/visual metrics.

## Design inference

An offline, dependency-free per-entry gate can serve a smaller task than a browser measurement suite. This is a product hypothesis, not user adoption evidence. Requiring explicit budgets and failing on unknown measurements makes the policy reviewable. Restricting output to numbers and fixed codes reduces accidental report disclosure; it does not establish that source HAR data is safe to share. The integer bodySize restriction and resource caps are local policy decisions, not claims of full specification compliance.

## Fair alternatives

Use Chrome DevTools to inspect requests visually or obtain a fresh export. Use Browsertime when repeatable browser runs and page-level performance metrics matter. A full schema validator is more appropriate for HAR structural compliance. This tool is useful only when a previously captured local archive needs a small numeric gate with stable value-free identifiers. No speed, quality or completeness superiority over those alternatives has been measured.

The tests are synthetic local checks. They do not measure network performance, validate browser export fidelity, or establish demand.
