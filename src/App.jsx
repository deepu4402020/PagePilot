import { useState, useEffect } from 'react';

export default function App() {
  const [activeTab, setActiveTab] = useState('chat');
  const [profile, setProfile] = useState('');

  // Load profile from Chrome storage on mount
  useEffect(() => {
    if (chrome?.storage?.local) {
      chrome.storage.local.get(['resumeProfile'], (result) => {
        if (result.resumeProfile) setProfile(result.resumeProfile);
      });
    }
  }, []);

  return (
    <div className="app-container">
      <div className="tabs">
        <button 
          className={`tab-button ${activeTab === 'chat' ? 'active' : ''}`}
          onClick={() => setActiveTab('chat')}
        >
          Chat
        </button>
        <button 
          className={`tab-button ${activeTab === 'profile' ? 'active' : ''}`}
          onClick={() => setActiveTab('profile')}
        >
          Resume Profile
        </button>
      </div>
      
      <div className="tab-content">
        {activeTab === 'chat' ? (
          <ChatTab profile={profile} />
        ) : (
          <ProfileTab profile={profile} setProfile={setProfile} />
        )}
      </div>
    </div>
  );
}

function ChatTab({ profile }) {
  const [messages, setMessages] = useState([{ role: 'system', content: 'How can I help you with this page?' }]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const sendMessage = async () => {
    if (!input.trim()) return;

    const userMessage = input;
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
    setIsLoading(true);

    try {
      // 1. Get current active tab
      const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
      if (!tab) throw new Error("No active tab found");

      // 2. Extract page context from content.js
      let pageContext = [];
      try {
        const response = await chrome.tabs.sendMessage(tab.id, { action: 'extract_context' });
        if (response && response.context) {
          pageContext = response.context;
        }
      } catch (err) {
        throw new Error("Could not read page context. Please REFRESH the Booking.com page and try again! (Chrome needs to inject the script into the fresh page).");
      }
      
      if (pageContext.length === 0) {
        throw new Error("No interactive elements found on the page. Are you on a blank page?");
      }

      // 3. Send data to FastAPI Backend
      const backendUrl = 'http://localhost:8000/api/chat'; // Change if deployed
      const res = await fetch(backendUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: userMessage,
          profile: profile,
          page_context: pageContext
        })
      });

      if (!res.ok) throw new Error('Backend request failed');
      
      const data = await res.json();
      
      // 4. Handle tool calls or normal text response
      if (data.tool_call) {
        // e.g. { type: 'click', selector: '#submit' }
        const result = await chrome.tabs.sendMessage(tab.id, { 
          action: 'execute_tool', 
          tool: data.tool_call 
        });
        
        setMessages(prev => [
          ...prev, 
          { role: 'system', content: `Tool Executed: ${data.tool_call.type}. Result: ${result?.message || 'Done'}` },
          { role: 'assistant', content: data.reply }
        ]);
      } else {
        setMessages(prev => [...prev, { role: 'assistant', content: data.reply }]);
      }

    } catch (error) {
      console.error(error);
      setMessages(prev => [...prev, { role: 'system', content: `Error: ${error.message}` }]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <div className="chat-messages" style={{ flex: 1, overflowY: 'auto', marginBottom: '12px' }}>
        {messages.map((msg, idx) => (
          <p key={idx} style={{ 
            textAlign: msg.role === 'user' ? 'right' : 'left',
            color: msg.role === 'system' ? 'red' : 'inherit'
          }}>
            <strong>{msg.role === 'user' ? 'You' : 'Copilot'}: </strong> 
            {msg.content}
          </p>
        ))}
        {isLoading && <p><em>Thinking...</em></p>}
      </div>
      <div className="chat-input-area" style={{ flexShrink: 0 }}>
        <input 
          type="text" 
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && sendMessage()}
          placeholder="Type a message..." 
          disabled={isLoading}
        />
        <button onClick={sendMessage} disabled={isLoading}>Send</button>
      </div>
    </div>
  );
}

function ProfileTab({ profile, setProfile }) {
  const saveProfile = () => {
    if (chrome?.storage?.local) {
      chrome.storage.local.set({ resumeProfile: profile }, () => {
        alert('Profile saved!');
      });
    } else {
      alert('Chrome storage not available outside extension.');
    }
  };

  return (
    <div className="profile-area">
      <h3>Your Resume Profile</h3>
      <textarea 
        value={profile}
        onChange={(e) => setProfile(e.target.value)}
        placeholder="Paste your resume details or JSON profile here..."
      />
      <button onClick={saveProfile}>Save Profile</button>
    </div>
  );
}
