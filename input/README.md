# Input Files

This directory contains input files for the Slack tools scripts.

## Format

### Default Mode (Same message for all users)

File: `recipients.json`

```json
{
  "message": "Your message here with *markdown* support",
  "slack_ids": ["U12345ABC", "U67890XYZ", "U11111111"]
}
```

Run with: `python scripts/mass_dm.py`

### Per-User Mode (Different messages)

File: `recipients.json` (or any name)

```json
[
  { "user_id": "U12345ABC", "message": "Personalized message for Alice" },
  { "user_id": "U67890XYZ", "message": "Personalized message for Bob" }
]
```

Run with: `python scripts/mass_dm.py --per-user`

### Channel Messages (`scripts/mass_channel.py`)

File: `channels.json` (or pass any path as the first argument)

```json
{
  "message": "Your message here with *markdown* support",
  "channels": ["C12345ABC", "#general", "random"]
}
```

Run with: `python scripts/mass_channel.py`

Per-channel messages:

```json
[
  { "channel": "C12345ABC", "message": "Message for this channel" },
  { "channel": "#general", "message": "Message for #general" }
]
```

Run with: `python scripts/mass_channel.py --per-channel`

## Examples

See:

- `example_recipients.json` - Default mode example
- `example_recipients_per_user.json` - Per-user mode example

## Tips

- User IDs must start with `U` (get them from user profile → "Copy user ID")
- Messages support Slack markdown: _bold_, _italic_, `code`, etc.
- File must be valid JSON
- `mass_dm.py` uses the first JSON file it finds here, so move `channels.json` out of the way before running it
