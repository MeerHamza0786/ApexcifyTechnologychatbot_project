#!/usr/bin/env python3
"""Enhanced CLI chatbot with rich features.

Usage:
  python cli_chat.py [--user USER_ID] [--debug]

Commands:
  /exit, /quit     - Exit the chat
  /history         - Show chat history
  /clear           - Clear chat history
  /search <query>  - Search messages
  /time            - Show current time
  /date            - Show current date
  /joke            - Tell a random joke
  /help            - Show all commands
  /export          - Export chat to JSON
  /import <file>   - Import chat from JSON
  /stats           - Show chat statistics
  /users           - List all users
  /switch <user>   - Switch to different user
"""

import sys
import json
import uuid
import random
import argparse
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple

# ===== CONFIGURATION =====
BASE_DIR = Path(__file__).parent
CHATS_FILE = BASE_DIR / "chats.json"
EXPORT_DIR = BASE_DIR / "exports"

# Colors for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

# ===== UTILITY FUNCTIONS =====
def now_ts() -> str:
    """Return current timestamp in readable format."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def colored(text: str, color: str) -> str:
    """Return colored text for terminal."""
    return f"{color}{text}{Colors.END}"

def print_header(text: str):
    """Print a formatted header."""
    print(f"\n{colored('═' * 60, Colors.CYAN)}")
    print(colored(f"  {text}", Colors.BOLD))
    print(f"{colored('═' * 60, Colors.CYAN)}\n")

def print_info(text: str):
    """Print info message."""
    print(colored(f"ℹ  {text}", Colors.CYAN))

def print_success(text: str):
    """Print success message."""
    print(colored(f"✓  {text}", Colors.GREEN))

def print_error(text: str):
    """Print error message."""
    print(colored(f"✗  {text}", Colors.RED))

def print_warning(text: str):
    """Print warning message."""
    print(colored(f"⚠  {text}", Colors.YELLOW))

# ===== DATA MANAGEMENT =====
def _read_all_chats() -> Dict:
    """Read all chat data from JSON file."""
    if not CHATS_FILE.exists():
        return {}
    try:
        with open(CHATS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        print_error("Chat file is corrupted. Creating backup...")
        backup = CHATS_FILE.with_suffix('.json.bak')
        CHATS_FILE.rename(backup)
        return {}
    except Exception as e:
        print_error(f"Error reading chats: {e}")
        return {}

def _write_all_chats(data: Dict):
    """Write all chat data to JSON file."""
    try:
        CHATS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CHATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print_error(f"Error writing chats: {e}")

def load_user_chat(uid: str) -> List[Dict]:
    """Load chat history for specific user."""
    return _read_all_chats().get(uid, [])

def save_user_chat(uid: str, messages: List[Dict]):
    """Save chat history for specific user."""
    allchats = _read_all_chats()
    allchats[uid] = messages
    _write_all_chats(allchats)

def get_all_users() -> List[str]:
    """Get list of all user IDs."""
    return list(_read_all_chats().keys())

# ===== RULE-BASED REPLY SYSTEM =====
def rule_based_reply(text: str) -> str:
    """Generate rule-based response to user input."""
    t = (text or '').strip().lower()
    
    if not t:
        return "Please say something."
    
    # Greetings
    greetings = ["hello", "hi", "hey", "greetings", "howdy", "hola"]
    if any(word in t for word in greetings):
        responses = [
            "Hello! How can I help you today?",
            "Hi there! What can I do for you?",
            "Hey! Great to see you!",
            "Greetings! How may I assist you?"
        ]
        return random.choice(responses)
    
    # How are you
    if any(phrase in t for phrase in ["how are you", "how r you", "how're you", "how are u"]):
        responses = [
            "I'm doing great, thank you for asking!",
            "I'm functioning perfectly! How about you?",
            "Excellent! Ready to chat!",
            "I'm fantastic! Thanks for asking!"
        ]
        return random.choice(responses)
    
    # Goodbye
    if any(word in t for word in ["bye", "goodbye", "see you", "farewell", "later", "cya"]):
        responses = [
            "Goodbye! Have a great day!",
            "See you later! Take care!",
            "Farewell! Come back soon!",
            "Bye! It was nice chatting with you!"
        ]
        return random.choice(responses)
    
    # Name questions
    if "your name" in t or "who are you" in t:
        return "I'm ChatPy, your friendly CLI chatbot assistant!"
    
    # What can you do
    if any(phrase in t for phrase in ["what can you do", "your capabilities", "can you help"]):
        return "I can chat with you, answer questions, tell jokes, and more! Type /help to see all commands."
    
    # Thank you
    if any(word in t for word in ["thank", "thanks", "thx", "appreciate"]):
        responses = [
            "You're welcome!",
            "Happy to help!",
            "Anytime!",
            "My pleasure!"
        ]
        return random.choice(responses)
    
    # Help/Support
    if any(word in t for word in ["help", "assist", "support"]):
        return "Sure! I'm here to help. What do you need assistance with? Type /help for available commands."
    
    # Age questions
    if "how old" in t or "your age" in t:
        return "I was created recently, so I'm quite young in AI years!"
    
    # Location questions
    if any(word in t for word in ["where are you", "your location", "where do you live"]):
        return "I exist in the digital realm, living inside your terminal!"
    
    # Weather (can't actually check)
    if "weather" in t:
        return "I can't check the weather, but I hope it's nice where you are!"
    
    # Love/Like
    if any(phrase in t for phrase in ["i love you", "i like you", "you're awesome", "you're great"]):
        return "Aww, that's so kind! I enjoy chatting with you too! 😊"
    
    # Questions
    if "?" in t:
        return "That's an interesting question! I'm a simple chatbot, so my knowledge is limited. Try rephrasing or type /help for commands."
    
    # Default fallback
    fallbacks = [
        "I'm not sure I understand. Could you rephrase that?",
        "Hmm, I didn't quite catch that. Can you try again?",
        "I'm still learning! Can you say that differently?",
        "Sorry, I don't have a good response for that yet.",
        "That's beyond my current capabilities. Type /help for what I can do!"
    ]
    return random.choice(fallbacks)

# ===== COMMAND HANDLERS =====
def handle_history(messages: List[Dict], limit: int = 50):
    """Display chat history."""
    if not messages:
        print_info("No messages in history yet.")
        return
    
    print_header("Chat History")
    display_messages = messages[-limit:] if len(messages) > limit else messages
    
    if len(messages) > limit:
        print_info(f"Showing last {limit} of {len(messages)} messages")
    
    for msg in display_messages:
        who = msg.get('who', 'unknown')
        text = msg.get('text', '')
        ts = msg.get('ts', '')
        
        if who in ('me', 'user', 'you'):
            prefix = colored("You: ", Colors.GREEN + Colors.BOLD)
        else:
            prefix = colored("Bot: ", Colors.BLUE + Colors.BOLD)
        
        print(f"{colored('[' + ts + ']', Colors.YELLOW)} {prefix}{text}")

def handle_search(messages: List[Dict], query: str):
    """Search through chat messages."""
    if not query:
        print_error("Please provide a search query. Usage: /search <query>")
        return
    
    query_lower = query.lower()
    results = [msg for msg in messages if query_lower in msg.get('text', '').lower()]
    
    if not results:
        print_info(f"No messages found matching '{query}'")
        return
    
    print_header(f"Search Results for '{query}'")
    print_info(f"Found {len(results)} message(s)")
    
    for msg in results[-20:]:  # Show last 20 results
        who = "You" if msg.get('who') in ('me', 'user', 'you') else "Bot"
        text = msg.get('text', '')
        ts = msg.get('ts', '')
        print(f"{colored('[' + ts + ']', Colors.YELLOW)} {colored(who + ':', Colors.BOLD)} {text}")

def handle_stats(messages: List[Dict], uid: str):
    """Show chat statistics."""
    if not messages:
        print_info("No statistics available yet.")
        return
    
    user_msgs = [m for m in messages if m.get('who') in ('me', 'user', 'you')]
    bot_msgs = [m for m in messages if m.get('who') == 'bot']
    
    total_words_user = sum(len(m.get('text', '').split()) for m in user_msgs)
    total_words_bot = sum(len(m.get('text', '').split()) for m in bot_msgs)
    
    first_msg = messages[0].get('ts', 'Unknown') if messages else 'N/A'
    last_msg = messages[-1].get('ts', 'Unknown') if messages else 'N/A'
    
    print_header("Chat Statistics")
    print(f"{colored('User ID:', Colors.BOLD)} {uid}")
    print(f"{colored('Total messages:', Colors.BOLD)} {len(messages)}")
    print(f"{colored('Your messages:', Colors.BOLD)} {len(user_msgs)}")
    print(f"{colored('Bot messages:', Colors.BOLD)} {len(bot_msgs)}")
    print(f"{colored('Your words:', Colors.BOLD)} {total_words_user}")
    print(f"{colored('Bot words:', Colors.BOLD)} {total_words_bot}")
    print(f"{colored('First message:', Colors.BOLD)} {first_msg}")
    print(f"{colored('Last message:', Colors.BOLD)} {last_msg}")

def handle_export(messages: List[Dict], uid: str):
    """Export chat history to JSON file."""
    if not messages:
        print_info("No messages to export.")
        return
    
    EXPORT_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"chat_export_{uid}_{timestamp}.json"
    filepath = EXPORT_DIR / filename
    
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(messages, f, ensure_ascii=False, indent=2)
        print_success(f"Chat exported to: {filepath}")
    except Exception as e:
        print_error(f"Export failed: {e}")

def handle_import(messages: List[Dict], uid: str, filepath: str) -> bool:
    """Import chat history from JSON file."""
    if not filepath:
        print_error("Please provide a file path. Usage: /import <filepath>")
        return False
    
    path = Path(filepath)
    if not path.exists():
        print_error(f"File not found: {filepath}")
        return False
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if not isinstance(data, list):
            print_error("Invalid file format. Expected a list of messages.")
            return False
        
        # Validate message structure
        valid_messages = []
        for msg in data:
            if isinstance(msg, dict) and 'text' in msg:
                valid_messages.append(msg)
        
        if not valid_messages:
            print_error("No valid messages found in file.")
            return False
        
        messages.extend(valid_messages)
        save_user_chat(uid, messages)
        print_success(f"Imported {len(valid_messages)} message(s)")
        return True
        
    except json.JSONDecodeError:
        print_error("Invalid JSON file.")
        return False
    except Exception as e:
        print_error(f"Import failed: {e}")
        return False

def handle_users():
    """List all users."""
    users = get_all_users()
    
    if not users:
        print_info("No users found.")
        return
    
    print_header("All Users")
    all_chats = _read_all_chats()
    
    for i, user_id in enumerate(users, 1):
        msg_count = len(all_chats.get(user_id, []))
        print(f"{i}. {colored(user_id, Colors.CYAN)} ({msg_count} messages)")

def handle_joke():
    """Tell a random joke."""
    jokes = [
        "Why do programmers prefer dark mode? Because light attracts bugs! 🐛",
        "Why did the programmer quit his job? Because he didn't get arrays. 📊",
        "How many programmers does it take to change a light bulb? None — it's a hardware problem. 💡",
        "Why do Java developers wear glasses? Because they can't C#! 👓",
        "What's a programmer's favorite hangout place? Foo Bar! 🍺",
        "Why did the developer go broke? Because he used up all his cache! 💰",
        "What do you call a programmer from Finland? Nerdic! 🇫🇮",
        "Why do Python programmers have low self-esteem? They're constantly comparing themselves to others! 🐍",
        "What's the object-oriented way to become wealthy? Inheritance! 💎",
        "Why did the variable break up with the constant? She needed some space! 🚀"
    ]
    return random.choice(jokes)

def handle_command(text: str, uid: str, messages: List[Dict]) -> Tuple[Optional[str], bool]:
    """
    Handle command input.
    Returns: (response_text, should_exit)
    """
    parts = text.strip().split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""
    
    if cmd in ('/exit', '/quit', '/q'):
        return None, True
    
    if cmd == '/history':
        handle_history(messages)
        return None, False
    
    if cmd == '/search':
        handle_search(messages, arg)
        return None, False
    
    if cmd in ('/clear', '/clearhistory', '/clear_history'):
        messages.clear()
        save_user_chat(uid, messages)
        print_success("Chat history cleared.")
        return None, False
    
    if cmd == '/stats':
        handle_stats(messages, uid)
        return None, False
    
    if cmd == '/export':
        handle_export(messages, uid)
        return None, False
    
    if cmd == '/import':
        handle_import(messages, uid, arg)
        return None, False
    
    if cmd == '/users':
        handle_users()
        return None, False
    
    if cmd == '/switch':
        if not arg:
            print_error("Usage: /switch <user_id>")
            return None, False
        return f"SWITCH:{arg}", False
    
    if cmd in ('/help', '/commands', '/?'):
        print_header("Available Commands")
        commands = [
            ("/help", "Show this help message"),
            ("/history", "Show chat history"),
            ("/search <query>", "Search messages"),
            ("/clear", "Clear chat history"),
            ("/stats", "Show chat statistics"),
            ("/time", "Show current time"),
            ("/date", "Show current date"),
            ("/joke", "Tell a random joke"),
            ("/export", "Export chat to JSON"),
            ("/import <file>", "Import chat from JSON"),
            ("/users", "List all users"),
            ("/switch <user>", "Switch to different user"),
            ("/exit", "Exit the chat"),
        ]
        for command, description in commands:
            print(f"{colored(command.ljust(20), Colors.GREEN)} {description}")
        return None, False
    
    if cmd == '/time':
        return f"⏰ Current time: {datetime.now().strftime('%I:%M:%S %p')}", False
    
    if cmd == '/date':
        return f"📅 Today is {datetime.now().strftime('%A, %B %d, %Y')}", False
    
    if cmd == '/joke':
        return handle_joke(), False
    
    print_error(f"Unknown command: {cmd}. Type /help for available commands.")
    return None, False

# ===== MAIN APPLICATION =====
def main():
    """Main application entry point."""
    parser = argparse.ArgumentParser(description='ChatPy CLI - Enhanced chatbot')
    parser.add_argument('--user', '-u', help='User ID to use')
    parser.add_argument('--debug', '-d', action='store_true', help='Enable debug mode')
    args = parser.parse_args()
    
    # Print welcome banner
    print_header("ChatPy CLI - Enhanced Chatbot")
    print(colored("Type your message or /help for commands", Colors.CYAN))
    
    # Get or create user ID
    if args.user:
        uid = args.user
        print_info(f"Using user ID: {uid}")
    else:
        uid = input(colored('\nEnter user ID (press Enter for new): ', Colors.CYAN)).strip()
        if not uid:
            uid = uuid.uuid4().hex[:8]
            print_success(f"Created new user ID: {uid}")
    
    # Load messages
    messages = load_user_chat(uid)
    if messages:
        print_info(f"Loaded {len(messages)} message(s)")
    
    # Main chat loop
    print()
    while True:
        try:
            user_input = input(colored('You: ', Colors.GREEN + Colors.BOLD)).strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{colored('Goodbye! 👋', Colors.CYAN)}")
            break
        
        if not user_input:
            continue
        
        # Handle commands
        if user_input.startswith('/'):
            response, should_exit = handle_command(user_input, uid, messages)
            
            if should_exit:
                print(colored('Goodbye! Thanks for chatting! 👋', Colors.CYAN))
                break
            
            if response:
                if response.startswith('SWITCH:'):
                    new_uid = response.split(':', 1)[1]
                    save_user_chat(uid, messages)
                    uid = new_uid
                    messages = load_user_chat(uid)
                    print_success(f"Switched to user: {uid}")
                    if messages:
                        print_info(f"Loaded {len(messages)} message(s)")
                else:
                    print(colored('Bot: ', Colors.BLUE + Colors.BOLD) + response)
            continue
        
        # Add user message
        messages.append({
            "id": uuid.uuid4().hex,
            "who": "me",
            "text": user_input,
            "ts": now_ts()
        })
        
        # Generate and add bot reply
        reply = rule_based_reply(user_input)
        messages.append({
            "id": uuid.uuid4().hex,
            "who": "bot",
            "text": reply,
            "ts": now_ts()
        })
        
        # Save and display
        save_user_chat(uid, messages)
        print(colored('Bot: ', Colors.BLUE + Colors.BOLD) + reply)


if __name__ == '__main__':
    main()