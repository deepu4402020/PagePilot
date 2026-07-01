import { useState, useEffect } from 'react';

export default function App() {
  const [activeTab, setActiveTab] = useState('chat');
  
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
        {activeTab === 'chat' ? <ChatTab /> : <ProfileTab />}
      </div>
    </div>
  );
}

function ChatTab() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div className="chat-messages">
        <p><strong>System:</strong> How can I help you with this page?</p>
      </div>
      <div className="chat-input-area">
        <input type="text" placeholder="Type a message..." />
        <button>Send</button>
      </div>
    </div>
  );
}

function ProfileTab() {
  const [profile, setProfile] = useState('');

  // Load profile from Chrome storage
  useEffect(() => {
    if (chrome?.storage?.local) {
      chrome.storage.local.get(['resumeProfile'], (result) => {
        if (result.resumeProfile) setProfile(result.resumeProfile);
      });
    }
  }, []);

  const saveProfile = () => {
    if (chrome?.storage?.local) {
      chrome.storage.local.set({ resumeProfile: profile }, () => {
        alert('Profile saved!');
      });
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
