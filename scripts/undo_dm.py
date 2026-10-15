#!/usr/bin/env python3
"""
Undo Mass DM Script

Deletes all messages sent in a previous mass DM campaign (scripts/mass_dm.py)
or mass channel campaign (scripts/mass_channel.py) using the sent ID.

Usage:
    python scripts/undo_dm.py <sent_id>

Example:
    python scripts/undo_dm.py a1b2c3d4
"""

import os
import sys
import json
from pathlib import Path
from typing import Optional, Dict
from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slack_sdk.http_retry.builtin_handlers import RateLimitErrorRetryHandler

# Load environment variables
load_dotenv()

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
OUTPUT_DIR = Path(__file__).parent.parent / "output"
SENT_HISTORY_FILE = OUTPUT_DIR / "sent_history.json"

if not SLACK_BOT_TOKEN:
    raise ValueError("SLACK_BOT_TOKEN not found in .env file")

client = WebClient(token=SLACK_BOT_TOKEN)
# Wait and retry automatically when Slack rate limits us
client.retry_handlers.append(RateLimitErrorRetryHandler(max_retry_count=5))


def get_sent_history(sent_id: str) -> Optional[Dict]:
    """Retrieve a specific sent batch from history."""
    if not SENT_HISTORY_FILE.exists():
        print(f"❌ No sent history found. History file doesn't exist: {SENT_HISTORY_FILE}")
        return None
    
    try:
        with open(SENT_HISTORY_FILE, "r") as f:
            history = json.load(f)
    except Exception as e:
        print(f"❌ Error reading history file: {e}")
        return None
    
    sent_batch = history.get(sent_id)
    if not sent_batch:
        print(f"❌ Sent ID not found: {sent_id}")
        print(f"\nAvailable sent IDs:")
        for available_id in history.keys():
            details = history[available_id]
            print(f"  • {available_id} - {details['total']} messages sent at {details['timestamp']}")
        return None
    
    return sent_batch


def describe_target(result: Dict) -> str:
    """Label for who a message was sent to: a user ID for DMs, #name for channel posts."""
    if result.get("user_id"):
        return result["user_id"]
    if result.get("channel_name"):
        return f"#{result['channel_name']}"
    return str(result.get("channel_id") or result.get("channel"))


def delete_message(channel_id: str, ts: str, target: str) -> bool:
    """Delete a single message from a channel."""
    try:
        client.chat_delete(channel=channel_id, ts=ts)
        print(f"  ✓ Deleted message to {target}")
        return True
    except SlackApiError as e:
        error_code = e.response.get("error", "unknown")
        # Some errors are expected (message already deleted, etc.)
        if error_code in ["message_not_found", "cant_delete_message"]:
            print(f"  ⚠ {target} - Message already deleted or cannot be deleted")
            return True
        else:
            print(f"  ✗ Failed to delete message for {target}: {error_code}")
            return False
    except Exception as e:
        print(f"  ✗ Error deleting message for {target}: {e}")
        return False


def confirm_undo(sent_batch: Dict, sent_id: str) -> bool:
    """Ask for confirmation before undoing."""
    print("\n" + "=" * 70)
    print("UNDO CONFIRMATION")
    print("=" * 70)
    print(f"\nSent ID: {sent_id}")
    print(f"Type: {'channel messages' if sent_batch.get('type') == 'channel' else 'direct messages'}")
    print(f"Timestamp: {sent_batch['timestamp']}")
    print(f"Total messages: {sent_batch['total']}")
    print(f"Successful: {sent_batch['successful']}")
    print(f"Failed: {sent_batch['failed']}")
    
    if sent_batch.get("common_message"):
        print(f"\nMessage:\n{sent_batch['common_message']}\n")
    
    print("=" * 70)
    print("⚠️  CONFIRMATION REQUIRED (2x)")
    print("=" * 70)
    print("⚠️  This will DELETE all messages from this sent batch!\n")
    
    # First confirmation
    response1 = input("[1/2] Do you want to undo? (yes/no): ").strip().lower()
    if response1 != "yes":
        print("❌ Cancelled by user")
        return False
    
    # Second confirmation
    response2 = input("[2/2] Please confirm again (yes/no): ").strip().lower()
    if response2 != "yes":
        print("❌ Cancelled by user")
        return False
    
    print("✅ Confirmed! Deleting messages...\n")
    return True


def main():
    """Main function to undo mass DMs."""
    if len(sys.argv) < 2:
        print("Usage: python scripts/undo_dm.py <sent_id>")
        print("\nExample: python scripts/undo_dm.py a1b2c3d4")
        print("\nTo find your sent IDs, check the sent_history.json file or check your")
        print("mass DM output - it shows the sent ID after sending.")
        return
    
    sent_id = sys.argv[1].strip()
    print(f"\n🔍 Looking up sent ID: {sent_id}")
    
    # Get the sent batch info
    sent_batch = get_sent_history(sent_id)
    if not sent_batch:
        return
    
    # Ask for confirmation
    if not confirm_undo(sent_batch, sent_id):
        return
    
    # Delete messages
    results = sent_batch.get("results", [])
    deleted_count = 0
    failed_count = 0
    skipped_count = 0
    
    print(f"Deleting {len(results)} messages...\n")
    
    for result in results:
        target = describe_target(result)
        
        if not result.get("success"):
            print(f"  ⊘ Skipping {target} (message send failed)")
            skipped_count += 1
            continue
        
        channel_id = result.get("channel_id")
        ts = result.get("ts")
        
        if not channel_id or not ts:
            print(f"  ⊘ Skipping {target} (missing channel or timestamp)")
            skipped_count += 1
            continue
        
        if delete_message(channel_id, ts, target):
            deleted_count += 1
        else:
            failed_count += 1
    
    # Print summary
    print("\n" + "=" * 70)
    print("UNDO SUMMARY")
    print("=" * 70)
    print(f"Deleted: {deleted_count}")
    print(f"Failed: {failed_count}")
    print(f"Skipped: {skipped_count}")
    print("=" * 70)
    
    if failed_count == 0:
        print("✅ All messages have been deleted!")
    else:
        print(f"⚠️  {failed_count} messages could not be deleted")


if __name__ == "__main__":
    main()
