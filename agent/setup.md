# End-to-end setup

This walks you from an empty workspace to the full **Microsoft IQ** loop:

```
CSV data ─► Fabric lakehouse ─► Direct Lake semantic model ─► Fabric IQ ontology
                                          │
                                          ├─► Fabric Data Agent (numbers)
knowledge/*.md ─► Foundry IQ knowledge ───┤
                                          └─► Foundry Agent orchestrator ─► web app
```

## 0. Prerequisites

- A Microsoft **Fabric** capacity + workspace.
- An **Azure AI Foundry** resource (AIServices account) and a project.
- **Python 3.9+**, **Node 18+**, and the **Azure CLI** (`az`).

## 1. Generate the data and knowledge

```bash
pip install -r requirements.txt   # (stdlib only; nothing to install for the generator)
python generate.py
```

Produces `data/output/*.csv`, `data/output/manifest.json` and
`knowledge/files/*.md`. The manifest records the reproducible headline answers.

## 2. Fabric lakehouse

1. Create a lakehouse named **`ConferencesData`**.
2. Upload every CSV from `data/output/` into the lakehouse's `Files/seed/` folder.
3. Create a notebook attached to the lakehouse, paste `data/load_to_fabric.py`,
   and run it. You now have one Delta table per CSV.

## 3. Semantic model (Direct Lake)

Follow **[agent/semantic-model.md](semantic-model.md)** — create the relationships
and paste the DAX measures. Verify the headline answers match `manifest.json`.

## 4. Ontology (Fabric IQ)

Follow **[agent/ontology.md](ontology.md)** — create the 13 entity types bound to
the lakehouse and the relationships. (Optional but completes the story.)

## 5. Fabric Data Agent

1. Create a Data Agent over the **`ConferencesData` semantic model**.
2. Add all tables as data sources.
3. Paste **[agent/fabric-data-agent-instructions.md](fabric-data-agent-instructions.md)**
   as the instructions (the top routing rule is essential).
4. **Publish**, then note the **workspace ID** and the **data agent (artifact) ID**
   from the URL — you'll need both for the orchestrator and the app.

## 6. Foundry model deployments

In your Foundry project, deploy:
- `gpt-4o` (chat) — used by the orchestrator and the knowledge base.
- `text-embedding-3-large` — used to embed the knowledge files.

## 7. Foundry IQ knowledge base

1. In the project, connect an **Azure AI Search** resource and create a knowledge
   base (e.g. `conference-knowledge`) using `gpt-4o` + `text-embedding-3-large`.
2. Upload all files from `knowledge/files/`.
3. **RBAC gotcha:** if API-key auth is disabled on the Foundry resource, the
   Search service must have a **managed identity** with the **Cognitive Services
   User** role on the Foundry resource — otherwise uploads fail with
   "File upload processing failed". Enable a system-assigned identity on the
   Search service and grant that role, then retry the upload.

## 8. Foundry Agent orchestrator

1. Create an agent (e.g. `ConferenceIQ-Orchestrator`) on `gpt-4o`.
2. Paste **[agent/orchestrator-instructions.md](orchestrator-instructions.md)**.
3. Add the **Fabric Data Agent** tool — supply the workspace ID and data agent
   (artifact) ID from step 5.
4. Under **Knowledge**, connect the `conference-knowledge` base from step 7.
5. **Save** and **Publish**. Note the **project name** and **agent name**.

## 9. Grant the calling identity data-plane access

The web app calls the agent as the signed-in user. Grant that identity the
**Cognitive Services OpenAI User** role on the Foundry resource (control-plane
Owner is *not* enough — it does not grant inference/agent data actions):

```bash
az role assignment create \
  --assignee <your-object-id> \
  --role "Cognitive Services OpenAI User" \
  --scope /subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<foundry-account>
```

## 10. Run the web app

```bash
cd app
cp ../.env.example .env      # then edit .env with your values
node server.js               # open http://localhost:3000
```

Sign in, then try the two headline questions and a knowledge question. See
**[app/README.md](../app/README.md)** for the exact endpoint contract.

## 11. (Optional) The pitch deck

```bash
cd slides
python build_slides.py       # reads data/output/manifest.json for the numbers
```
