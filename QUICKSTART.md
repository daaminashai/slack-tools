# Quick Start Guide

Get sending DMs in 5 minutes!

## 1. Setup (First time only)

```bash
# Install dependencies
pip install -r requirements.txt

# Create .env file with your Slack token
# Edit .env and add your SLACK_BOT_TOKEN
```

[Get your token here](https://api.slack.com/apps) → OAuth & Permissions → Copy Bot User OAuth Token

## 2. Create Input File

Option A: **Same message for everyone** (Default mode)

Create `input/recipients.json`:

```json
{
  "message": "Hello team! Check out this *important update*",
  "slack_ids": ["U12345ABC", "U67890XYZ"]
}
```

Option B: **Different message per person** (Per-user mode)

Create `input/recipients.json`:

```json
[
  { "user_id": "U12345ABC", "message": "Hey Alice!" },
  { "user_id": "U67890XYZ", "message": "Hey Bob!" }
]
```

## 3. Find User IDs

In Slack:

1. Click user's profile
2. Click **...** menu
3. Select **Copy user ID**

## 4. Run the Script

Option A:

```bash
python scripts/mass_dm.py
```

Option B:

```bash
python scripts/mass_dm.py --per-user
```

## 5. Confirm

- Review the message and recipients
- Confirm **twice**
- ✅ Done!

## 6. Check Results

Look in the `output/` folder for:

- `sent_XXXXX.json` - Detailed results
- `sent_XXXXX_summary.txt` - Quick summary
- Your **Sent ID** for undo

## Undo (if needed)

```bash
python scripts/undo_dm.py <your-sent-id>
```

The Sent ID is shown after sending, or check the summary file.

---

That's it! Happy DMing! 🚀

For more details, see [README.md](README.md)
