## docs_workflow

Automation to turn real-world developer feedback into actionable documentation improvements. It ingests messages from Discord, clusters them with LLM + embeddings, finds the most relevant doc page from a vector DB, asks an LLM to propose concrete edits, creates a Linear issue, and stores the ticket + suggestion for a feedback loop that updates status when the Linear issue changes.

### High-level architecture
- **AWS SAM** deploys all infrastructure defined in `template.yaml`.
- **AWS Step Functions** orchestrates the workflow on a schedule (`rate(7 days)` by default).
- **AWS Lambda** handlers (under `src/handlers/`) implement each step:
  - `ingest_discord`: Pulls recent non-bot messages and threads from configured Discord channels.
  - `cluster_insights`: Uses OpenAI to extract issues per channel, embeds with OpenAI, clusters with DBSCAN, and filters for significance.
  - `find_docs`: Embeds the insight summary and queries Pinecone to find the most relevant documentation page.
  - `generate_suggestion`: Uses OpenAI to propose a concrete, actionable doc change.
  - `create_linear_ticket`: Creates a ticket in Linear (GraphQL API) including quotes, doc link, and suggested change.
  - `store_in_dynamodb`: Persists ticket metadata and suggestion for the feedback loop.
  - `process_linear_webhook`: Receives Linear webhooks via API Gateway (HttpApi) and updates the DynamoDB record status.
- **AWS Secrets Manager** holds API keys; `src/shared/utils.py` loads secrets (cached) either from env (local) or Secrets Manager (deployed).
- **Amazon DynamoDB** stores issue records and lifecycle status.
- **Amazon EventBridge** triggers the Step Functions state machine on a schedule.

### State machine flow
Defined in `statemachine/workflow.asl.json` and wired via `template.yaml` substitutions:
1) Ingest Discord Messages → 2) Cluster and Summarize Insights → 3) Map over clusters:
   - Find Relevant Docs → Generate Suggestion → Create Linear Ticket → Store Ticket in DynamoDB

### Repository layout
- `template.yaml`: SAM/CloudFormation template (all resources, IAM, env vars, schedule, API).
- `statemachine/workflow.asl.json`: Step Functions definition.
- `src/handlers/`: Lambda handlers for each workflow step and the Linear webhook endpoint.
- `src/shared/utils.py`: Secrets loading helper.
- `src/requirements.txt`: Runtime dependencies for Lambdas.
- `samconfig.toml`: Default deployment parameters (stack name, region, parameter overrides).

### Prerequisites
- AWS account with permissions for Lambda, Step Functions, EventBridge, API Gateway, DynamoDB, Secrets Manager.
- AWS SAM CLI (`sam --version`).
- Python 3.12.
- Accounts/keys for:
  - Discord (bot token with channel read permissions)
  - Linear (API key, project ID, team ID)
  - OpenAI (API key)
  - Pinecone (API key; index pre-populated with your docs, see below)

### Configuration and secrets
Secrets are read via `src/shared/utils.get_secrets()`:
- Local: set `AWS_SAM_LOCAL=true` and provide secrets as environment variables.
- Deployed: functions read `SECRETS_ARN` and fetch a JSON secret from AWS Secrets Manager.

Expected secret keys (JSON object):
```json
{
  "DISCORD_BOT_TOKEN": "...",
  "LINEAR_API_KEY": "...",
  "OPENAI_API_KEY": "...",
  "PINECONE_API_KEY": "...",
  "PINECONE_ENVIRONMENT": "optional-for-sdk-compat",
  "PINECONE_INDEX_NAME": "your-docs-index"
}
```

Environment variables set via `template.yaml`:
- Global to all functions: `SECRETS_ARN`, `DYNAMODB_TABLE`.
- Function-specific:
  - `ingest_discord`: `DISCORD_CHANNEL_IDS` (comma-separated)
  - `create_linear_ticket`: `LINEAR_PROJECT_ID`, `LINEAR_TEAM_ID`

Deployment parameters (from `samconfig.toml` or `sam deploy --guided`):
- `LinearProjectID`, `LinearTeamID`, `DiscordChannelIDs`.

### Pinecone index
`find_docs` expects a Pinecone index containing document chunks with metadata like:
```json
{
  "id": "doc-chunk-id",
  "values": [0.01, -0.02, ...],
  "metadata": {
    "url": "https://docs.example.com/path",
    "text": "The text of the documentation chunk..."
  }
}
```
Ensure `PINECONE_INDEX_NAME` exists and is populated. The code queries `top_k=1` and returns the matched `metadata`.

### Local development
Install dependencies (for local testing):
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r src/requirements.txt
```

Provide local env (example):
```bash
export AWS_SAM_LOCAL=true
export DISCORD_BOT_TOKEN=xxxxx
export DISCORD_CHANNEL_IDS=123,456
export LINEAR_API_KEY=xxxxx
export OPENAI_API_KEY=xxxxx
export PINECONE_API_KEY=xxxxx
export PINECONE_INDEX_NAME=docs-index
```

Invoke a function locally (examples):
```bash
# Ingest recent messages
echo '{"since_days": 7}' | sam local invoke IngestDiscordFunction

# Cluster insights from a sample conversations payload
echo '{"conversations": []}' | sam local invoke ClusterInsightsFunction

# Start the local API (for webhook testing)
sam local start-api --port 3000
# POST to http://127.0.0.1:3000/linear-webhook
```

### Deploy
First deployment (guided):
```bash
sam build
sam deploy --guided
```

Subsequent deploys (uses `samconfig.toml`):
```bash
sam build && sam deploy
```

After deploy:
- Go to the stack outputs and copy `StateMachineArn` and `WebhookApiUrl`.
- Update the Secrets Manager secret created by the stack (`AWSSecuritySecrets`) with your real keys:
```bash
aws secretsmanager put-secret-value \
  --secret-id <YOUR_SECRET_ARN_OR_NAME> \
  --secret-string '{
    "DISCORD_BOT_TOKEN": "...",
    "LINEAR_API_KEY": "...",
    "OPENAI_API_KEY": "...",
    "PINECONE_API_KEY": "...",
    "PINECONE_INDEX_NAME": "docs-index"
  }'
```
- Configure a Linear webhook to POST updates to `WebhookApiUrl` and include issue state changes.

### Operations
- The workflow runs on a schedule (`rate(7 days)`). Adjust `ScheduledRule` in `template.yaml` if needed.
- Inspect executions in Step Functions; view Lambda logs in CloudWatch.
- DynamoDB table: `TicketsTable` stores items with keys like:
  - `ticket_id`, `ticket_identifier`, `ticket_url`
  - `insight_summary`, `llm_suggestion`, `doc_url`
  - `status` (updated by `process_linear_webhook`)

### Error handling and troubleshooting
- **Secrets not found**: Ensure `SECRETS_ARN` is set by SAM and the secret contains all keys.
- **Discord 401/403**: Check `DISCORD_BOT_TOKEN` and channel permissions.
- **No Pinecone index**: `find_docs` raises if `PINECONE_INDEX_NAME` is missing or not found.
- **Linear GraphQL errors**: Verify `LINEAR_API_KEY`, `LINEAR_PROJECT_ID`, `LINEAR_TEAM_ID` and that the token has access.
- **Rate limits / timeouts**: Adjust `Globals.Function.Timeout/MemorySize` in `template.yaml`.

### Customization
- Swap OpenAI models in `cluster_insights.py` and `generate_suggestion.py`.
- Tune clustering (`DBSCAN` `eps`/`min_samples`) and significance rules in `cluster_insights.is_issue_significant`.
- Increase `Map.MaxConcurrency` in the state machine for higher throughput.
- Modify the Linear ticket description template in `create_linear_ticket.py`.

### Security
- IAM role `WorkflowLambdaRole` grants only needed access (Secrets Manager read, DynamoDB write, Lambda invoke via state machine). API Gateway is allowed to invoke `process_linear_webhook`.
- Do not commit secrets. Use AWS Secrets Manager in production.

### License
Add a license file if you plan to distribute this project.

### Contributing
Open a PR or issue with improvements, bug reports, or feature ideas.
