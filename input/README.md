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

## Examples

See:

- `example_recipients.json` - Default mode example
- `example_recipients_per_user.json` - Per-user mode example

## Tips

- User IDs must start with `U` (get them from user profile → "Copy user ID")
- Messages support Slack markdown: _bold_, _italic_, `code`, etc.
- File must be valid JSON
- Only one input file should be in this directory when you run the script
