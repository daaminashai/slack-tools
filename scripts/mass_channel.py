#!/usr/bin/env python3
"""
Mass Channel Message Script for Slack

Posts messages to multiple channels with support for:
- Channel IDs (C12345ABC) or channel names (#general or general)
- Slack markdown formatting and mentions
- Auto-joining public channels the bot isn't in (--join)
- Output logging of sent messages
- Undo functionality with sent IDs (via scripts/undo_dm.py)

Modes:
  - Default (same message for all): Message + array of channels
  - Per-channel (different messages): Array of objects with channel + message (use --per-channel flag)

Usage:
    python scripts/mass_channel.py [input_file] [--per-channel] [--join]
"""

import os
import re
import json
import uuid
import argparse
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple
from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slack_sdk.http_retry.builtin_handlers import RateLimitErrorRetryHandler

# Load environment variables
load_dotenv()

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
INPUT_DIR = Path(__file__).parent.parent / "input"
OUTPUT_DIR = Path(__file__).parent.parent / "output"
SENT_HISTORY_FILE = OUTPUT_DIR / "sent_history.json"
DEFAULT_INPUT_FILE = INPUT_DIR / "channels.json"

# Channel IDs are uppercase (C... or legacy G...), channel names are always lowercase
CHANNEL_ID_PATTERN = re.compile(r"^[CG][A-Z0-9]{6,}$")

if not SLACK_BOT_TOKEN:
    raise ValueError("SLACK_BOT_TOKEN not found in .env file")

client = WebClient(token=SLACK_BOT_TOKEN)
# Wait and retry automatically when Slack rate limits us
client.retry_handlers.append(RateLimitErrorRetryHandler(max_retry_count=5))


def load_targets(file_path: Path, per_channel_mode: bool = False) -> Tuple[Optional[str], List[Dict[str, str]]]:
    """
    Load target channels from a JSON file.

    Default mode (per_channel_mode=False):
    {
        "message": "Hello everyone!",
        "channels": ["C12345ABC", "#general", "random"]
    }

    Per-channel mode (per_channel_mode=True):
    [
        {"channel": "C12345ABC", "message": "Hello first channel"},
        {"channel": "#general", "message": "Hello general"}
    ]
    """
    if file_path.suffix.lower() != ".json":
        raise ValueError(f"Only JSON files supported. Got: {file_path.suffix}")

    with open(file_path, "r") as f:
        data = json.load(f)

    if per_channel_mode:
        # Per-channel mode: array of {channel, message}
        if not isinstance(data, list):
            raise ValueError("Per-channel mode expects a JSON array")
        return None, data

    # Default mode: {message, channels}
    if not isinstance(data, dict):
        raise ValueError("Default mode expects a JSON object with 'message' and 'channels'")

    message = data.get("message")
    channels = data.get("channels", [])

    if not message:
        raise ValueError("Missing 'message' field in JSON")
    if not channels:
        raise ValueError("Missing 'channels' array in JSON")

    # Convert to per-channel format for consistency
    targets = [{"channel": channel, "message": message} for channel in channels]
    return message, targets


def parse_channel_ref(ref: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Split a channel reference into (channel_id, channel_name); exactly one is set.

    Accepts "C12345ABC", "#general" or "general".
    """
    ref = ref.strip().lstrip("#")
    if CHANNEL_ID_PATTERN.match(ref):
        return ref, None
    return None, ref.lower()


def fetch_channels_by_name(names: Set[str]) -> Dict[str, Dict]:
    """
    Look up channels by name by paging through the workspace's channel list.

    Stops as soon as every name has been found. Private channels are only
    visible if the bot is a member of them.
    """
    found = {}
    remaining = set(names)
    types = "public_channel,private_channel"
    cursor = None
    scanned = 0

    while remaining:
        try:
            response = client.conversations_list(
                types=types,
                exclude_archived=True,
                limit=1000,
                cursor=cursor
            )
        except SlackApiError as e:
            # Without groups:read we can still look up public channels
            if e.response["error"] == "missing_scope" and types != "public_channel":
                print("⚠ Missing groups:read scope - only public channels can be looked up by name")
                types = "public_channel"
                cursor = None
                continue
            raise

        for channel in response["channels"]:
            if channel["name"] in remaining:
                found[channel["name"]] = channel
                remaining.discard(channel["name"])

        scanned += len(response["channels"])
        print(f"  Scanned {scanned} channels...")

        cursor = response.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break

    return found


def fetch_channel_by_id(channel_id: str) -> Tuple[Optional[Dict], Optional[str]]:
    """Get a channel's info by ID. Returns (channel, error)."""
    try:
        response = client.conversations_info(channel=channel_id, include_num_members=True)
        return response["channel"], None
    except SlackApiError as e:
        return None, f"Slack API Error: {e.response['error']}"
    except Exception as e:
        return None, f"Error: {str(e)}"


def resolve_targets(targets: List[Dict]) -> List[Dict]:
    """
    Resolve every target's channel (ID or name) to an actual Slack channel.

    Each returned target has: channel, message, channel_id, channel_name,
    is_member, is_private, num_members, and error (set if it can't be sent).
    """
    resolved = []
    names = set()

    for target in targets:
        ref = target.get("channel")
        channel_id, channel_name = parse_channel_ref(str(ref)) if ref else (None, None)
        resolved.append({
            "channel": ref,
            "message": target.get("message"),
            "channel_id": channel_id,
            "channel_name": channel_name,
            "is_member": False,
            "is_private": False,
            "num_members": None,
            "error": None
        })
        if channel_name:
            names.add(channel_name)

    channels_by_name = {}
    if names:
        print(f"\n🔎 Looking up {len(names)} channel name(s)...")
        channels_by_name = fetch_channels_by_name(names)

    channels_by_id = {}
    for target in resolved:
        if not target["channel"] or not target["message"]:
            target["error"] = "Missing channel or message"
            continue

        if target["channel_id"]:
            if target["channel_id"] not in channels_by_id:
                channels_by_id[target["channel_id"]] = fetch_channel_by_id(target["channel_id"])
            channel, error = channels_by_id[target["channel_id"]]
            if error:
                target["error"] = error
                continue
            if channel.get("is_archived"):
                target["error"] = "Channel is archived"
                continue
        else:
            channel = channels_by_name.get(target["channel_name"])
            if not channel:
                target["error"] = "Channel not found (archived, misspelled, or private without the bot in it)"
                continue

        target["channel_id"] = channel["id"]
        target["channel_name"] = channel.get("name")
        target["is_member"] = channel.get("is_member", False)
        target["is_private"] = channel.get("is_private", False)
        target["num_members"] = channel.get("num_members")

    return resolved


def remove_duplicates(targets: List[Dict]) -> List[Dict]:
    """Drop targets that point at a channel already in the list (e.g. listed by both name and ID)."""
    seen = set()
    unique = []
    for target in targets:
        if not target["error"]:
            if target["channel_id"] in seen:
                print(f"⚠ Skipping duplicate: {target['channel']} ({format_channel(target)})")
                continue
            seen.add(target["channel_id"])
        unique.append(target)
    return unique


def format_channel(target: Dict) -> str:
    """Format a resolved channel as '#name (ID)'."""
    if target.get("channel_name"):
        return f"#{target['channel_name']} ({target['channel_id']})"
    return str(target.get("channel_id") or target.get("channel"))


def preview(message: str, length: int = 100) -> str:
    """Single-line, truncated preview of a message."""
    flat = " ".join(message.split())
    return flat if len(flat) <= length else flat[:length - 1] + "…"


def confirm_action(targets: List[Dict], common_message: Optional[str] = None, auto_join: bool = False) -> bool:
    """
    Ask for confirmation twice before proceeding.
    Shows a summary of what will be sent and where.
    """
    ready = [t for t in targets if not t["error"]]
    skipped = [t for t in targets if t["error"]]
    not_member = [t for t in ready if not t["is_member"]]

    print("\n" + "=" * 70)
    print("SEND CONFIRMATION SUMMARY")
    print("=" * 70)

    if common_message:
        print(f"\n📨 Message:\n{common_message}\n")
    else:
        print(f"\n📨 Sending {len(ready)} per-channel messages\n")

    print(f"📣 Channels ({len(ready)}):")
    for target in ready:
        details = []
        if target["num_members"] is not None:
            details.append(f"{target['num_members']:,} members")
        if target["is_private"]:
            details.append("private")
        if not target["is_member"]:
            details.append("bot not in channel")
        suffix = f" [{', '.join(details)}]" if details else ""
        print(f"  • {format_channel(target)}{suffix}")
        if not common_message:
            print(f"      ↳ {preview(target['message'])}")

    reach = sum(t["num_members"] or 0 for t in ready)
    if reach:
        print(f"\n👥 Reaches up to {reach:,} members (overlapping members counted per channel)")

    if skipped:
        print(f"\n⚠️  Will be SKIPPED ({len(skipped)}):")
        for target in skipped:
            print(f"  • {target['channel']}: {target['error']}")

    if not_member:
        if auto_join:
            print(f"\nℹ️  The bot will join {len(not_member)} public channel(s) it isn't in if needed")
        else:
            print(f"\nℹ️  The bot isn't in {len(not_member)} channel(s). Posting there only works if the app has")
            print("   the chat:write.public scope. Re-run with --join to have the bot join them instead.")

    print("\n" + "=" * 70)
    print("⚠️  CONFIRMATION REQUIRED (2x)")
    print("=" * 70)

    # First confirmation
    response1 = input("\n[1/2] Do you want to proceed? (yes/no): ").strip().lower()
    if response1 != "yes":
        print("❌ Cancelled by user")
        return False

    # Second confirmation
    response2 = input("[2/2] Please confirm again (yes/no): ").strip().lower()
    if response2 != "yes":
        print("❌ Cancelled by user")
        return False

    print("✅ Confirmed! Sending messages...\n")
    return True


def post_message(channel_id: str, message: str):
    return client.chat_postMessage(
        channel=channel_id,
        text=message,
        mrkdwn=True  # Enable Slack markdown rendering
    )


def send_channel_message(target: Dict, auto_join: bool = False) -> Dict[str, any]:
    """
    Post a message to a resolved channel.

    Returns:
        dict with keys:
            - success: bool
            - channel: str (as given in the input file)
            - channel_id: str
            - channel_name: str
            - ts: str (timestamp, if successful)
            - joined: bool (whether the bot joined the channel to post)
            - error: str (if failed)
    """
    result = {
        "channel": target["channel"],
        "channel_id": target["channel_id"],
        "channel_name": target["channel_name"],
        "message": target["message"],
        "success": False,
        "ts": None,
        "joined": False,
        "error": None
    }
    label = format_channel(target)

    try:
        try:
            response = post_message(target["channel_id"], target["message"])
        except SlackApiError as e:
            if e.response["error"] != "not_in_channel" or not auto_join or target["is_private"]:
                raise
            client.conversations_join(channel=target["channel_id"])
            result["joined"] = True
            print(f"  ↪ Joined {label}")
            response = post_message(target["channel_id"], target["message"])

        result["success"] = True
        result["ts"] = response["ts"]
        print(f"✓ Sent message to {label}")

    except SlackApiError as e:
        result["error"] = f"Slack API Error: {e.response['error']}"
        print(f"✗ Failed to send message to {label}: {result['error']}")
    except Exception as e:
        result["error"] = f"Error: {str(e)}"
        print(f"✗ Failed to send message to {label}: {result['error']}")

    return result


def save_results(results: List[Dict], sent_id: str, common_message: Optional[str] = None) -> Path:
    """Save results to a JSON file in the output directory and update sent history."""
    output_file = OUTPUT_DIR / f"sent_{sent_id}.json"

    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)

    # Also save a summary
    summary_file = OUTPUT_DIR / f"sent_{sent_id}_summary.txt"
    successful = sum(1 for r in results if r["success"])
    failed = len(results) - successful
    joined = [format_channel(r) for r in results if r.get("joined")]

    with open(summary_file, "w") as f:
        f.write(f"Mass Channel Message Results - Sent ID: {sent_id}\n")
        f.write(f"{'=' * 50}\n")
        f.write(f"Timestamp: {datetime.now().isoformat()}\n")
        f.write(f"Total messages: {len(results)}\n")
        f.write(f"Successful: {successful}\n")
        f.write(f"Failed: {failed}\n")
        if joined:
            f.write(f"\nBot joined these channels (undo will NOT leave them):\n")
            for channel in joined:
                f.write(f"  {channel}\n")
        if common_message:
            f.write(f"\nMessage:\n{common_message}\n")
        f.write(f"\nUse the following ID to undo these messages:\n")
        f.write(f"  python scripts/undo_dm.py {sent_id}\n")
        f.write(f"\nDetailed results: {output_file}\n")

    # Update sent history
    update_sent_history(sent_id, results, common_message)

    print(f"\n✓ Results saved to {output_file}")
    print(f"✓ Summary saved to {summary_file}")
    print(f"\n🆔 SENT ID: {sent_id}")
    print(f"To undo, run: python scripts/undo_dm.py {sent_id}")

    return output_file


def update_sent_history(sent_id: str, results: List[Dict], common_message: Optional[str] = None) -> None:
    """Add sent batch to history for undo capability."""
    history = {}

    if SENT_HISTORY_FILE.exists():
        with open(SENT_HISTORY_FILE, "r") as f:
            history = json.load(f)

    history[sent_id] = {
        "type": "channel",
        "timestamp": datetime.now().isoformat(),
        "common_message": common_message,
        "results": results,
        "total": len(results),
        "successful": sum(1 for r in results if r["success"]),
        "failed": sum(1 for r in results if not r["success"])
    }

    with open(SENT_HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


def main():
    """Main function to send messages to multiple channels."""
    parser = argparse.ArgumentParser(description="Send messages to multiple Slack channels by ID or name.")
    parser.add_argument(
        "input_file",
        nargs="?",
        type=Path,
        default=DEFAULT_INPUT_FILE,
        help="JSON input file (default: input/channels.json)"
    )
    parser.add_argument(
        "--per-channel",
        action="store_true",
        help="Input is an array of {channel, message} objects (different message per channel)"
    )
    parser.add_argument(
        "--join",
        action="store_true",
        help="Join public channels the bot isn't in before posting (requires channels:join scope)"
    )
    args = parser.parse_args()

    if not args.input_file.exists():
        print(f"Input file not found: {args.input_file}")
        print("\n📄 DEFAULT MODE (same message for all):")
        print("Create input/channels.json:")
        print(json.dumps({
            "message": "Hello everyone! *This is bold* and check out <https://example.com|our website>",
            "channels": ["C12345ABC", "#general", "random"]
        }, indent=2))
        print("\n📄 PER-CHANNEL MODE (different messages):")
        print("Run with: python scripts/mass_channel.py --per-channel")
        print("Create input/channels.json:")
        print(json.dumps([
            {"channel": "C12345ABC", "message": "Hey team! *Important* update"},
            {"channel": "#general", "message": "Hello general! Check this out"}
        ], indent=2))
        return

    print(f"\n📂 Loading channels from: {args.input_file.name}")

    try:
        common_message, targets = load_targets(args.input_file, per_channel_mode=args.per_channel)
        print(f"✓ Loaded {len(targets)} channels")

        targets = resolve_targets(targets)
        if not args.per_channel:
            targets = remove_duplicates(targets)

        if not any(not t["error"] for t in targets):
            print("\n❌ None of the channels could be resolved:")
            for target in targets:
                print(f"  • {target['channel']}: {target['error']}")
            return

        # Show confirmation summary
        if not confirm_action(targets, common_message, auto_join=args.join):
            return

        # Generate unique sent ID
        sent_id = str(uuid.uuid4())[:8]

        # Send messages
        results = []
        for target in targets:
            if target["error"]:
                print(f"✗ Skipping {target['channel']}: {target['error']}")
                results.append({
                    "channel": target["channel"],
                    "channel_id": target["channel_id"],
                    "channel_name": target["channel_name"],
                    "message": target["message"],
                    "success": False,
                    "ts": None,
                    "joined": False,
                    "error": target["error"]
                })
                continue

            result = send_channel_message(target, auto_join=args.join)
            results.append(result)

        # Save results
        save_results(results, sent_id, common_message)

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
