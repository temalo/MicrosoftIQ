# Metadata-only grounding probe — known limitation

**Observed result, not a supported grounding claim:** in the observed **Standard
runtime**, the isolated ontology-only Data Agent baseline was **unavailable**.
After persisting a source-element description, the answer was **still unavailable**.
This does not demonstrate successful metadata grounding or working instance joins.
Tenant/runtime/version behavior may change; reproduce and record your own results.
No actual tenant identifiers or service traces are included here.

## Reproduction (manually, in an isolated demo agent)

1. Use the synthetic model and reviewed entity/instance bindings. Create a separate
   Data Agent with **only the ontology** source; do not include semantic model,
   KQL database, knowledge files, reference answers or example Q&A.
2. Inspect the Data Agent source configuration and locate the BadgeScan entry in
   **`elements[].description`**. This is the **Data Agent source configuration**,
   **not the native ontology entity description**. Configuration shape varies by
   API/UI version: [`metadata-probe.json`](metadata-probe.json) is an illustrative
   fragment, not a REST payload. Select your actual ontology item/element through
   the supported editor; do not invent resource IDs or API schemas.
3. In a clean conversation before setting this description ask:
   “According to the BadgeScan entity description available in your ontology
   source metadata, what is Conference Engagement Rule CE-17? Explain its
   qualifying interactions and exclusions. If that description is unavailable,
   say so rather than infer an answer.”
   Record runtime, source selection, bindings, question, returned answer/error and
   timestamp. **Observed baseline: unavailable.**
4. Persist the description from the fragment: CE-17 requires **active licensed**
   plus **opt-in** plus **demo request or meeting booked**. Do not merely edit the
   ontology's native description. Re-read the source configuration to verify
   persistence, publish as required, and repeat the same question in a fresh chat.
   **Observed persisted-description result: still unavailable in Standard runtime.**
5. Keep the observed failure. Do not copy expected counts or a reference answer
   into instructions/knowledge to make the probe appear grounded. A business-rule
   description is the experimental input, not proof that the runtime consumed it.

After definition retrieval succeeds, a separate, not-yet-validated extension is:
“How many CE-17 eligible badge scans are there for ConferenceId 1 in RunId
`<chosen-run>` during `[<UTC-start>, <UTC-end>)`? Identify the source and rule.”
Do not describe this quantitative extension as an observed test result.

For the working architecture's intended query path, select the actual semantic
model measures (Delta) or explicitly add the KQL database (Eventhouse) to the
Data Agent and republish. Test that path independently; a successful direct KQL
query is not proof of ontology grounding or of published-agent tool routing.
