import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import DashboardLayout from "../components/DashboardLayout";
import { apiFetch } from "../utils/api";
import { hasPermission } from "../utils/permissions";

function AiAssistantHub() {
  const role = localStorage.getItem("role") || "Staff";
  const [settings, setSettings] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [error, setError] = useState("");
  const [sending, setSending] = useState(false);
  const bottomRef = useRef(null);
  const canChat = hasPermission("ai_assistant.chat");

  const load = async () => {
    const [cfg, sess] = await Promise.all([
      apiFetch("/ai-assistant/settings"),
      apiFetch("/ai-assistant/sessions"),
    ]);
    setSettings(cfg);
    setSessions(sess.items || []);
  };

  useEffect(() => {
    load().catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const openSession = async (id) => {
    const sess = await apiFetch(`/ai-assistant/sessions/${id}`);
    setSessionId(sess.id);
    setMessages(sess.messages || []);
  };

  const send = async (text) => {
    const message = (text || input).trim();
    if (!message || !canChat) return;
    setSending(true);
    setError("");
    setInput("");
    try {
      const res = await apiFetch("/ai-assistant/chat", {
        method: "POST",
        body: JSON.stringify({ message, session_id: sessionId }),
      });
      setSessionId(res.session_id);
      setMessages((prev) => [...prev, res.user_message, res.assistant_message]);
      load().catch(() => {});
    } catch (err) {
      setError(err.message);
    } finally {
      setSending(false);
    }
  };

  const newChat = () => {
    setSessionId(null);
    setMessages([]);
    setInput("");
  };

  return (
    <DashboardLayout title="AI Assistant" roleLabel={role}>
      <div className="crm-panel crm-ai-assistant-layout">
        <div className="crm-detail-header">
          <p className="crm-muted">Search records, draft emails, and get quick CRM help</p>
          <div className="crm-inline-actions">
            {hasPermission("ai_assistant.manage_settings") && (
              <Link to="/ai-assistant/settings" className="crm-btn crm-btn-sm crm-btn-outline">Settings</Link>
            )}
            <button type="button" className="crm-btn crm-btn-sm" onClick={newChat}>New chat</button>
          </div>
        </div>

        {error && <p className="crm-error crm-mt">{error}</p>}
        {settings && !settings.is_enabled && (
          <p className="crm-muted crm-mt">AI Assistant is disabled. Enable it in settings.</p>
        )}

        <div className="crm-ai-assistant-grid crm-mt">
          <aside className="crm-ai-assistant-sidebar">
            <h3>Recent chats</h3>
            {sessions.length === 0 && <p className="crm-muted">No sessions yet</p>}
            <ul className="crm-ai-session-list">
              {sessions.map((s) => (
                <li key={s.id}>
                  <button type="button" className={sessionId === s.id ? "active" : ""} onClick={() => openSession(s.id)}>
                    <strong>{s.title}</strong>
                    <span>{s.message_count} messages</span>
                  </button>
                </li>
              ))}
            </ul>
            {settings?.suggested_prompts?.length > 0 && (
              <div className="crm-ai-prompts">
                <h3>Suggestions</h3>
                {settings.suggested_prompts.map((p) => (
                  <button key={p} type="button" className="crm-btn crm-btn-sm crm-btn-outline crm-ai-prompt-btn" onClick={() => send(p)}>
                    {p}
                  </button>
                ))}
              </div>
            )}
          </aside>

          <section className="crm-ai-chat-panel">
            <div className="crm-ai-messages">
              {messages.length === 0 && (
                <p className="crm-muted crm-ai-empty">Ask about leads, invoices, follow-ups, or request a draft email.</p>
              )}
              {messages.map((m) => (
                <div key={m.id} className={`crm-ai-message crm-ai-message-${m.role}`}>
                  <div className="crm-ai-message-bubble">
                    <pre className="crm-ai-message-text">{m.content}</pre>
                    {m.actions_json?.length > 0 && (
                      <div className="crm-ai-message-actions">
                        {m.actions_json.map((a) =>
                          a.path ? (
                            <Link key={a.path} to={a.path} className="crm-btn crm-btn-sm crm-btn-outline">{a.label}</Link>
                          ) : null
                        )}
                      </div>
                    )}
                  </div>
                </div>
              ))}
              <div ref={bottomRef} />
            </div>
            <form
              className="crm-ai-composer"
              onSubmit={(e) => {
                e.preventDefault();
                send();
              }}
            >
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder={canChat ? "Type your question…" : "You do not have chat permission"}
                disabled={!canChat || sending || !settings?.is_enabled}
              />
              <button type="submit" className="crm-btn" disabled={!canChat || sending || !settings?.is_enabled}>
                {sending ? "…" : "Send"}
              </button>
            </form>
          </section>
        </div>
      </div>
    </DashboardLayout>
  );
}

export default AiAssistantHub;
