const chatMessages = document.getElementById('chat-messages');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const typingIndicator = document.getElementById('typing-indicator');

// API کنفیگریشن
const API_CONFIG = {
    BASE_URL: 'http://localhost:5000',
    ENDPOINTS: {
        CHAT: '/chat'
    }
};

// پیغام بھیجنے کا فنکشن
async function sendMessage() {
    const message = userInput.value.trim();
    if (!message) return;

    // UI اپ ڈیٹ
    addMessage(message, true);
    userInput.value = '';
    sendBtn.disabled = true;
    showTypingIndicator();

    try {
        const response = await fetch(API_CONFIG.BASE_URL + API_CONFIG.ENDPOINTS.CHAT, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ message: message })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        
        if (data.reply) {
            hideTypingIndicator();
            setTimeout(() => {
                addMessage(data.reply, false);
            }, 1000);
        } else {
            throw new Error('Invalid response format');
        }
    } catch (error) {
        console.error('Error:', error);
        hideTypingIndicator();
        addMessage('معذرت، کنکشن میں مسئلہ ہے۔ براہ کرم دوبارہ کوشش کریں۔', false);
    } finally {
        sendBtn.disabled = false;
    }
}

// نیا پیغام شامل کرنے کا فنکشن
function addMessage(message, isUser = false) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${isUser ? 'user-message' : 'ai-message'}`;
    
    const messageContent = `
        <div class="message-content">
            <div class="message-header">
                <i class="fas ${isUser ? 'fa-user' : 'fa-robot'}"></i>
                <span>${isUser ? 'آپ' : 'AI معاون'}</span>
            </div>
            <p>${message}</p>
        </div>
    `;
    
    messageDiv.innerHTML = messageContent;
    chatMessages.appendChild(messageDiv);
    
    // سکرول کو نیچے لے جانا
    scrollToBottom();
}

// سکرول کو نیچے لے جانے کا فنکشن
function scrollToBottom() {
    chatMessages.scrollTo({
        top: chatMessages.scrollHeight,
        behavior: 'smooth'
    });
}

// ٹائپنگ انڈیکیٹر دکھانے کا فنکشن
function showTypingIndicator() {
    typingIndicator.style.display = 'flex';
    scrollToBottom();
}

// ٹائپنگ انڈیکیٹر چھپانے کا فنکشن
function hideTypingIndicator() {
    typingIndicator.style.display = 'none';
}

// چیٹ صاف کرنے کا فنکشن
function clearChat() {
    if (confirm('کیا آپ واقعی تمام چیٹ صاف کرنا چاہتے ہیں؟')) {
        chatMessages.innerHTML = `
            <div class="message ai-message">
                <div class="message-content">
                    <div class="message-header">
                        <i class="fas fa-robot"></i>
                        <span>AI معاون</span>
                    </div>
                    <p>ہیلو! 👋 میں آپ کی کیسے مدد کر سکتا ہوں؟</p>
                </div>
            </div>
        `;
    }
}

// کی بورڈ ایونٹ ہینڈلنگ
function handleKeyPress(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
}

// ایونٹ لسٹنرز
userInput.addEventListener('input', function() {
    sendBtn.disabled = this.value.trim() === '';
});

userInput.addEventListener('keypress', handleKeyPress);
sendBtn.addEventListener('click', sendMessage);

// ان پٹ پر فوکس
window.addEventListener('load', () => {
    userInput.focus();
});

// آن لائن/آف لائن ڈیٹیکشن
window.addEventListener('online', () => {
    showNotification('کنکشن بحال ہو گیا ہے', 'success');
});

window.addEventListener('offline', () => {
    showNotification('کنکشن منقطع ہو گیا ہے', 'error');
});

// نوٹیفکیشن دکھانے کا فنکشن
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 15px 20px;
        border-radius: 10px;
        color: white;
        font-weight: 600;
        z-index: 1000;
        animation: slideIn 0.3s ease;
    `;
    
    if (type === 'success') notification.style.background = '#10b981';
    if (type === 'error') notification.style.background = '#ef4444';
    if (type === 'info') notification.style.background = '#3b82f6';
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.remove();
    }, 3000);
}

// localStorage میں چیٹ سیو کرنے کا فنکشن (اختیاری)
function saveChatToLocalStorage() {
    const messages = chatMessages.innerHTML;
    localStorage.setItem('chatHistory', messages);
}

function loadChatFromLocalStorage() {
    const savedChat = localStorage.getItem('chatHistory');
    if (savedChat) {
        chatMessages.innerHTML = savedChat;
        scrollToBottom();
    }
}

// پیج لوڈ ہونے پر ڈیٹا لوڈ کریں
window.addEventListener('load', loadChatFromLocalStorage);

// چیٹ میں تبدیلی پر ڈیٹا سیو کریں
chatMessages.addEventListener('DOMNodeInserted', saveChatToLocalStorage);