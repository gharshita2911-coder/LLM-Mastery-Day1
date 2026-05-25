# IT Helpdesk Bot — Microsoft Teams

A Python bot built with Microsoft Bot Framework that helps users troubleshoot
common IT issues step by step inside Microsoft Teams, and escalates unresolved
issues by email to the IT team.

---

## Project structure

```
it-helpdesk-bot/
├── app.py               # aiohttp web server entry point
├── bot.py               # conversation logic and Yes/No/Skip flow
├── knowledge_base.py    # 8 helpdesk categories with keywords and steps
├── escalation.py        # SMTP / Graph API email escalation
├── config.py            # environment variable configuration
├── requirements.txt     # Python dependencies
├── .env.example         # copy to .env for local development
├── README.md            # this file
└── teams_manifest/
    ├── manifest.json    # Microsoft Teams app manifest
    ├── color.png        # 192×192 px colour icon
    └── outline.png      # 32×32 px white outline icon on transparent background
```

---

## Supported helpdesk categories

| # | Category | Urgent escalation |
|---|---|---|
| 1 | Account & Access | No |
| 2 | Microsoft 365 | No |
| 3 | Hardware & Peripherals | No |
| 4 | Connectivity | No (sensitive info via DM) |
| 5 | Software & Updates | No |
| 6 | Performance | No |
| 7 | Security | **Yes** |
| 8 | Equipment Requests | No |

---

## Local development setup

### Prerequisites

- Python 3.11 or later
- [Bot Framework Emulator](https://github.com/microsoft/BotFramework-Emulator/releases) (optional but recommended for local testing)
- An Azure account (free tier is sufficient for development)

### 1. Clone and install

```bash
git clone https://github.com/yourorg/it-helpdesk-bot.git
cd it-helpdesk-bot
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in:

| Variable | Where to find it |
|---|---|
| `MicrosoftAppId` | Azure Portal → App Registration → Overview → Application (client) ID |
| `MicrosoftAppPassword` | Azure Portal → App Registration → Certificates & secrets → New client secret |
| `SMTP_USER` | The FROM address for escalation emails |
| `SMTP_PASSWORD` | App password for that mailbox (not your personal password) |
| `IT_TEAM_EMAIL` | The IT team's shared mailbox |

For local testing with Bot Framework Emulator, you can leave `MicrosoftAppId`
and `MicrosoftAppPassword` **blank** — the emulator does not require auth.

### 3. Run the bot

```bash
python app.py
```

The server starts at `http://localhost:3978`.

### 4. Test with Bot Framework Emulator

1. Open Bot Framework Emulator.
2. Click **Open Bot**.
3. Set Bot URL to: `http://localhost:3978/api/messages`
4. Leave App ID and password blank for local testing.
5. Click **Connect**.
6. Type `menu` to begin.

---

## Azure deployment

### Step 1 — Create an Azure App Registration

1. Azure Portal → **Azure Active Directory** → **App registrations** → **New registration**.
2. Name: `IT Helpdesk Bot`, Supported account types: **Accounts in any organizational directory**.
3. Click **Register**. Copy the **Application (client) ID** — this is your `MicrosoftAppId`.
4. Go to **Certificates & secrets** → **New client secret**. Copy the secret value immediately — this is your `MicrosoftAppPassword`.

### Step 2 — Create an Azure Bot resource

1. Azure Portal → **Create a resource** → search **Azure Bot** → **Create**.
2. Bot handle: choose a unique name (e.g. `it-helpdesk-bot-prod`).
3. Pricing tier: **F0** (free) is sufficient for internal use.
4. Microsoft App ID: paste the App ID from Step 1.
5. Click **Create**.

### Step 3 — Enable the Microsoft Teams channel

1. Open the Azure Bot resource → **Channels** → **Microsoft Teams** → **Apply**.
2. Accept the Terms of Service.

### Step 4 — Deploy code to Azure App Service

#### Option A — Deploy via Azure CLI (recommended)

```bash
az login
az webapp up \
  --name it-helpdesk-bot \
  --resource-group your-resource-group \
  --runtime "PYTHON:3.11" \
  --sku B1
```

#### Option B — Deploy via GitHub Actions

Add a workflow file at `.github/workflows/deploy.yml` using the
`azure/webapps-deploy@v2` action. The Azure App Service publish profile
is available under the App Service → Deployment Center.

### Step 5 — Set application settings on Azure

In Azure Portal → App Service → **Configuration** → **Application settings**,
add all variables from your `.env` file:

```
MicrosoftAppId          = <your app id>
MicrosoftAppPassword    = <your client secret>
SMTP_HOST               = smtp.office365.com
SMTP_PORT               = 587
SMTP_USER               = helpdesk-bot@yourcompany.com
SMTP_PASSWORD           = <app password>
IT_TEAM_EMAIL           = it-team@yourcompany.com
```

### Step 6 — Update the messaging endpoint

In Azure Portal → Azure Bot resource → **Configuration** → **Messaging endpoint**:

```
https://<your-app-name>.azurewebsites.net/api/messages
```

---

## Teams app registration

### Step 1 — Prepare icons

- `color.png` — 192×192 px, your company / bot logo with colour
- `outline.png` — 32×32 px, white icon on transparent background

Place both inside `teams_manifest/`.

### Step 2 — Edit manifest.json

Open `teams_manifest/manifest.json` and replace every instance of
`YOUR_BOT_APP_ID_HERE` with your `MicrosoftAppId`.

Update the `developer` section with your company's actual URLs.

### Step 3 — Package the manifest

```bash
cd teams_manifest
zip it-helpdesk-bot.zip manifest.json color.png outline.png
```

### Step 4 — Sideload for testing

1. Open Microsoft Teams → **Apps** → **Manage your apps** → **Upload an app**.
2. Select `it-helpdesk-bot.zip`.
3. The bot will appear in your Apps list — click **Add** to start a personal chat.

### Step 5 — Publish to your organisation (optional)

1. Teams Admin Center → **Teams apps** → **Manage apps** → **Upload**.
2. Upload the same ZIP. The bot becomes available to all users in your tenant.

---

## Environment variables reference

| Variable | Required | Description |
|---|---|---|
| `MicrosoftAppId` | Yes | Azure app registration client ID |
| `MicrosoftAppPassword` | Yes | Azure app registration client secret |
| `PORT` | No | Web server port (default: 3978) |
| `SMTP_HOST` | Yes (SMTP) | SMTP server hostname |
| `SMTP_PORT` | Yes (SMTP) | SMTP port — 587 (STARTTLS) or 465 (SSL) |
| `SMTP_USER` | Yes (SMTP) | Sender email address |
| `SMTP_PASSWORD` | Yes (SMTP) | App password for SMTP mailbox |
| `IT_TEAM_EMAIL` | Yes | Recipient address for escalation emails |
| `USE_GRAPH_EMAIL` | No | `true` to switch to Graph API email |
| `GRAPH_TENANT_ID` | If Graph | Azure AD tenant ID |
| `GRAPH_CLIENT_ID` | If Graph | App registration for Graph API |
| `GRAPH_CLIENT_SECRET` | If Graph | Client secret for Graph API |

---

## Production improvements

The following are known limitations of the current implementation that should
be addressed before wide production rollout:

**State storage**
The bot currently uses `MemoryStorage`, which is wiped on every application
restart (e.g. deployments, App Service restarts). Replace it with
`CosmosDbPartitionedStorage` or `BlobStorage` from `botbuilder-azure`:

```python
from botbuilder.azure import CosmosDbPartitionedStorage, CosmosDbPartitionedConfig

storage = CosmosDbPartitionedStorage(
    CosmosDbPartitionedConfig(
        cosmos_db_endpoint=os.environ["COSMOS_ENDPOINT"],
        auth_key=os.environ["COSMOS_KEY"],
        database_id="helpdesk-bot",
        container_id="conversations",
    )
)
```

**Email via Microsoft Graph API**
Switch `USE_GRAPH_EMAIL=true` and configure the Graph credentials to avoid
storing an SMTP password. The Graph API uses OAuth 2.0 client credentials,
which is more secure and compatible with modern authentication policies.

**Observability**
Add Azure Application Insights for structured logging, exception tracking,
and usage analytics:

```bash
pip install opencensus-ext-azure
```

**NLP / intent detection**
Replace the keyword-matching in `knowledge_base.py` with Azure Language
Understanding (CLU) or a lightweight embeddings-based classifier to handle
more natural and varied user phrasing.

**Adaptive Cards**
Replace plain-text menus with Adaptive Cards for a richer Teams UI
(buttons, images, input fields) using the `botbuilder-core` card builder.

**Multi-language support**
Add Azure Cognitive Services Translator to detect and respond in the user's
language.

**Ticket system integration**
Connect escalation to ServiceNow, Jira Service Management, or Azure DevOps
Boards instead of (or in addition to) email, using their REST APIs.

---

## License

MIT — see LICENSE file.
