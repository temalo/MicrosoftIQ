# Pitch deck

`build_slides.py` builds a 5-slide "Microsoft IQ" story deck, reading the
headline numbers from `../data/output/manifest.json` so it always matches the
generated data.

```bash
pip install -r ../requirements.txt   # python-pptx
python ../generate.py                # produces the manifest
python build_slides.py               # -> microsoft-iq-story.pptx
```

Set `BRAND` to rebrand: `BRAND="Acme Events" python build_slides.py`.

Slides:
1. **What the output looks like** — one question, four defensible licensed-user answers.
2. **The trusted foundation** — the ontology verbs and the Fabric → Foundry stack.
3. **Two questions the business asks** — top speakers and top sponsors (from the data).
4. **One agent, two grounded brains** — the orchestrator's routing.
5. **Ask it anything** — blended questions that use both sources.
