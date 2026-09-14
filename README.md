# slack-tools

Handy Slack tools for automation and bulk operations (e.g., sending mass DMs, etc.)

## Setup

### Prerequisites

- Python 3.8+
- A Slack Workspace where you have admin/app permissions
- A Slack App created in your workspace

### Installation

1. **Clone the repository:**

   ```bash
   git clone <repository-url>
   cd slack-tools
   ```

2. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

3. **Configure your Slack App:**
   - Copy `.env.example` to `.env` and fill in your credentials
   - See [Slack App Configuration](#slack-app-configuration) below

### Configuration

#### Environment Variables

Create a `.env` file in the root directory with:

```env
SLACK_BOT_TOKEN=xoxb-your-token-here
SLACK_SIGNING_SECRET=your-signing-secret-here
SLACK_APP_ID=your-app-id-here
```

Get these values from your Slack App settings at https://api.slack.com/apps

## Slack App Configuration

### Required OAuth Scopes

Add the following scopes to your Slack App in the **OAuth & Permissions** section:

#### For Mass DM Script (`scripts/mass_dm.py`)

- **`chat:write`** - Send messages to users
- **`conversations:open`** - Open direct message conversations with users
- **`users:read`** - Read user information (optional, for validation)
- **`users:read.email`** - Read user email addresses (optional)

#### General Scopes (Recommended)

- **`app_mentions:read`** - Read mentions of your app
- **`channels:history`** - Read message history in channels
- **`im:history`** - Read direct message history
- **`team:read`** - Read workspace information

### Step-by-Step Setup

1. Go to https://api.slack.com/apps
2. Select or create your app
3. Navigate to **OAuth & Permissions** in the left sidebar
4. Scroll to **Scopes** section
5. Under **Bot Token Scopes**, add the required scopes above
6. Click **Install to Workspace** (or **Reinstall** if updating scopes)
7. Copy the **Bot User OAuth Token** (starts with `xoxb-`)
8. Paste it in your `.env` file as `SLACK_BOT_TOKEN`

## Project Structure

```
slack-tools/
├── input/              # Place input files here (JSON with recipients)
├── output/             # Script results and logs are saved here
├── scripts/            # All automation scripts
│   ├── mass_dm.py      # Send mass DMs to users
│   └── undo_dm.py      # Delete messages from a previous mass DM campaign
├── .env                # API credentials (DO NOT commit)
├── .gitignore          # Ignore sensitive files
├── requirements.txt    # Python dependencies
├── README.md           # This file
└── LICENSE
```

## Scripts

### Mass DM Script (`scripts/mass_dm.py`)

Send personalized direct messages to multiple Slack users with markdown formatting and mentions.

#### Two Modes

**Default Mode (Same message for all):**

- Single message sent to multiple users
- Input format: `message` + array of `slack_ids`
- Usage: `python scripts/mass_dm.py`

**Per-User Mode (Different message per user):**

- Each user gets a personalized message
- Input format: Array of `{user_id, message}` objects
- Usage: `python scripts/mass_dm.py --per-user`

#### Usage

1. **Create an input file** in the `input/` directory with recipients:

**Default Mode (`input/recipients.json`):**

```json
{
  "message": "Hey everyone! 📢 Check out this *important update* and visit <https://example.com|our website>",
  "slack_ids": ["U12345ABC", "U67890XYZ", "U11111111"]
}
```

**Per-User Mode (`input/recipients.json` with `--per-user` flag):**

```json
[
  {
    "user_id": "U12345ABC",
    "message": "Hey Alice! 👋 *Important:* Please review the new docs at <https://docs.example.com|here>"
  },
  {
    "user_id": "U67890XYZ",
    "message": "Hey Bob! 📝 Check out this `code snippet`"
  },
  {
    "user_id": "U11111111",
    "message": "Hi Team! We're launching _new features_ tomorrow!"
  }
]
```

2. **Run the script:**

   ```bash
   # Default mode (same message)
   python scripts/mass_dm.py

   # Per-user mode (different messages)
   python scripts/mass_dm.py --per-user
   ```

3. **Confirm twice:** The script will show you:
   - The message(s) to be sent
   - A list of recipients with their Slack display names
   - Ask for confirmation TWICE before sending

4. **Get your Sent ID:** After sending, you'll receive a unique **Sent ID** that you can use to undo

5. **Check results** in `output/`:
   - `sent_<id>.json` - Detailed results for each message
   - `sent_<id>_summary.txt` - Summary statistics

#### Undo Messages

Each mass DM campaign gets a unique **Sent ID**. Use it to delete all messages:

```bash
python scripts/undo_dm.py <sent_id>
```

Example:

```bash
python scripts/undo_dm.py a1b2c3d4
```

The undo script will:

- Show what messages will be deleted
- Ask for confirmation TWICE
- Delete all messages from that campaign
- Report how many were successfully deleted

#### Finding User IDs

To get a user's ID:

1. In Slack, click on a user's profile
2. Click the **...** menu and select **Copy user ID**
3. User IDs start with `U` (e.g., `U12345ABC`)

#### Features

- ✅ **Two input modes:**
  - Default mode: Send the same message to all users
  - Per-user mode: Send personalized messages with `--per-user` flag

- ✅ **Dual confirmation:** Asks for confirmation twice before sending to prevent accidents

- ✅ **Sent ID tracking:** Every batch gets a unique ID for future reference

- ✅ **Undo capability:** Delete all messages from a campaign using the Sent ID

- ✅ **Display names in confirmation:** Shows Slack display names for recipients (not just IDs)

- ✅ **Slack markdown formatting support:**
  - **Bold:** `*text*`
  - _Italic:_ `_text_`
  - ~~Strikethrough:~~ `~text~`
  - `Inline code:` `` `code` ``
  - Code blocks: ` ```code``` `
  - Links: `<https://example.com|link text>`
  - User mentions: `<@USER_ID>`
  - Channel mentions: `<#CHANNEL_ID>`

- ✅ **Detailed error handling and logging**
- ✅ **Results saved to output directory**
- ✅ **Success/failure tracking for each message**
- ✅ **Sent history** for reference and undo capability

## Tips & Best Practices

- Always test with a small batch before running mass operations
- Check the `output/` folder after running scripts to verify results
- User IDs are required; usernames will not work
- Messages support full Slack markdown syntax
- Keep `.env` file secure and never commit it to version control

## Troubleshooting

### "SLACK_BOT_TOKEN not found"

- Make sure `.env` file exists in the root directory
- Verify the `SLACK_BOT_TOKEN` is set correctly
- Check that you've installed the app to your workspace

### "Permission denied" or API errors

- Ensure all required OAuth scopes are added
- Reinstall the app after adding new scopes
- Check that the bot token is still valid (tokens can expire in some workspaces)

### Messages not sending

- Verify user IDs are correct (not usernames)
- Ensure the bot has access to DM with those users (privacy settings)
- Check the detailed results in `output/mass_dm_results.json` for specific errors

## License

See LICENSE file for details

## Contributing

Feel free to add more scripts and improve existing ones!
