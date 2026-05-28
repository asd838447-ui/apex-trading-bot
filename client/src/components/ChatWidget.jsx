import React, { useState, useRef, useEffect } from 'react';
import { MessageSquare, Send, Bot, User, Loader2, Brain, X } from 'lucide-react';

export default function ChatWidget() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([
    { id: 1, sender: 'bot', text: 'Привет! Я APEX Deep Brain. Вы можете задавать мне вопросы по рынку или передавать инсайды. Если включите Learning Mode, я буду проверять ваши факты и менять веса бота.' }
  ]);
  const [input, setInput] = useState('');
  const [isLearningMode, setIsLearningMode] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim()) return;
    
    const userMsg = { id: Date.now(), sender: 'user', text: input };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setIsLoading(true);

    try {
      const token = localStorage.getItem('apex_token');
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ message: input, is_learning_mode: isLearningMode })
      });
      
      const data = await response.json();
      const botMsg = { id: Date.now() + 1, sender: 'bot', text: data.reply || 'No response.' };
      setMessages(prev => [...prev, botMsg]);
    } catch (error) {
      setMessages(prev => [...prev, { id: Date.now() + 1, sender: 'bot', text: `❌ Ошибка сети: ${error.message}` }]);
    } finally {
      setIsLoading(false);
    }
  };

  if (!isOpen) {
    return (
      <button 
        onClick={() => setIsOpen(true)}
        style={styles.floatingButton}
        className="glow-cyan"
        aria-label="Open AI Chat"
      >
        <MessageSquare size={24} color="#fff" />
      </button>
    );
  }

  return (
    <div className="glass-card glow-cyan" style={styles.chatWindow}>
      {/* Header */}
      <div style={styles.header}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Bot size={20} color="var(--cyan)" />
          <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>APEX AI Agent</span>
        </div>
        <button onClick={() => setIsOpen(false)} style={styles.closeBtn}>
          <X size={18} />
        </button>
      </div>

      {/* Toggles */}
      <div style={styles.toolbar}>
        <label style={styles.toggleLabel}>
          <input 
            type="checkbox" 
            checked={isLearningMode} 
            onChange={(e) => setIsLearningMode(e.target.checked)} 
            style={styles.checkbox}
          />
          <Brain size={14} color={isLearningMode ? 'var(--emerald)' : 'var(--text-muted)'} />
          <span style={{ color: isLearningMode ? 'var(--emerald)' : 'var(--text-muted)' }}>
            Learning Mode (Fact-Check)
          </span>
        </label>
      </div>

      {/* Messages */}
      <div style={styles.messageArea}>
        {messages.map(msg => (
          <div key={msg.id} style={{
            ...styles.messageWrapper,
            justifyContent: msg.sender === 'user' ? 'flex-end' : 'flex-start'
          }}>
            {msg.sender === 'bot' && <Bot size={16} color="var(--cyan)" style={{ marginTop: '8px' }} />}
            <div style={{
              ...styles.messageBubble,
              background: msg.sender === 'user' ? 'rgba(6, 182, 212, 0.15)' : 'rgba(30, 41, 59, 0.6)',
              border: msg.sender === 'user' ? '1px solid rgba(6, 182, 212, 0.3)' : '1px solid var(--border-subtle)',
              color: msg.sender === 'user' ? 'var(--cyan)' : 'var(--text-primary)',
            }}>
              {msg.text.split('\n').map((line, i) => <React.Fragment key={i}>{line}<br/></React.Fragment>)}
            </div>
          </div>
        ))}
        {isLoading && (
          <div style={{ ...styles.messageWrapper, justifyContent: 'flex-start' }}>
             <Bot size={16} color="var(--cyan)" style={{ marginTop: '8px' }} />
             <div style={styles.loadingBubble}>
                <Loader2 size={16} className="spinner" color="var(--cyan)" />
                <span style={{ color: 'var(--text-muted)', fontSize: '12px' }}>
                  {isLearningMode ? 'Searching & Verifying Facts...' : 'Thinking...'}
                </span>
             </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div style={styles.inputArea}>
        <input 
          type="text" 
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSend()}
          placeholder="Ask or teach the bot..."
          style={styles.input}
        />
        <button onClick={handleSend} disabled={!input.trim() || isLoading} style={styles.sendBtn}>
          <Send size={18} />
        </button>
      </div>
    </div>
  );
}

const styles = {
  floatingButton: {
    position: 'fixed',
    bottom: '24px',
    right: '24px',
    width: '60px',
    height: '60px',
    borderRadius: '30px',
    background: 'linear-gradient(135deg, #06b6d4, #3b82f6)',
    border: 'none',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    cursor: 'pointer',
    zIndex: 1000,
    boxShadow: '0 8px 32px rgba(6, 182, 212, 0.4)'
  },
  chatWindow: {
    position: 'fixed',
    bottom: '24px',
    right: '24px',
    width: '380px',
    height: '550px',
    display: 'flex',
    flexDirection: 'column',
    zIndex: 1000,
    padding: 0,
    overflow: 'hidden'
  },
  header: {
    padding: '16px',
    background: 'rgba(15, 23, 42, 0.8)',
    borderBottom: '1px solid var(--border-subtle)',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center'
  },
  closeBtn: {
    background: 'none',
    border: 'none',
    color: 'var(--text-muted)',
    cursor: 'pointer'
  },
  toolbar: {
    padding: '8px 16px',
    borderBottom: '1px solid var(--border-subtle)',
    background: 'rgba(30, 41, 59, 0.4)',
  },
  toggleLabel: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    fontSize: '12px',
    cursor: 'pointer',
    fontWeight: 500
  },
  checkbox: {
    cursor: 'pointer'
  },
  messageArea: {
    flex: 1,
    padding: '16px',
    overflowY: 'auto',
    display: 'flex',
    flexDirection: 'column',
    gap: '12px'
  },
  messageWrapper: {
    display: 'flex',
    gap: '8px',
    alignItems: 'flex-start'
  },
  messageBubble: {
    padding: '10px 14px',
    borderRadius: '12px',
    fontSize: '13px',
    lineHeight: '1.5',
    maxWidth: '85%',
    wordBreak: 'break-word'
  },
  loadingBubble: {
    padding: '10px 14px',
    borderRadius: '12px',
    background: 'rgba(30, 41, 59, 0.6)',
    border: '1px solid var(--border-subtle)',
    display: 'flex',
    alignItems: 'center',
    gap: '8px'
  },
  inputArea: {
    padding: '12px',
    borderTop: '1px solid var(--border-subtle)',
    background: 'rgba(15, 23, 42, 0.8)',
    display: 'flex',
    gap: '8px'
  },
  input: {
    flex: 1,
    background: 'var(--bg-card)',
    border: '1px solid var(--border-subtle)',
    padding: '10px 14px',
    borderRadius: '8px',
    color: 'var(--text-primary)',
    outline: 'none',
    fontSize: '14px'
  },
  sendBtn: {
    background: 'var(--cyan)',
    color: '#fff',
    border: 'none',
    borderRadius: '8px',
    padding: '0 16px',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center'
  }
};
