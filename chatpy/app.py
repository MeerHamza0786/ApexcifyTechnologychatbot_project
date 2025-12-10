"""
Enhanced Flask ChatBot with OpenAI Integration
Features: Intent detection, context memory, rate limiting, error handling, and more
"""

import os
import json
import uuid
import random
import re
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from functools import wraps
from collections import defaultdict

from flask import Flask, render_template, request, jsonify, session, send_file
from typing import TYPE_CHECKING
import importlib

if TYPE_CHECKING:
    # Provide imports for type checkers / linters without requiring the package at runtime
    from flask_limiter import Limiter  # type: ignore
    from flask_limiter.util import get_remote_address  # type: ignore

# Runtime import handling for optional dependency
try:
    if importlib.util.find_spec("flask_limiter") is not None:
        from flask_limiter import Limiter
        from flask_limiter.util import get_remote_address
        _FLASK_LIMITER_AVAILABLE = True
    else:
        raise ModuleNotFoundError
except Exception:  # pragma: no cover - optional dependency
    Limiter = None
    _FLASK_LIMITER_AVAILABLE = False

    def get_remote_address():
        try:
            return request.remote_addr
        except Exception:
            return '127.0.0.1'

from dotenv import load_dotenv
from openai import OpenAI

# ===== CONFIGURATION =====
load_dotenv()

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Flask app setup
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", os.urandom(24).hex())

# Configuration
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=timedelta(days=7),
    MAX_CONTENT_LENGTH=16 * 1024 * 1024,  # 16MB max request size
    JSON_SORT_KEYS=False
)

# Rate limiting (optional)
if _FLASK_LIMITER_AVAILABLE and Limiter is not None:
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=["200 per day", "50 per hour"],
        storage_uri="memory://"
    )
else:
    # Provide a noop limiter so decorators like @limiter.limit(...) still work
    class _NoopLimiter:
        def limit(self, *args, **kwargs):
            def _decorator(f):
                return f
            return _decorator

    limiter = _NoopLimiter()

# OpenAI client
openai_api_key = os.getenv("OPENAI_API_KEY")
if openai_api_key:
    client = OpenAI(api_key=openai_api_key)
    logger.info("OpenAI client initialized successfully")
else:
    client = None
    logger.warning("OPENAI_API_KEY not found - AI features will be disabled")

# ===== DATA STORAGE =====
# In production, replace with Redis, PostgreSQL, or MongoDB
conversations: Dict[str, List[Dict[str, Any]]] = {}
user_metadata: Dict[str, Dict[str, Any]] = {}
message_stats = defaultdict(lambda: {"count": 0, "last_reset": datetime.now()})

# ===== CONSTANTS =====
MAX_HISTORY_LENGTH = 100
CONTEXT_WINDOW = 8
MAX_MESSAGE_LENGTH = 2000
AI_MODEL = "gpt-3.5-turbo"
AI_TEMPERATURE = 0.7
AI_MAX_TOKENS = 300

# ===== INTENT DETECTION =====
INTENTS = {
    'greeting': {
        'patterns': [
            r'\b(hello|hi|hey|greetings|good\s+(morning|afternoon|evening)|howdy|sup)\b'
        ],
        'responses': [
            "Hello! I'm here to help. What can I do for you today? 👋",
            "Hi there! How can I assist you? 😊",
            "Hey! Welcome! What would you like to know?",
            "Greetings! How may I help you today?"
        ],
        'confidence': 0.9
    },
    'wellbeing': {
        'patterns': [
            r'how\s+are\s+you',
            r"how'?s\s+it\s+going",
            r"what'?s\s+up",
            r'how\s+do\s+you\s+do'
        ],
        'responses': [
            "I'm doing great, thanks for asking! How can I help you today? 😊",
            "All systems running smoothly! How about you?",
            "I'm functioning perfectly! What can I do for you?",
            "Doing wonderful! How are you doing?"
        ],
        'confidence': 0.85
    },
    'capabilities': {
        'patterns': [
            r'what\s+can\s+you\s+do',
            r'your\s+capabilities',
            r'what\s+are\s+you\s+capable\s+of',
            r'what\s+do\s+you\s+do'
        ],
        'responses': [
            "I can chat with you, answer questions, help with tasks, check time/date, tell jokes, and more! Just ask away! 💡",
            "I'm here to assist with conversations, provide information, and help you with various tasks. Type /help for commands!"
        ],
        'confidence': 0.9
    },
    'help': {
        'patterns': [
            r'\bhelp\b',
            r'\bassist(ance)?\b',
            r'\bsupport\b',
            r'need\s+help'
        ],
        'responses': [
            "I'm here to help! You can ask me questions, use commands (type /help), or just chat naturally! 🤝"
        ],
        'confidence': 0.8
    },
    'time': {
        'patterns': [
            r'\b(what\s+)?time(\s+is\s+it)?\b',
            r'current\s+time',
            r"o'clock",
            r'tell\s+me\s+the\s+time'
        ],
        'responses': [lambda: f"⏰ The current time is {datetime.now().strftime('%I:%M:%S %p')}."],
        'confidence': 0.95
    },
    'date': {
        'patterns': [
            r'\b(what\s+)?date(\s+is\s+it)?\b',
            r'what\s+day\s+is\s+it',
            r"today'?s\s+date",
            r'current\s+date'
        ],
        'responses': [lambda: f"📅 Today is {datetime.now().strftime('%A, %B %d, %Y')}."],
        'confidence': 0.95
    },
    'thanks': {
        'patterns': [
            r'\b(thank\s*you|thanks|thx|appreciate\s+it|grateful)\b'
        ],
        'responses': [
            "You're welcome! 😊",
            "Happy to help! 🤗",
            "Anytime! Glad I could assist!",
            "My pleasure! Let me know if you need anything else!"
        ],
        'confidence': 0.9
    },
    'goodbye': {
        'patterns': [
            r'\b(bye|goodbye|see\s+you|farewell|later|cya|take\s+care)\b'
        ],
        'responses': [
            "Goodbye! Have a wonderful day! 👋",
            "Take care! Come back anytime! 😊",
            "See you later! It was nice chatting with you!",
            "Farewell! Feel free to return whenever you need help!"
        ],
        'confidence': 0.9
    },
    'name': {
        'patterns': [
            r"what'?s\s+your\s+name",
            r'who\s+are\s+you',
            r'introduce\s+yourself'
        ],
        'responses': [
            "I'm ChatBot, your friendly AI assistant! 🤖",
            "You can call me ChatBot - I'm here to help you! 😊"
        ],
        'confidence': 0.9
    },
    'joke': {
        'patterns': [
            r'\b(tell\s+me\s+)?a?\s*joke\b',
            r'make\s+me\s+laugh',
            r'something\s+funny'
        ],
        'responses': [
            lambda: get_random_joke()
        ],
        'confidence': 0.85
    }
}

def get_random_joke() -> str:
    """Return a random joke."""
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
        "Why did the variable break up with the constant? She needed some space! 🚀",
        "What's a computer's favorite snack? Microchips! 🍟",
        "Why was the JavaScript developer sad? Because he didn't Node how to Express himself! 😢"
    ]
    return random.choice(jokes)

def detect_intent(message: str) -> Tuple[str, float]:
    """
    Detect intent from message using regex patterns.
    Returns: (intent_name, confidence_score)
    """
    message_lower = message.lower().strip()
    
    best_intent = 'unknown'
    best_confidence = 0.0
    
    for intent_name, intent_data in INTENTS.items():
        for pattern in intent_data['patterns']:
            if re.search(pattern, message_lower, re.IGNORECASE):
                confidence = intent_data.get('confidence', 0.5)
                if confidence > best_confidence:
                    best_intent = intent_name
                    best_confidence = confidence
    
    return best_intent, best_confidence

# ===== COMMAND HANDLERS =====
def handle_local_command(cmd: str, conversation_id: str) -> Optional[Dict[str, Any]]:
    """Handle local slash commands."""
    cmd_lower = cmd.lower().strip()
    parts = cmd_lower.split(maxsplit=1)
    command = parts[0]
    argument = parts[1] if len(parts) > 1 else ""
    
    handlers = {
        '/time': lambda: {
            'reply': f"⏰ Current time: {datetime.now().strftime('%I:%M:%S %p')}",
            'type': 'info'
        },
        '/date': lambda: {
            'reply': f"📅 Today is {datetime.now().strftime('%A, %B %d, %Y')}",
            'type': 'info'
        },
        '/help': lambda: {
            'reply': get_help_text(),
            'type': 'info'
        },
        '/commands': lambda: {
            'reply': get_help_text(),
            'type': 'info'
        },
        '/joke': lambda: {
            'reply': get_random_joke(),
            'type': 'info'
        },
        '/history': lambda: {
            'reply': get_conversation_history(conversation_id),
            'type': 'info'
        },
        '/whoami': lambda: {
            'reply': f"🔑 Your conversation ID: `{conversation_id}`\n"
                    f"📊 Messages in session: {len(conversations.get(conversation_id, []))}",
            'type': 'info'
        },
        '/clear': lambda: clear_conversation_history(conversation_id),
        '/clear_history': lambda: clear_conversation_history(conversation_id),
        '/stats': lambda: get_conversation_stats(conversation_id),
        '/export': lambda: export_conversation(conversation_id),
    }
    
    # Handle search command separately
    if command == '/search':
        if not argument:
            return {
                'reply': '🔍 Usage: /search <query>\nExample: /search hello',
                'type': 'error'
            }
        return search_conversation(conversation_id, argument)
    
    # Execute command handler
    handler = handlers.get(command)
    if handler:
        try:
            result = handler()
            return result if isinstance(result, dict) else {'reply': str(result), 'type': 'info'}
        except Exception as e:
            logger.error(f"Error handling command {command}: {e}")
            return {'reply': f'❌ Error executing command: {str(e)}', 'type': 'error'}
    
    return {
        'reply': f'❌ Unknown command: {command}\nType /help for available commands.',
        'type': 'error'
    }

def get_help_text() -> str:
    """Return formatted help text."""
    return """📋 **Available Commands:**

**Information:**
• `/time` - Show current time
• `/date` - Show current date
• `/joke` - Tell a random joke
• `/stats` - View conversation statistics

**History:**
• `/history` - View recent messages
• `/search <query>` - Search your messages
• `/clear` - Clear conversation history
• `/export` - Export conversation as JSON

**Other:**
• `/whoami` - Show your session info
• `/help` - Show this help message

💡 **Tip:** You can also just chat naturally with me!"""

def get_conversation_history(conversation_id: str, limit: int = 10) -> str:
    """Get formatted conversation history."""
    msgs = conversations.get(conversation_id, [])
    
    if not msgs:
        return "📜 No conversation history yet."
    
    history_lines = [f"📜 **Recent Messages** (last {min(limit, len(msgs))}):\n"]
    
    for msg in msgs[-limit:]:
        role = msg.get('role', 'unknown')
        message = msg.get('message', '')
        timestamp = msg.get('timestamp', '')
        
        icon = "👤" if role == 'user' else "🤖"
        who = "You" if role == 'user' else "Bot"
        
        # Truncate long messages
        if len(message) > 100:
            message = message[:97] + "..."
        
        history_lines.append(f"{icon} **[{timestamp}] {who}:** {message}")
    
    return "\n".join(history_lines)

def clear_conversation_history(conversation_id: str) -> Dict[str, Any]:
    """Clear conversation history for a user."""
    if conversation_id in conversations:
        msg_count = len(conversations[conversation_id])
        conversations[conversation_id] = []
        return {
            'reply': f'🗑️ Cleared {msg_count} message(s) from your history.',
            'type': 'success'
        }
    return {
        'reply': '📭 No history to clear.',
        'type': 'info'
    }

def get_conversation_stats(conversation_id: str) -> Dict[str, Any]:
    """Get conversation statistics."""
    msgs = conversations.get(conversation_id, [])
    
    if not msgs:
        return {'reply': '📊 No statistics available yet.', 'type': 'info'}
    
    user_msgs = [m for m in msgs if m.get('role') == 'user']
    bot_msgs = [m for m in msgs if m.get('role') == 'bot']
    
    total_words_user = sum(len(m.get('message', '').split()) for m in user_msgs)
    total_words_bot = sum(len(m.get('message', '').split()) for m in bot_msgs)
    
    first_msg = msgs[0].get('timestamp', 'Unknown') if msgs else 'N/A'
    last_msg = msgs[-1].get('timestamp', 'Unknown') if msgs else 'N/A'
    
    stats_text = f"""📊 **Conversation Statistics:**

💬 Total messages: {len(msgs)}
👤 Your messages: {len(user_msgs)} ({total_words_user} words)
🤖 Bot messages: {len(bot_msgs)} ({total_words_bot} words)
⏰ First message: {first_msg}
🕐 Last message: {last_msg}
🔑 Session ID: `{conversation_id[:16]}...`"""
    
    return {'reply': stats_text, 'type': 'info'}

def search_conversation(conversation_id: str, query: str) -> Dict[str, Any]:
    """Search conversation for specific text."""
    msgs = conversations.get(conversation_id, [])
    
    if not msgs:
        return {'reply': '🔍 No messages to search.', 'type': 'info'}
    
    query_lower = query.lower()
    results = [m for m in msgs if query_lower in m.get('message', '').lower()]
    
    if not results:
        return {
            'reply': f'🔍 No messages found matching "{query}"',
            'type': 'info'
        }
    
    result_lines = [f'🔍 **Found {len(results)} message(s) matching "{query}":**\n']
    
    for msg in results[-5:]:  # Show last 5 results
        role = "You" if msg.get('role') == 'user' else "Bot"
        message = msg.get('message', '')
        timestamp = msg.get('timestamp', '')
        
        if len(message) > 80:
            message = message[:77] + "..."
        
        result_lines.append(f"• **[{timestamp}] {role}:** {message}")
    
    return {'reply': '\n'.join(result_lines), 'type': 'info'}

def export_conversation(conversation_id: str) -> Dict[str, Any]:
    """Export conversation as JSON."""
    msgs = conversations.get(conversation_id, [])
    
    if not msgs:
        return {'reply': '📭 No messages to export.', 'type': 'info'}
    
    try:
        export_data = {
            'conversation_id': conversation_id,
            'export_time': datetime.now().isoformat(),
            'message_count': len(msgs),
            'messages': msgs
        }
        
        json_str = json.dumps(export_data, ensure_ascii=False, indent=2)
        
        return {
            'reply': '📦 **Conversation Export:**\n\nCopy the JSON below:\n\n```json\n' + 
                    json_str[:500] + '\n...\n```\n\n(Full export available via API)',
            'type': 'success',
            'export_data': json_str
        }
    except Exception as e:
        logger.error(f"Export error: {e}")
        return {'reply': f'❌ Export failed: {str(e)}', 'type': 'error'}

# ===== AI INTEGRATION =====
def ask_openai(user_message: str, conversation_id: str) -> str:
    """
    Query OpenAI API with conversation context.
    """
    if not client:
        return "🔴 AI features are currently unavailable. OpenAI API key not configured."
    
    try:
        # Get conversation history
        user_history = conversations.get(conversation_id, [])
        
        # Prepare messages with system prompt
        messages = [{
            "role": "system",
            "content": "You are a helpful, friendly, and concise AI assistant. "
                      "Provide clear and accurate responses. Use emojis sparingly for friendliness."
        }]
        
        # Add context from recent messages
        for msg in user_history[-CONTEXT_WINDOW:]:
            role = "assistant" if msg['role'] == "bot" else "user"
            messages.append({
                "role": role,
                "content": msg['message']
            })
        
        # Add current message
        messages.append({"role": "user", "content": user_message})
        
        # Call OpenAI API
        response = client.chat.completions.create(
            model=AI_MODEL,
            messages=messages,
            temperature=AI_TEMPERATURE,
            max_tokens=AI_MAX_TOKENS,
            timeout=10
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        logger.error(f"OpenAI API error: {e}", exc_info=True)
        return "🔴 I'm having trouble connecting to my AI brain right now. Please try again in a moment."

# ===== HELPER FUNCTIONS =====
def save_message(conversation_id: str, role: str, message: str) -> None:
    """Save message to conversation history."""
    if conversation_id not in conversations:
        conversations[conversation_id] = []
    
    # Limit history length
    if len(conversations[conversation_id]) >= MAX_HISTORY_LENGTH:
        conversations[conversation_id] = conversations[conversation_id][-MAX_HISTORY_LENGTH+1:]
    
    conversations[conversation_id].append({
        'id': str(uuid.uuid4()),
        'role': role,
        'message': message,
        'timestamp': datetime.now().strftime('%I:%M %p')
    })

def validate_message(message: str) -> Tuple[bool, Optional[str]]:
    """Validate user message."""
    if not message or not message.strip():
        return False, "Please type a message!"
    
    if len(message) > MAX_MESSAGE_LENGTH:
        return False, f"Message too long! Maximum {MAX_MESSAGE_LENGTH} characters."
    
    # Check for spam patterns
    if message.count(message[0]) > len(message) * 0.8:
        return False, "Message appears to be spam."
    
    return True, None

def get_or_create_session_id() -> str:
    """Get or create conversation session ID."""
    if 'conversation_id' not in session:
        session['conversation_id'] = str(uuid.uuid4())
        session.permanent = True
    return session['conversation_id']

# ===== ROUTES =====
@app.route("/")
def index():
    """Render main chat interface."""
    conversation_id = get_or_create_session_id()
    logger.info(f"New session: {conversation_id}")
    return render_template("index.html")

@app.route("/get_response", methods=["POST"])
@limiter.limit("30 per minute")
def get_response():
    """Handle chat message and return bot response."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid request"}), 400
        
        user_message = data.get("message", "").strip()
        conversation_id = get_or_create_session_id()
        
        # Validate message
        is_valid, error_msg = validate_message(user_message)
        if not is_valid:
            return jsonify({"error": error_msg}), 400
        
        # Handle local commands first
        if user_message.startswith('/'):
            command_result = handle_local_command(user_message, conversation_id)
            if command_result:
                save_message(conversation_id, 'user', user_message)
                save_message(conversation_id, 'bot', command_result['reply'])
                
                return jsonify({
                    "reply": command_result['reply'],
                    "type": command_result.get('type', 'info'),
                    "timestamp": datetime.now().strftime('%I:%M %p')
                })
        
        # Detect intent
        intent, confidence = detect_intent(user_message)
        
        bot_reply = None
        response_source = "intent"
        
        # Use intent-based response if confidence is high
        if intent != 'unknown' and confidence >= 0.8:
            response_data = INTENTS[intent]['responses']
            response = random.choice(response_data)
            bot_reply = response() if callable(response) else response
        else:
            # Fallback to AI
            bot_reply = ask_openai(user_message, conversation_id)
            response_source = "ai"
        
        # Save messages
        save_message(conversation_id, 'user', user_message)
        save_message(conversation_id, 'bot', bot_reply)
        
        return jsonify({
            "reply": bot_reply,
            "timestamp": datetime.now().strftime('%I:%M %p'),
            "source": response_source,
            "intent": intent if intent != 'unknown' else None
        })
        
    except Exception as e:
        logger.error(f"Error in get_response: {e}", exc_info=True)
        return jsonify({
            "error": "An error occurred processing your message.",
            "details": str(e) if app.debug else None
        }), 500

@app.route("/clear_history", methods=["POST"])
def clear_history_route():
    """Clear conversation history endpoint."""
    conversation_id = get_or_create_session_id()
    result = clear_conversation_history(conversation_id)
    return jsonify({"status": "success", "message": result['reply']})

@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "ai_available": client is not None,
        "active_conversations": len(conversations)
    })

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(429)
def rate_limit_exceeded(error):
    """Handle rate limit errors."""
    return jsonify({"error": "Rate limit exceeded. Please slow down."}), 429

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    logger.error(f"Internal error: {error}", exc_info=True)
    return jsonify({"error": "Internal server error"}), 500

# ===== STARTUP =====
if __name__ == "__main__":
    # Environment checks
    if not os.getenv("OPENAI_API_KEY"):
        logger.warning("⚠️  OPENAI_API_KEY not found - AI features will be disabled")
    
    if not os.getenv("FLASK_SECRET_KEY"):
        logger.warning("⚠️  FLASK_SECRET_KEY not found - using random key (sessions won't persist)")
    
    # Start server
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_ENV") == "development"
    
    logger.info(f"🚀 Starting ChatBot server on port {port}")
    app.run(debug=debug, port=port, host="0.0.0.0")