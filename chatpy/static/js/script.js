// ===== CONFIGURATION =====
const CONFIG = {
    API_ENDPOINT: '/get_response',
    API_TIMEOUT: 30000,
    MAX_MESSAGE_LENGTH: 5000,
    TYPING_DELAY: 300,
    AUTO_SCROLL_THRESHOLD: 100,
    STORAGE_KEY: 'chatbot_history',
    THEME_KEY: 'chatbot_theme'
};

// ===== STATE MANAGEMENT =====
const state = {
    isOnline: navigator.onLine,
    isTyping: false,
    messageHistory: [],
    currentTheme: 'light'
};

// ===== DOM ELEMENTS =====
const elements = {
    chatMessages: document.getElementById('chat-messages'),
    messageInput: document.getElementById('message-input'),
    sendBtn: document.getElementById('send-btn'),
    typingIndicator: document.getElementById('typing-indicator'),
    themeToggle: document.getElementById('theme-toggle'),
    searchBtn: document.getElementById('search-btn'),
    voiceBtn: document.getElementById('voice-btn'),
    exportBtn: document.getElementById('export-btn'),
    menuBtn: document.getElementById('menu-btn'),
    attachmentBtn: document.getElementById('attachment-btn'),
    emojiBtn: document.getElementById('emoji-btn'),
    statusText: document.querySelector('.status-text'),
    statusIndicator: document.querySelector('.status-indicator')
};

// ===== INITIALIZATION =====
function init() {
    loadTheme();
    loadHistory();
    setupEventListeners();
    updateOnlineStatus();
    autoResizeTextarea();
    
    // Focus input on load
    elements.messageInput.focus();
}

// ===== EVENT LISTENERS =====
function setupEventListeners() {
    // Message sending
    elements.sendBtn.addEventListener('click', handleSendMessage);
    elements.messageInput.addEventListener('keydown', handleKeyPress);
    elements.messageInput.addEventListener('input', autoResizeTextarea);
    
    // Theme toggle
    elements.themeToggle.addEventListener('click', toggleTheme);
    
    // Other actions
    elements.searchBtn.addEventListener('click', handleSearch);
    elements.voiceBtn.addEventListener('click', handleVoiceInput);
    elements.exportBtn.addEventListener('click', handleExport);
    elements.menuBtn.addEventListener('click', handleMenu);
    elements.attachmentBtn.addEventListener('click', handleAttachment);
    elements.emojiBtn.addEventListener('click', handleEmoji);
    
    // Quick action buttons
    document.querySelectorAll('.quick-action-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const command = btn.dataset.command;
            if (command) {
                elements.messageInput.value = command;
                handleSendMessage();
            }
        });
    });
    
    // Suggestion cards
    document.querySelectorAll('.suggestion-card').forEach(card => {
        card.addEventListener('click', () => {
            const message = card.dataset.message;
            if (message) {
                elements.messageInput.value = message;
                handleSendMessage();
            }
        });
    });
    
    // Online/Offline detection
    window.addEventListener('online', updateOnlineStatus);
    window.addEventListener('offline', updateOnlineStatus);
    
    // Prevent form submission
    elements.messageInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
        }
    });
}

// ===== MESSAGE HANDLING =====
async function handleSendMessage() {
    const message = elements.messageInput.value.trim();
    
    if (!message) {
        elements.messageInput.focus();
        return;
    }
    
    if (message.length > CONFIG.MAX_MESSAGE_LENGTH) {
        showSystemMessage(`Message too long. Maximum ${CONFIG.MAX_MESSAGE_LENGTH} characters.`);
        return;
    }
    
    // Clear input and disable controls
    elements.messageInput.value = '';
    autoResizeTextarea();
    setInputState(false);
    
    // Hide welcome screen
    hideWelcomeScreen();
    
    // Add user message
    addMessage(message, 'user');
    
    // Check for local commands
    const localResponse = handleLocalCommand(message);
    if (localResponse) {
        setTimeout(() => {
            addMessage(localResponse, 'bot');
            saveToHistory(message, localResponse);
            setInputState(true);
        }, CONFIG.TYPING_DELAY);
        return;
    }
    
    // Check online status
    if (!state.isOnline) {
        setTimeout(() => {
            addMessage('🔴 You are offline. Please check your connection or use local commands like /help, /time, /date, /joke.', 'system');
            setInputState(true);
        }, CONFIG.TYPING_DELAY);
        return;
    }
    
    // Send to API
    showTyping();
    
    try {
        const response = await fetch(CONFIG.API_ENDPOINT, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message }),
            signal: AbortSignal.timeout(CONFIG.API_TIMEOUT)
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        hideTyping();
        
        const reply = data.reply || 'No response received';
        addMessage(reply, 'bot');
        saveToHistory(message, reply);
        
    } catch (error) {
        hideTyping();
        
        let errorMessage = '❌ Error sending message. ';
        if (error.name === 'AbortError') {
            errorMessage += 'Request timeout.';
        } else if (!navigator.onLine) {
            errorMessage += 'You are offline.';
        } else {
            errorMessage += error.message;
        }
        
        addMessage(errorMessage, 'system');
    } finally {
        setInputState(true);
    }
}

function handleKeyPress(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSendMessage();
    } else if (e.key === 'Escape') {
        elements.messageInput.value = '';
        autoResizeTextarea();
    } else if (e.key === 'ArrowUp' && !elements.messageInput.value) {
        e.preventDefault();
        const lastUserMessage = state.messageHistory.filter(m => m.type === 'user').pop();
        if (lastUserMessage) {
            elements.messageInput.value = lastUserMessage.text;
            autoResizeTextarea();
        }
    }
}

// ===== LOCAL COMMANDS =====
function handleLocalCommand(message) {
    const cmd = message.toLowerCase().trim();
    
    const commands = {
        '/help': () => `📋 Available Commands:
        
/time - Show current time
/date - Show current date
/joke - Tell a random joke
/help - Show this help message
/history - View chat history
/clear - Clear chat history
/search [query] - Search messages

You can also chat naturally with the AI when online!`,
        
        '/time': () => {
            const now = new Date();
            return `⏰ Current time: ${now.toLocaleTimeString('en-US', { 
                hour: '2-digit', 
                minute: '2-digit', 
                second: '2-digit',
                hour12: true 
            })}`;
        },
        
        '/date': () => {
            const now = new Date();
            return `📅 Today's date: ${now.toLocaleDateString('en-US', { 
                weekday: 'long', 
                year: 'numeric', 
                month: 'long', 
                day: 'numeric' 
            })}`;
        },
        
        '/joke': () => {
            const jokes = [
                "Why don't scientists trust atoms? Because they make up everything! 😄",
                "Why did the scarecrow win an award? He was outstanding in his field! 🌾",
                "What do you call a fake noodle? An impasta! 🍝",
                "Why don't eggs tell jokes? They'd crack each other up! 🥚",
                "What do you call a bear with no teeth? A gummy bear! 🐻",
                "Why did the math book look sad? It had too many problems! 📚",
                "What did the ocean say to the beach? Nothing, it just waved! 🌊",
                "Why can't bicycles stand on their own? They're two tired! 🚲"
            ];
            return jokes[Math.floor(Math.random() * jokes.length)];
        },
        
        '/history': () => {
            if (state.messageHistory.length === 0) {
                return '📜 No message history yet.';
            }
            const count = state.messageHistory.length;
            return `📜 You have ${count} message${count !== 1 ? 's' : ''} in history. Use /clear to clear history.`;
        },
        
        '/clear': () => {
            state.messageHistory = [];
            localStorage.removeItem(CONFIG.STORAGE_KEY);
            clearMessages();
            showWelcomeScreen();
            return '🗑️ Chat history cleared!';
        }
    };
    
    // Handle search command
    if (cmd.startsWith('/search ')) {
        const query = message.slice(8).trim();
        if (!query) {
            return '🔍 Usage: /search [query]';
        }
        return searchMessages(query);
    }
    
    // Execute command
    const command = commands[cmd];
    return command ? command() : null;
}

function searchMessages(query) {
    const results = state.messageHistory.filter(msg => 
        msg.text.toLowerCase().includes(query.toLowerCase())
    );
    
    if (results.length === 0) {
        return `🔍 No messages found for "${query}"`;
    }
    
    return `🔍 Found ${results.length} message${results.length !== 1 ? 's' : ''} matching "${query}":\n\n` +
        results.slice(0, 5).map(msg => `• ${msg.text.slice(0, 100)}...`).join('\n');
}

// ===== MESSAGE DISPLAY =====
function addMessage(text, type = 'bot') {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}`;
    
    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';
    
    const textDiv = document.createElement('div');
    textDiv.className = 'message-text';
    textDiv.textContent = text;
    
    const timeDiv = document.createElement('div');
    timeDiv.className = 'message-time';
    timeDiv.textContent = formatTime(new Date());
    
    bubble.appendChild(textDiv);
    bubble.appendChild(timeDiv);
    messageDiv.appendChild(bubble);
    
    // Insert before typing indicator
    const typingIndicator = elements.typingIndicator;
    elements.chatMessages.insertBefore(messageDiv, typingIndicator);
    
    // Scroll to bottom
    scrollToBottom();
}

function showSystemMessage(text) {
    addMessage(text, 'system');
}

function clearMessages() {
    const messages = elements.chatMessages.querySelectorAll('.message');
    messages.forEach(msg => msg.remove());
}

function hideWelcomeScreen() {
    const welcomeScreen = document.querySelector('.welcome-screen');
    if (welcomeScreen) {
        welcomeScreen.style.display = 'none';
    }
}

function showWelcomeScreen() {
    const welcomeScreen = document.querySelector('.welcome-screen');
    if (welcomeScreen) {
        welcomeScreen.style.display = 'flex';
    }
}

// ===== TYPING INDICATOR =====
function showTyping() {
    state.isTyping = true;
    elements.typingIndicator.classList.add('active');
    scrollToBottom();
}

function hideTyping() {
    state.isTyping = false;
    elements.typingIndicator.classList.remove('active');
}

// ===== UI UTILITIES =====
function setInputState(enabled) {
    elements.messageInput.disabled = !enabled;
    elements.sendBtn.disabled = !enabled;
    
    if (enabled) {
        elements.messageInput.focus();
    }
}

function autoResizeTextarea() {
    const textarea = elements.messageInput;
    textarea.style.height = 'auto';
    textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
}

function scrollToBottom(smooth = true) {
    const behavior = smooth ? 'smooth' : 'auto';
    elements.chatMessages.scrollTo({
        top: elements.chatMessages.scrollHeight,
        behavior
    });
}

function formatTime(date) {
    return date.toLocaleTimeString('en-US', { 
        hour: '2-digit', 
        minute: '2-digit',
        hour12: true 
    });
}

// ===== THEME MANAGEMENT =====
function toggleTheme() {
    state.currentTheme = state.currentTheme === 'light' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', state.currentTheme);
    localStorage.setItem(CONFIG.THEME_KEY, state.currentTheme);
}

function loadTheme() {
    const savedTheme = localStorage.getItem(CONFIG.THEME_KEY);
    if (savedTheme) {
        state.currentTheme = savedTheme;
        document.documentElement.setAttribute('data-theme', savedTheme);
    }
}

// ===== ONLINE STATUS =====
function updateOnlineStatus() {
    state.isOnline = navigator.onLine;
    
    if (state.isOnline) {
        elements.statusText.textContent = 'Online';
        elements.statusIndicator.classList.remove('offline');
    } else {
        elements.statusText.textContent = 'Offline';
        elements.statusIndicator.classList.add('offline');
        showSystemMessage('📡 Connection lost. You are now in offline mode.');
    }
}

// ===== HISTORY MANAGEMENT =====
function saveToHistory(userMessage, botReply) {
    state.messageHistory.push(
        { text: userMessage, type: 'user', timestamp: new Date().toISOString() },
        { text: botReply, type: 'bot', timestamp: new Date().toISOString() }
    );
    
    // Keep only last 100 messages
    if (state.messageHistory.length > 100) {
        state.messageHistory = state.messageHistory.slice(-100);
    }
    
    localStorage.setItem(CONFIG.STORAGE_KEY, JSON.stringify(state.messageHistory));
}

function loadHistory() {
    try {
        const saved = localStorage.getItem(CONFIG.STORAGE_KEY);
        if (saved) {
            state.messageHistory = JSON.parse(saved);
            
            // Restore last 10 messages
            const recentMessages = state.messageHistory.slice(-10);
            if (recentMessages.length > 0) {
                hideWelcomeScreen();
                recentMessages.forEach(msg => {
                    addMessage(msg.text, msg.type);
                });
            }
        }
    } catch (error) {
        console.error('Error loading history:', error);
    }
}

// ===== ADDITIONAL FEATURES =====
function handleSearch() {
    const query = prompt('🔍 Search chat history:');
    if (query) {
        const result = searchMessages(query);
        showSystemMessage(result);
    }
}

function handleVoiceInput() {
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
        showSystemMessage('🎤 Voice input is not supported in your browser.');
        return;
    }
    
    try {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        const recognition = new SpeechRecognition();
        
        recognition.lang = 'en-US';
        recognition.continuous = false;
        recognition.interimResults = false;
        
        recognition.onstart = () => {
            elements.voiceBtn.style.color = '#ef4444';
            showSystemMessage('🎤 Listening...');
        };
        
        recognition.onresult = (event) => {
            const transcript = event.results[0][0].transcript;
            elements.messageInput.value = transcript;
            autoResizeTextarea();
            elements.messageInput.focus();
        };
        
        recognition.onerror = (event) => {
            showSystemMessage(`🎤 Voice input error: ${event.error}`);
            elements.voiceBtn.style.color = '';
        };
        
        recognition.onend = () => {
            elements.voiceBtn.style.color = '';
        };
        
        recognition.start();
    } catch (error) {
        showSystemMessage('🎤 Voice input failed: ' + error.message);
    }
}

function handleExport() {
    if (state.messageHistory.length === 0) {
        showSystemMessage('💾 No messages to export.');
        return;
    }
    
    try {
        const content = state.messageHistory.map(msg => 
            `[${msg.type.toUpperCase()}] ${new Date(msg.timestamp).toLocaleString()}\n${msg.text}\n`
        ).join('\n---\n\n');
        
        const blob = new Blob([content], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `chat-history-${Date.now()}.txt`;
        a.click();
        URL.revokeObjectURL(url);
        
        showSystemMessage('💾 Chat history exported successfully!');
    } catch (error) {
        showSystemMessage('💾 Export failed: ' + error.message);
    }
}

function handleMenu() {
    showSystemMessage('⚙️ Menu feature coming soon!');
}

function handleAttachment() {
    showSystemMessage('📎 File attachment feature coming soon!');
}

function handleEmoji() {
    const emojis = ['😊', '😄', '😍', '🤔', '👍', '❤️', '🎉', '🔥', '✨', '💡'];
    const emoji = emojis[Math.floor(Math.random() * emojis.length)];
    elements.messageInput.value += emoji;
    autoResizeTextarea();
    elements.messageInput.focus();
}

// ===== START APPLICATION =====
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}