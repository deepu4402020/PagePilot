import { useState, useEffect, useRef } from 'react';

const BACKEND_URL = 'http://localhost:8000';

// Default empty profile structure
const EMPTY_PROFILE = {
  fullName: '',
  email: '',
  phone: '',
  location: '',
  linkedin: '',
  currentTitle: '',
  summary: '',
  experience: '',
  education: '',
  skills: ''
};

export default function App() {
  const [activeTab, setActiveTab] = useState('chat');
  const [profile, setProfile] = useState(EMPTY_PROFILE);
  const [profileLoaded, setProfileLoaded] = useState(false);

  // Load profile from Chrome storage on mount (persists forever)
  useEffect(() => {
    if (chrome?.storage?.local) {
      chrome.storage.local.get(['resumeProfile'], (result) => {
        if (result.resumeProfile) {
          setProfile({ ...EMPTY_PROFILE, ...result.resumeProfile });
        }
        setProfileLoaded(true);
      });
    } else {
      setProfileLoaded(true);
    }
  }, []);

  return (
    <div className="app-container">
      <div className="app-header">
        <div className="app-title">CareerOps Copilot</div>
        <div className="app-subtitle">AI-powered browser assistant</div>
      </div>

      <div className="tabs">
        <button
          className={`tab-button ${activeTab === 'chat' ? 'active' : ''}`}
          onClick={() => setActiveTab('chat')}
        >
          <span className="tab-icon">💬</span> Chat
        </button>
        <button
          className={`tab-button ${activeTab === 'profile' ? 'active' : ''}`}
          onClick={() => setActiveTab('profile')}
        >
          <span className="tab-icon">👤</span> Profile
        </button>
        <button
          className={`tab-button ${activeTab === 'autofill' ? 'active' : ''}`}
          onClick={() => setActiveTab('autofill')}
        >
          <span className="tab-icon">⚡</span> Auto-Fill
        </button>
      </div>

      <div className="tab-content">
        {activeTab === 'chat' && <ChatTab profile={profile} />}
        {activeTab === 'profile' && profileLoaded && (
          <ProfileTab profile={profile} setProfile={setProfile} />
        )}
        {activeTab === 'autofill' && <AutofillTab profile={profile} />}
      </div>
    </div>
  );
}


// =============================================
// CHAT TAB — Talk to the page + trigger actions
// =============================================
function ChatTab({ profile }) {
  const [messages, setMessages] = useState([
    { role: 'assistant', content: 'Hey! I can help you interact with this page. Try asking me to click buttons, fill forms, or describe what\'s on the page.' }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const sendMessage = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage = input;
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
    setIsLoading(true);

    try {
      // 1. Get active tab
      const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
      if (!tab) throw new Error('No active tab found');

      // 2. Extract page context from content.js
      let pageContext = [];
      let pageText = "";
      try {
        const response = await chrome.tabs.sendMessage(tab.id, { action: 'extract_context' });
        if (response?.context) pageContext = response.context;
        if (response?.page_text) pageText = response.page_text;
      } catch {
        // Content script not injected yet — inject it and retry
        try {
          await chrome.scripting.executeScript({
            target: { tabId: tab.id },
            files: ['content.js']
          });
          await new Promise(r => setTimeout(r, 150));
          const retryResponse = await chrome.tabs.sendMessage(tab.id, { action: 'extract_context' });
          if (retryResponse?.context) pageContext = retryResponse.context;
          if (retryResponse?.page_text) pageText = retryResponse.page_text;
        } catch {
          throw new Error('Could not read the page. Try refreshing the page first!');
        }
      }

      // 3. Send to backend
      const profileText = Object.entries(profile)
        .filter(([, v]) => v)
        .map(([k, v]) => `${k}: ${v}`)
        .join('\n');

      let res;
      try {
        res = await fetch(`${BACKEND_URL}/api/chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            message: userMessage,
            profile: profileText,
            page_context: pageContext,
            page_text: pageText,
            tab_id: tab.id,
            history: messages
              .filter(m => m.role === 'user' || m.role === 'assistant')
              .slice(-10)
              .map(m => ({ role: m.role, content: m.content }))
          })
        });
      } catch {
        throw new Error('Backend not running. Start it: cd backend && uvicorn main:app --reload');
      }

      if (!res.ok) throw new Error('Backend request failed');
      const data = await res.json();

      // 4. If there's a tool call, execute it on the page
      if (data.tool_calls && data.tool_calls.length > 0) {
        for (const tool of data.tool_calls) {
          try {
            const result = await chrome.tabs.sendMessage(tab.id, {
              action: 'execute_tool',
              tool: tool
            });
            setMessages(prev => [
              ...prev,
              { role: 'system', content: `✅ Action: ${tool.type} → ${result?.message || 'Done'}` }
            ]);
          } catch {
            setMessages(prev => [
              ...prev,
              { role: 'error', content: `Failed to execute action ${tool.type} on the page.` }
            ]);
          }
        }
        setMessages(prev => [...prev, { role: 'assistant', content: data.reply }]);
      } else {
        setMessages(prev => [...prev, { role: 'assistant', content: data.reply }]);
      }
    } catch (error) {
      setMessages(prev => [...prev, { role: 'error', content: error.message }]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="chat-container">
      <div className="chat-messages">
        {messages.map((msg, idx) => (
          <div key={idx} className={`message-bubble ${msg.role}`}>
            {(msg.role === 'assistant' || msg.role === 'user') && (
              <div className="message-sender">
                {msg.role === 'user' ? 'You' : 'Copilot'}
              </div>
            )}
            {msg.content}
          </div>
        ))}
        {isLoading && (
          <div className="typing-indicator">
            <div className="typing-dot"></div>
            <div className="typing-dot"></div>
            <div className="typing-dot"></div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="chat-input-area">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && sendMessage()}
          placeholder="Ask me anything about this page..."
          disabled={isLoading}
        />
        <button className="btn-send" onClick={sendMessage} disabled={isLoading}>
          Send
        </button>
      </div>
    </div>
  );
}


// =============================================
// PROFILE TAB — Structured form saved to Chrome storage
// =============================================
function ProfileTab({ profile, setProfile }) {
  const [saved, setSaved] = useState(false);

  const updateField = (field, value) => {
    setProfile(prev => ({ ...prev, [field]: value }));
    setSaved(false); // Mark as unsaved when editing
  };

  const saveProfile = () => {
    if (chrome?.storage?.local) {
      chrome.storage.local.set({ resumeProfile: profile }, () => {
        setSaved(true);
        setTimeout(() => setSaved(false), 3000);
      });
    }
  };

  // Each field definition: [key, label, placeholder, isTextarea]
  const fields = [
    ['fullName', 'Full Name', 'John Doe', false],
    ['email', 'Email', 'john@example.com', false],
    ['phone', 'Phone', '+1 555-123-4567', false],
    ['location', 'Location', 'San Francisco, CA', false],
    ['linkedin', 'LinkedIn URL', 'https://linkedin.com/in/johndoe', false],
    ['currentTitle', 'Current Title', 'Software Engineer', false],
    ['summary', 'Summary / Objective', 'Experienced developer with 5+ years...', true],
    ['experience', 'Work Experience', 'Company A — Role — 2020-2023\n• Did X, Y, Z', true],
    ['education', 'Education', 'B.S. Computer Science — MIT — 2020', true],
    ['skills', 'Skills', 'JavaScript, Python, React, Node.js', true],
  ];

  return (
    <div className="profile-area">
      <div className="profile-header">
        <h3>Your Resume Profile</h3>
        {saved && <span className="saved-badge">✓ Saved</span>}
      </div>

      {fields.map(([key, label, placeholder, isTextarea]) => (
        <div className="profile-field" key={key}>
          <label>{label}</label>
          {isTextarea ? (
            <textarea
              value={profile[key]}
              onChange={(e) => updateField(key, e.target.value)}
              placeholder={placeholder}
              rows={3}
            />
          ) : (
            <input
              type="text"
              value={profile[key]}
              onChange={(e) => updateField(key, e.target.value)}
              placeholder={placeholder}
            />
          )}
        </div>
      ))}

      <button className="btn-save" onClick={saveProfile}>
        💾 Save Profile
      </button>
    </div>
  );
}


// =============================================
// AUTOFILL TAB — One-click form filling
// =============================================
function AutofillTab({ profile }) {
  const [status, setStatus] = useState('idle'); // idle | loading | done | error
  const [results, setResults] = useState([]);
  const [errorMsg, setErrorMsg] = useState('');

  // Check if profile has any data
  const hasProfile = Object.values(profile).some(v => v.trim());

  const runAutofill = async () => {
    if (!hasProfile) return;

    setStatus('loading');
    setResults([]);
    setErrorMsg('');

    try {
      // 1. Get active tab
      const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
      if (!tab) throw new Error('No active tab found');

      // 2. Extract page context
      let pageContext = [];
      try {
        const response = await chrome.tabs.sendMessage(tab.id, { action: 'extract_context' });
        if (response?.context) pageContext = response.context;
      } catch {
        // Content script not injected yet — inject it and retry
        try {
          await chrome.scripting.executeScript({
            target: { tabId: tab.id },
            files: ['content.js']
          });
          await new Promise(r => setTimeout(r, 150));
          const retryResponse = await chrome.tabs.sendMessage(tab.id, { action: 'extract_context' });
          if (retryResponse?.context) pageContext = retryResponse.context;
        } catch {
          throw new Error('Could not read the page. Try refreshing first!');
        }
      }

      if (pageContext.length === 0) {
        throw new Error('No form fields found on this page.');
      }

      // 3. Send to autofill endpoint
      let res;
      try {
        res = await fetch(`${BACKEND_URL}/api/autofill`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            profile: profile,
            page_context: pageContext
          })
        });
      } catch {
        throw new Error('Backend not running. Start it: cd backend && uvicorn main:app --reload');
      }

      if (!res.ok) throw new Error('Backend autofill request failed');
      const data = await res.json();

      if (!data.tool_calls || data.tool_calls.length === 0) {
        setStatus('done');
        setResults([]);
        setErrorMsg('No matching fields found on this page.');
        return;
      }

      // 4. Execute all tool calls on the page (batch mode with delays)
      const executionResults = [];
      for (const toolCall of data.tool_calls) {
        try {
          const result = await chrome.tabs.sendMessage(tab.id, {
            action: 'execute_tool',
            tool: toolCall
          });
          executionResults.push({
            success: true,
            action: toolCall.type,
            selector: toolCall.selector,
            value: toolCall.value || '',
            message: result?.message || 'Done'
          });
        } catch {
          executionResults.push({
            success: false,
            action: toolCall.type,
            selector: toolCall.selector,
            value: toolCall.value || '',
            message: 'Failed'
          });
        }
        // Small delay between actions so the page can process
        await new Promise(r => setTimeout(r, 200));
      }

      setResults(executionResults);
      setStatus('done');
    } catch (error) {
      setStatus('error');
      setErrorMsg(error.message);
    }
  };

  return (
    <div className="autofill-area">
      <div className="autofill-icon">🚀</div>
      <h3>Auto-Fill Application</h3>
      <p>
        Click below to automatically fill out the job application form on this page 
        using your saved profile data.
      </p>

      {!hasProfile && (
        <div className="warning-card">
          <p>⚠️ No profile data saved yet. Go to the Profile tab and fill in your details first.</p>
        </div>
      )}

      <button
        className="btn-autofill"
        onClick={runAutofill}
        disabled={!hasProfile || status === 'loading'}
      >
        {status === 'loading' ? (
          <><span className="spinner"></span> Filling...</>
        ) : (
          '⚡ Auto-Fill This Page'
        )}
      </button>

      {status === 'error' && (
        <div className="autofill-status" style={{ color: 'var(--error)' }}>
          ❌ {errorMsg}
        </div>
      )}

      {status === 'done' && results.length === 0 && errorMsg && (
        <div className="autofill-status">
          {errorMsg}
        </div>
      )}

      {results.length > 0 && (
        <div className="autofill-results">
          {results.map((r, idx) => (
            <div key={idx} className="autofill-result-item">
              <span className="result-icon">{r.success ? '✅' : '❌'}</span>
              <span className="result-text">
                {r.action === 'fill_input' ? `Filled "${r.value.substring(0, 30)}"` : r.message}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
