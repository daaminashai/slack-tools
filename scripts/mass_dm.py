#!/usr/bin/env python3
"""
Mass DM Script for Slack

Sends direct messages to multiple users with support for:
- Slack markdown formatting
- User mentions
- File-based input with user IDs and messages
- Output logging of sent messages
- Undo functionality with sent IDs

Modes:
  - Default (same message for all): Message + array of user IDs
  - Per-user (different messages): Array of objects with user_id + message (use --per-user flag)
"""

import os
import json
import csv
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# Load environment variables
load_dotenv()

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
INPUT_DIR = Path(__file__).parent.parent / "input"
OUTPUT_DIR = Path(__file__).parent.parent / "output"
SENT_HISTORY_FILE = OUTPUT_DIR / "sent_history.json"

if not SLACK_BOT_TOKEN:
    raise ValueError("SLACK_BOT_TOKEN not found in .env file")

client = WebClient(token=SLACK_BOT_TOKEN)


def load_recipients(file_path: Path, per_user_mode: bool = False) -> Tuple[Optional[str], List[Dict[str, str]]]:
    """
    Load recipients from a JSON or CSV file.
    
    Default mode (per_user_mode=False):
    {
        "message": "Hello everyone!",
        "slack_ids": ["U12345", "U67890"]
    }
    
    Per-user mode (per_user_mode=True):
    [
        {"user_id": "U12345", "message": "Hello Alice"},
        {"user_id": "U67890", "message": "Hello Bob"}
    ]
    """
    if file_path.suffix.lower() == ".json":
        with open(file_path, "r") as f:
            data = json.load(f)
    else:
        raise ValueError(f"Only JSON files supported. Got: {file_path.suffix}")
    
    if per_user_mode:
        # Per-user mode: array of {user_id, message}
        if not isinstance(data, list):
            raise ValueError("Per-user mode expects a JSON array")
        return None, data
    else:
        # Default mode: {message, slack_ids}
        if not isinstance(data, dict):
            raise ValueError("Default mode expects a JSON object with 'message' and 'slack_ids'")
        
        message = data.get("message")
        slack_ids = data.get("slack_ids", [])
        
        if not message:
            raise ValueError("Missing 'message' field in JSON")
        if not slack_ids:
            raise ValueError("Missing 'slack_ids' array in JSON")
        
        # Convert to per-recipient format for consistency
        recipients = [{"user_id": uid, "message": message} for uid in slack_ids]
        return message, recipients


def get_user_display_name(user_id: str) -> str:
    """Get the display name of a user from Slack."""
    try:
        response = client.users_info(user=user_id)
        user = response.get("user", {})
        # Try real_name first, then display_name, then name
        return user.get("real_name") or user.get("profile", {}).get("display_name") or user.get("name") or user_id
    except Exception:
        return user_id


def confirm_action(message: str, user_names: List[str], common_message: Optional[str] = None) -> bool:
    """
    Ask for confirmation twice before proceeding.
    Shows a summary of what will be sent.
    """
    print("\n" + "=" * 70)
    print("SEND CONFIRMATION SUMMARY")
    print("=" * 70)
    
    if common_message:
        print(f"\n📨 Message:\n{common_message}\n")
    else:
        print(f"\n📨 Sending {len(user_names)} personalized messages\n")
    
    print(f"👥 Recipients ({len(user_names)} users):")
    for name in user_names:
        print(f"  • {name}")
    
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


def send_dm(user_id: str, message: str) -> Dict[str, any]:
    """
    Send a direct message to a user.
    
    Returns:
        dict with keys:
            - success: bool
            - user_id: str
            - ts: str (timestamp, if successful)
            - channel_id: str (DM channel ID, if successful)
            - error: str (if failed)
    """
    result = {
        "user_id": user_id,
        "message": message,
        "success": False,
        "ts": None,
        "channel_id": None,
        "error": None
    }
    
    try:
        response = client.conversations_open(users=[user_id])
        channel_id = response["channel"]["id"]
        
        message_response = client.chat_postMessage(
            channel=channel_id,
            text=message,
            mrkdwn=True  # Enable Slack markdown rendering
        )
        
        result["success"] = True
        result["ts"] = message_response["ts"]
        result["channel_id"] = channel_id
        print(f"✓ Sent message to {user_id}")
        
    except SlackApiError as e:
        result["error"] = f"Slack API Error: {e.response['error']}"
        print(f"✗ Failed to send message to {user_id}: {result['error']}")
    except Exception as e:
        result["error"] = f"Error: {str(e)}"
        print(f"✗ Failed to send message to {user_id}: {result['error']}")
    
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
    
    with open(summary_file, "w") as f:
        f.write(f"Mass DM Results - Sent ID: {sent_id}\n")
        f.write(f"{'=' * 50}\n")
        f.write(f"Timestamp: {datetime.now().isoformat()}\n")
        f.write(f"Total messages: {len(results)}\n")
        f.write(f"Successful: {successful}\n")
        f.write(f"Failed: {failed}\n")
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
        "timestamp": datetime.now().isoformat(),
        "common_message": common_message,
        "results": results,
        "total": len(results),
        "successful": sum(1 for r in results if r["success"]),
        "failed": sum(1 for r in results if not r["success"])
    }
    
    with open(SENT_HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


def get_sent_history(sent_id: str) -> Optional[Dict]:
    """Retrieve a specific sent batch from history."""
    if not SENT_HISTORY_FILE.exists():
        return None
    
    with open(SENT_HISTORY_FILE, "r") as f:
        history = json.load(f)
    
    return history.get(sent_id)


def main():
    """Main function to send mass DMs."""
    # Parse command line arguments
    per_user_mode = "--per-user" in sys.argv
    
    # Look for input file
    input_files = [f for f in INPUT_DIR.glob("*") if f.suffix.lower() == ".json"]
    
    if not input_files:
        print("No JSON input files found in the input/ directory")
        print("\n📄 DEFAULT MODE (same message for all):")
        print("Create input/recipients.json:")
        print(json.dumps({
            "message": "Hello everyone! *This is bold* and check out <https://example.com|our website>",
            "slack_ids": ["U12345ABC", "U67890XYZ"]
        }, indent=2))
        print("\n📄 PER-USER MODE (different messages):")
        print("Run with: python scripts/mass_dm.py --per-user")
        print("Create input/recipients.json:")
        print(json.dumps([
            {"user_id": "U12345ABC", "message": "Hey Alice! *Important* update"},
            {"user_id": "U67890XYZ", "message": "Hey Bob! Check this out"}
        ], indent=2))
        return
    
    input_file = input_files[0]  # Use the first JSON file found
    print(f"\n📂 Loading recipients from: {input_file.name}")
    
    try:
        common_message, recipients = load_recipients(input_file, per_user_mode=per_user_mode)
        print(f"✓ Loaded {len(recipients)} recipients")
        
        # Fetch user display names for confirmation
        print("\n👥 Fetching user display names...")
        user_names = []
        for recipient in recipients:
            user_id = recipient.get("user_id")
            display_name = get_user_display_name(user_id)
            user_names.append(display_name)
        
        # Show confirmation summary
        if not confirm_action("Mass DM", user_names, common_message):
            return
        
        # Generate unique sent ID
        sent_id = str(uuid.uuid4())[:8]
        
        # Send messages
        results = []
        for recipient in recipients:
            user_id = recipient.get("user_id")
            message = recipient.get("message")
            
            if not user_id or not message:
                print(f"✗ Skipping invalid recipient: {recipient}")
                results.append({
                    "user_id": user_id,
                    "message": message,
                    "success": False,
                    "error": "Missing user_id or message"
                })
                continue
            
            result = send_dm(user_id, message)
            results.append(result)
        
        # Save results
        save_results(results, sent_id, common_message)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
