import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { Send, Bot, User } from "lucide-react";
import { chat, ApiError } from "../api";

function Bubble({ role, content }) {
  const isUser = role === "user";
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className={`flex gap-2 ${isUser ? "flex-row-reverse" : ""}`}
    >
      <div
        className={`w-6 h-6 rounded-full flex items-center justify-center shrink-0 ${
          isUser ? "bg-surface-hover text-ink-secondary" : "bg-severity-suspicious/15 text-severity-suspicious"
        }`}
      >
        {isUser ? <User size={12} /> : <Bot size={12} />}
      </div>
      <div
        className={`max-w-[80%] rounded-xl px-3 py-2 text-sm leading-relaxed ${
          isUser ? "bg-surface-raised text-ink-primary" : "bg-severity-suspicious/10 text-ink-primary"
        }`}
      >
        {content}
      </div>
    </motion.div>
  );
}

export default function ChatPanel() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState(null);
  const scrollRef = useRef(null);

  useEffect(() => {
    chat
      .history(30)
      .then((history) => setMessages(history.map((m) => ({ role: m.role, content: m.content }))))
      .catch(() => {
        /* No history yet, or anonymous session -- start with an empty thread. */
      });
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  async function handleSend(e) {
    e.preventDefault();
    const text = input.trim();
    if (!text || sending) return;

    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setInput("");
    setSending(true);
    setError(null);

    try {
      const res = await chat.send(text);
      setMessages((prev) => [...prev, { role: "assistant", content: res.reply }]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "The copilot is unavailable right now.");
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="panel flex flex-col h-full">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-border-subtle">
        <Bot size={16} className="text-severity-suspicious" />
        <h2 className="font-display text-sm font-semibold text-ink-primary">Security Copilot</h2>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto scrollbar-thin px-4 py-3 space-y-3">
        {messages.length === 0 && (
          <p className="text-sm text-ink-muted">
            Ask me anything — e.g. "Any critical events today?" or "Summarize current risk."
          </p>
        )}
        {messages.map((m, i) => (
          <Bubble key={i} role={m.role} content={m.content} />
        ))}
        {sending && <p className="text-xs text-ink-muted pl-8">Copilot is thinking…</p>}
      </div>

      {error && <p className="px-4 pb-1 text-xs text-severity-critical">{error}</p>}

      <form onSubmit={handleSend} className="flex items-center gap-2 p-3 border-t border-border-subtle">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask the copilot…"
          className="flex-1 bg-surface-raised border border-border rounded-lg px-3 py-2 text-sm text-ink-primary placeholder:text-ink-muted focus:outline-none focus:ring-1 focus:ring-severity-suspicious"
        />
        <button
          type="submit"
          disabled={sending || !input.trim()}
          className="w-9 h-9 flex items-center justify-center rounded-lg bg-severity-suspicious text-void hover:brightness-110 transition-all disabled:opacity-40"
        >
          <Send size={15} />
        </button>
      </form>
    </div>
  );
}