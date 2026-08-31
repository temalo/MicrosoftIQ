# Web client — Microsoft IQ agent

A tiny, zero-dependency Node app to chat with the published Foundry orchestrator
agent from outside the Foundry portal, with configurable branding.

## Configure

```bash
cp ../.env.example .env
# edit .env:
#   BRAND=Contoso Events
#   FOUNDRY_ACCOUNT=https://<your-foundry>.services.ai.azure.com
#   FOUNDRY_PROJECT=<your-project>
#   FOUNDRY_AGENT=ConferenceIQ-Orchestrator
```

## Run

```bash
node server.js          # open http://localhost:3000
```

Click **Sign in with Microsoft** and complete the device-code flow with an
account that has the **Cognitive Services OpenAI User** data-plane role on the
Foundry resource. Then try the two headline questions and a knowledge question.

## How it works

- `server.js` is a Node HTTP proxy (built-in modules + global `fetch`; a tiny
  built-in `.env` loader, no npm install).
- Device-code sign-in (Azure CLI public client) mints an
  `https://ai.azure.com/.default` token.
- Each turn is POSTed server-side to the project **Responses API**, referencing
  the agent by name; multi-turn context chains via `previous_response_id`. The
  token never leaves the server.
- `{{BRAND}}` in `public/index.html` is replaced at serve time with `BRAND`.

## Endpoint contract (verified)

```
POST {FOUNDRY_ACCOUNT}/api/projects/{FOUNDRY_PROJECT}/openai/responses?api-version=2025-05-15-preview
Authorization: Bearer <https://ai.azure.com/.default token>

{ "input": "<question>",
  "agent": { "type": "agent_reference", "name": "<FOUNDRY_AGENT>" },
  "previous_response_id": "<prior id>"   // optional, multi-turn
}
```

The answer is read from `output[]` → the `message` item → `content[]` where
`type === "output_text"`.

> **Why the project path?** The account-root Azure OpenAI path
> (`.../openai/responses`) only accepts model *deployments*, not agents. The
> **project** path above routes to the Foundry agent runtime, which runs the
> agent's tools (Fabric Data Agent + Foundry IQ knowledge).

## Config (env)

| Var | Default | Notes |
|-----|---------|-------|
| `PORT` | `3000` | |
| `BRAND` | `Contoso Events` | shown in the header/hero/footer |
| `FOUNDRY_ACCOUNT` | placeholder | `https://<account>.services.ai.azure.com` |
| `FOUNDRY_PROJECT` | placeholder | Foundry project name |
| `FOUNDRY_AGENT` | `ConferenceIQ-Orchestrator` | published agent name |
| `FOUNDRY_API_VERSION` | `2025-05-15-preview` | |
| `AZURE_TENANT` | `organizations` | tenant id or domain, optional |
