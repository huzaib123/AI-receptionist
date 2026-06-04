import React, { useState, useEffect, useRef } from 'react';
import {
  MessageSquare, Calendar, Users, Send, X, Clock,
  ExternalLink, Lock, CheckCircle, ArrowUpRight,
  TrendingUp, LogOut, RefreshCw, Zap, Database,
  Activity, ChevronRight, Inbox
} from 'lucide-react';

const API_BASE = '';

export default function App() {
  const [currentView, setCurrentView] = useState('home');
  const [adminKey, setAdminKey] = useState(localStorage.getItem('admin_api_key') || '');
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [authError, setAuthError] = useState('');

  const [stats, setStats] = useState(null);
  const [bookings, setBookings] = useState([]);
  const [loadingDashboard, setLoadingDashboard] = useState(false);
  const [dashboardError, setDashboardError] = useState('');

  const [chatOpen, setChatOpen] = useState(false);
  const [sessionId, setSessionId] = useState('');
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [chatError, setChatError] = useState('');

  const chatEndRef = useRef(null);

  useEffect(() => {
    let sid = localStorage.getItem('chat_session_id');
    if (!sid) {
      sid = 'sess_' + Math.random().toString(36).substring(2, 15);
      localStorage.setItem('chat_session_id', sid);
    }
    setSessionId(sid);

    const history = localStorage.getItem(`chat_history_${sid}`);
    if (history) {
      setChatMessages(JSON.parse(history));
    } else {
      const greeting = [{
        id: 1, sender: 'bot',
        text: "Hi there — I'm your AI receptionist. I can help you book appointments, check availability, or answer questions about our services. What can I do for you?",
        timestamp: new Date().toISOString()
      }];
      setChatMessages(greeting);
      localStorage.setItem(`chat_history_${sid}`, JSON.stringify(greeting));
    }
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages, isTyping, chatOpen]);

  useEffect(() => {
    if (adminKey && currentView === 'admin') handleAdminLogin(null, adminKey);
  }, [currentView]);

  const handleAdminLogin = async (e, keyOverride = null) => {
    if (e) e.preventDefault();
    const key = keyOverride || adminKey;
    if (!key) { setAuthError('API key is required'); return; }

    setLoadingDashboard(true);
    setAuthError('');
    setDashboardError('');

    try {
      const res = await fetch(`${API_BASE}/admin/stats`, {
        headers: { 'X-Admin-API-Key': key }
      });
      if (res.status === 401 || res.status === 403) {
        setIsAuthenticated(false);
        setAuthError('Invalid API key');
        setLoadingDashboard(false);
        return;
      }
      if (!res.ok) throw new Error(`Status ${res.status}`);

      setStats(await res.json());
      localStorage.setItem('admin_api_key', key);
      setIsAuthenticated(true);

      const bRes = await fetch(`${API_BASE}/admin/bookings/today`, {
        headers: { 'X-Admin-API-Key': key }
      });
      if (bRes.ok) setBookings(await bRes.json());
    } catch (err) {
      console.error(err);
      setDashboardError('Unable to reach backend. Ensure the server is running.');
    } finally {
      setLoadingDashboard(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('admin_api_key');
    setAdminKey('');
    setIsAuthenticated(false);
    setStats(null);
    setBookings([]);
  };

  const handleSend = async (e) => {
    e.preventDefault();
    if (!chatInput.trim()) return;

    const text = chatInput.trim();
    setChatInput('');
    setChatError('');

    const userMsg = { id: Date.now(), sender: 'user', text, timestamp: new Date().toISOString() };
    const updated = [...chatMessages, userMsg];
    setChatMessages(updated);
    localStorage.setItem(`chat_history_${sessionId}`, JSON.stringify(updated));
    setIsTyping(true);

    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, session_id: sessionId })
      });

      if (res.status === 429) {
        setChatError('Rate limit reached. Please wait a moment.');
        setIsTyping(false);
        return;
      }
      if (!res.ok) throw new Error('Server error');

      const data = await res.json();
      const botMsg = {
        id: Date.now() + 1, sender: 'bot', text: data.reply,
        tools: data.tools_called || [], timestamp: new Date().toISOString()
      };
      const final = [...updated, botMsg];
      setChatMessages(final);
      localStorage.setItem(`chat_history_${sessionId}`, JSON.stringify(final));
    } catch (err) {
      console.error(err);
      setChatError('Something went wrong. Please try again.');
    } finally {
      setIsTyping(false);
    }
  };

  const clearChat = () => {
    localStorage.removeItem(`chat_history_${sessionId}`);
    const greeting = [{
      id: 1, sender: 'bot',
      text: "Hi there — I'm your AI receptionist. How can I help you today?",
      timestamp: new Date().toISOString()
    }];
    setChatMessages(greeting);
    localStorage.setItem(`chat_history_${sessionId}`, JSON.stringify(greeting));
    setChatError('');
  };

  const fmtTime = (iso) => {
    try { return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }); }
    catch { return iso; }
  };

  const statusClass = (s) => {
    if (s === 'confirmed') return 'status-confirmed';
    if (s === 'no-show') return 'status-no-show';
    if (s === 'cancelled') return 'status-cancelled';
    return 'status-pending';
  };

  return (
    <div className="app-wrapper">
      {/* ── Header ──────────────────────────────────────────────────── */}
      <header className="app-header">
        <a className="logo" onClick={() => setCurrentView('home')}>
          <Zap size={20} />
          <span>Poitola</span>
        </a>
        <nav className="nav-links">
          {currentView === 'admin' ? (
            <button className="btn btn-ghost" onClick={() => setCurrentView('home')}>
              ← Back to Home
            </button>
          ) : (
            <button className="btn btn-secondary" onClick={() => setCurrentView('admin')}>
              Admin
              <ChevronRight size={14} />
            </button>
          )}
        </nav>
      </header>

      {/* ── Landing Page ────────────────────────────────────────────── */}
      {currentView === 'home' && (
        <main className="animate-fade-in">
          <section className="hero-section">
            <span className="hero-badge">
              <span className="hero-badge-dot" />
              Now available
            </span>
            <h1>
              The AI receptionist<br />
              for <em>modern</em> clinics
            </h1>
            <p className="hero-subtitle">
              Automate appointment booking, answer patient inquiries, and reduce
              no-shows with an intelligent agent that connects to your calendar,
              database, and ML pipeline.
            </p>
            <div className="hero-actions">
              <button className="btn btn-primary" onClick={() => setChatOpen(true)}>
                <MessageSquare size={16} />
                Try the demo
              </button>
              <button className="btn btn-secondary" onClick={() => setCurrentView('admin')}>
                View dashboard
                <ArrowUpRight size={14} />
              </button>
            </div>
          </section>

          <section className="features-section">
            <p className="features-section-title">What it does</p>
            <div className="features-grid">
              <div className="feature-card">
                <div className="feature-icon"><Calendar size={20} /></div>
                <h3>Calendar sync</h3>
                <p>Reads real-time availability from Google Calendar, calculates buffers, and creates confirmed bookings instantly.</p>
              </div>
              <div className="feature-card">
                <div className="feature-icon"><Database size={20} /></div>
                <h3>Patient CRM</h3>
                <p>Stores customer profiles, appointment history, and contact details in a secure PostgreSQL database.</p>
              </div>
              <div className="feature-card">
                <div className="feature-icon"><Activity size={20} /></div>
                <h3>No-show prediction</h3>
                <p>A trained ML model scores every booking for no-show risk and triggers proactive reminders for high-risk appointments.</p>
              </div>
            </div>
          </section>

          <section className="how-section">
            <div className="how-section-header">
              <h2>How it works</h2>
              <p>Three steps from inquiry to confirmed booking.</p>
            </div>
            <div className="how-steps">
              <div className="how-step">
                <div className="step-number">1</div>
                <div className="step-content">
                  <h4>Patient sends a message</h4>
                  <p>Through the chat widget, a patient asks about availability, pricing, or requests an appointment in natural language.</p>
                </div>
              </div>
              <div className="how-step">
                <div className="step-number">2</div>
                <div className="step-content">
                  <h4>Agent coordinates tools</h4>
                  <p>The LangChain agent queries the calendar for open slots, looks up FAQ answers, and checks the patient's booking history — all automatically.</p>
                </div>
              </div>
              <div className="how-step">
                <div className="step-number">3</div>
                <div className="step-content">
                  <h4>Booking confirmed &amp; logged</h4>
                  <p>A Google Calendar event is created, the booking is saved to the database, and the ML model flags any high-risk appointments for follow-up.</p>
                </div>
              </div>
            </div>
          </section>

          <footer className="app-footer">
            Built with FastAPI · LangChain · React
          </footer>
        </main>
      )}

      {/* ── Admin Dashboard ─────────────────────────────────────────── */}
      {currentView === 'admin' && (
        <main className="animate-fade-in">
          {!isAuthenticated ? (
            <div className="admin-auth-container">
              <div className="admin-auth-card">
                <div className="admin-auth-icon"><Lock size={22} /></div>
                <h2>Admin access</h2>
                <p className="auth-desc">Enter your API key to view bookings and system metrics.</p>
                <form onSubmit={handleAdminLogin}>
                  <div className="form-group">
                    <label htmlFor="apiKey">API Key</label>
                    <input
                      type="password" id="apiKey" className="form-input"
                      placeholder="X-Admin-API-Key"
                      value={adminKey} onChange={(e) => setAdminKey(e.target.value)}
                    />
                  </div>
                  {authError && <div className="chat-error-banner" style={{ marginBottom: '1rem' }}>{authError}</div>}
                  <button type="submit" className="btn btn-primary" style={{ width: '100%', justifyContent: 'center' }} disabled={loadingDashboard}>
                    {loadingDashboard ? 'Authenticating…' : 'Sign in'}
                  </button>
                </form>
              </div>
            </div>
          ) : (
            <div className="dashboard-container">
              <div className="dashboard-header">
                <div>
                  <h1>Dashboard</h1>
                  <p>Booking operations and system health at a glance.</p>
                </div>
                <div className="dashboard-actions">
                  <button className="btn btn-secondary" onClick={(e) => handleAdminLogin(e)} disabled={loadingDashboard}>
                    <RefreshCw size={14} className={loadingDashboard ? 'animate-spin' : ''} />
                    Refresh
                  </button>
                  <button className="btn btn-danger" onClick={handleLogout}>
                    <LogOut size={14} />
                    Sign out
                  </button>
                </div>
              </div>

              {dashboardError && <div className="chat-error-banner" style={{ marginBottom: '1.5rem' }}>{dashboardError}</div>}

              <div className="stats-grid">
                <div className="stat-card">
                  <div className="stat-card-label">Total Bookings</div>
                  <div className="stat-card-value">{stats?.total_bookings ?? 0}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-card-label">Customers</div>
                  <div className="stat-card-value">{stats?.total_customers ?? 0}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-card-label">Avg. Latency</div>
                  <div className="stat-card-value">
                    {stats?.avg_model_call_latency_ms ? `${Math.round(stats.avg_model_call_latency_ms)}ms` : '—'}
                  </div>
                </div>
                <div className="stat-card">
                  <div className="stat-card-label">Errors</div>
                  <div className={`stat-card-value ${(stats?.tool_error_count ?? 0) > 0 ? 'danger' : ''}`}>
                    {stats?.tool_error_count ?? 0}
                  </div>
                </div>
              </div>

              <div className="dashboard-grid">
                <div className="panel">
                  <div className="panel-header">
                    <Clock size={16} />
                    <h3>Today's bookings</h3>
                  </div>
                  <div className="panel-body">
                    {bookings.length === 0 ? (
                      <div className="bookings-empty">
                        <Inbox size={32} />
                        No bookings scheduled for today.
                      </div>
                    ) : (
                      bookings.map((b) => (
                        <div key={b.id} className="booking-item">
                          <div className="booking-customer">
                            <h4>{b.customer?.name}</h4>
                            <div className="booking-meta">
                              <span>{b.customer?.phone || 'No phone'}</span>
                              <span className="sep">·</span>
                              <span className="service-tag">{b.service}</span>
                            </div>
                          </div>
                          <div className="booking-right">
                            <span className="booking-time">{fmtTime(b.datetime)}</span>
                            <span className={`status-badge ${statusClass(b.status)}`}>{b.status}</span>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>

                <div className="panel">
                  <div className="panel-header">
                    <TrendingUp size={16} />
                    <h3>Breakdown</h3>
                  </div>
                  <div className="panel-body">
                    <div className="breakdown-list">
                      <div className="breakdown-section-title">By service</div>
                      {stats?.service_breakdown && Object.keys(stats.service_breakdown).length > 0 ? (
                        Object.entries(stats.service_breakdown).map(([svc, count]) => (
                          <div key={svc} className="breakdown-row">
                            <span className="breakdown-label">{svc}</span>
                            <span className="breakdown-value">{count}</span>
                          </div>
                        ))
                      ) : (
                        <div className="breakdown-row">
                          <span className="breakdown-label" style={{ color: 'var(--text-tertiary)' }}>No data yet</span>
                        </div>
                      )}

                      <div className="breakdown-section-title" style={{ marginTop: '1rem' }}>By status</div>
                      <div className="breakdown-row">
                        <span className="breakdown-label">Confirmed</span>
                        <span className="breakdown-value success">{stats?.confirmed_count ?? 0}</span>
                      </div>
                      <div className="breakdown-row">
                        <span className="breakdown-label">No-shows</span>
                        <span className="breakdown-value danger">{stats?.no_show_count ?? 0}</span>
                      </div>
                      <div className="breakdown-row">
                        <span className="breakdown-label">Cancelled</span>
                        <span className="breakdown-value muted">{stats?.cancelled_count ?? 0}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </main>
      )}

      {/* ── Chat Widget ─────────────────────────────────────────────── */}
      {!chatOpen ? (
        <button className="chat-fab" onClick={() => setChatOpen(true)}>
          <MessageSquare size={22} />
        </button>
      ) : (
        <div className="chat-drawer">
          <div className="chat-header">
            <div className="chat-header-info">
              <div className="chat-avatar">✦</div>
              <div className="chat-header-text">
                <h3>Poitola</h3>
                <div className="chat-status">
                  <span className="status-dot" />
                  Online
                </div>
              </div>
            </div>
            <button className="chat-close-btn" onClick={() => setChatOpen(false)}>
              <X size={18} />
            </button>
          </div>

          <div className="chat-body">
            {chatMessages.map((msg) => (
              <div key={msg.id} className={`chat-bubble chat-bubble-${msg.sender}`}>
                <p>{msg.text}</p>
                {msg.tools && msg.tools.length > 0 && (
                  <div className="tool-tags">
                    {msg.tools.map((t, i) => (
                      <span key={`${t}-${i}`} className="tool-tag">{t}</span>
                    ))}
                  </div>
                )}
              </div>
            ))}
            {isTyping && (
              <div className="typing-indicator">
                <div className="typing-dot" />
                <div className="typing-dot" />
                <div className="typing-dot" />
              </div>
            )}
            <div ref={chatEndRef} />
          </div>

          {chatError && <div className="chat-error-banner" style={{ margin: '0 0.75rem 0.5rem' }}>{chatError}</div>}

          <div className="chat-footer">
            <form onSubmit={handleSend} className="chat-input-wrapper">
              <input
                type="text" className="chat-input"
                placeholder="Message Poitola…"
                value={chatInput} onChange={(e) => setChatInput(e.target.value)}
                disabled={isTyping}
              />
              <button type="submit" className="chat-send-btn" disabled={isTyping || !chatInput.trim()}>
                <Send size={14} />
              </button>
            </form>
            <button onClick={clearChat} className="chat-clear-btn">Clear conversation</button>
          </div>
        </div>
      )}
    </div>
  );
}
