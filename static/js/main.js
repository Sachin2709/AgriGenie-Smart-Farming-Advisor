// =====================================================
//  AgriGenie AI – Main JavaScript
// =====================================================

/* ── Dark Mode ─────────────────────────────────────── */
(function () {
  const saved = localStorage.getItem("ag-theme") || "light";
  document.documentElement.setAttribute("data-theme", saved);
})();

function toggleDarkMode() {
  const html  = document.documentElement;
  const theme = html.getAttribute("data-theme") === "dark" ? "light" : "dark";
  html.setAttribute("data-theme", theme);
  localStorage.setItem("ag-theme", theme);
}

/* ── Sidebar Toggle ────────────────────────────────── */
function toggleSidebar() {
  const sidebar = document.querySelector(".ag-sidebar");
  const main    = document.querySelector(".ag-main");
  if (!sidebar) return;
  const isMobile = window.innerWidth <= 1024;
  if (isMobile) {
    sidebar.classList.toggle("mobile-open");
  } else {
    sidebar.classList.toggle("collapsed");
    main && main.classList.toggle("sidebar-collapsed");
  }
}

/* ── Active Nav Link ───────────────────────────────── */
document.addEventListener("DOMContentLoaded", function () {
  const path  = window.location.pathname;
  const links = document.querySelectorAll(".ag-nav-link");
  links.forEach(link => {
    const href = link.getAttribute("href");
    if (href && (href === path || (href !== "/" && path.startsWith(href)))) {
      link.classList.add("active");
    }
  });
});

/* ── Toast Notifications ───────────────────────────── */
function showToast(message, type = "info", duration = 3500) {
  let container = document.querySelector(".ag-toast-container");
  if (!container) {
    container = document.createElement("div");
    container.className = "ag-toast-container";
    document.body.appendChild(container);
  }
  const icons = { success: "✅", error: "❌", info: "ℹ️", warning: "⚠️" };
  const toast = document.createElement("div");
  toast.className = `ag-toast ${type}`;
  toast.innerHTML = `<span style="font-size:1.1rem">${icons[type] || "📢"}</span>
                     <span style="flex:1">${message}</span>
                     <button onclick="this.parentElement.remove()"
                       style="background:none;border:none;cursor:pointer;opacity:.5;font-size:1rem;">✕</button>`;
  container.appendChild(toast);
  setTimeout(() => toast.style.opacity = "0", duration);
  setTimeout(() => toast.remove(), duration + 400);
}

/* ── Format AI Response (Markdown-lite) ────────────── */
function formatAIResponse(text) {
  if (!text) return "";
  let html = text
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/^### (.+)$/gm, '<h3 style="color:var(--ag-primary);margin:12px 0 4px;font-size:.95rem">$1</h3>')
    .replace(/^## (.+)$/gm,  '<h2 style="color:var(--ag-primary);margin:14px 0 6px;font-size:1.05rem">$1</h2>')
    .replace(/^# (.+)$/gm,   '<h1 style="color:var(--ag-primary);margin:16px 0 8px;font-size:1.15rem">$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g,     '<em>$1</em>')
    .replace(/`(.+?)`/g,       '<code style="background:rgba(34,134,58,.1);padding:2px 6px;border-radius:4px">$1</code>')
    .replace(/^[-*] (.+)$/gm,  '<li style="margin-bottom:3px">$1</li>')
    .replace(/(<li.*<\/li>\n?)+/g, '<ul style="padding-left:18px;margin:6px 0">$&</ul>')
    .replace(/^\d+\. (.+)$/gm, '<li style="margin-bottom:3px">$1</li>')
    .replace(/\n\n/g, '<br><br>')
    .replace(/\n/g, '<br>');
  return html;
}

/* ── Copy Text to Clipboard ─────────────────────────── */
function copyToClipboard(text, btn) {
  navigator.clipboard.writeText(text).then(() => {
    if (btn) {
      const orig = btn.innerHTML;
      btn.innerHTML = "✅ Copied!";
      setTimeout(() => btn.innerHTML = orig, 2000);
    }
    showToast("Copied to clipboard", "success");
  }).catch(() => showToast("Copy failed", "error"));
}

/* ── Download Report ────────────────────────────────── */
async function downloadReport(reportType, adviceText) {
  const btn = event.currentTarget;
  const orig = btn.innerHTML;
  btn.innerHTML = "⏳ Generating PDF…";
  btn.disabled = true;
  try {
    const resp = await fetch("/api/download-report", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCsrfToken()
      },
      body: JSON.stringify({ report_type: reportType, advice: adviceText })
    });
    if (!resp.ok) throw new Error("Report generation failed");
    const blob = await resp.blob();
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement("a");
    a.href     = url;
    a.download = `agrigenie_${reportType.toLowerCase().replace(/\s+/g, "_")}.pdf`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showToast("Report downloaded!", "success");
  } catch (err) {
    showToast("Failed to generate report: " + err.message, "error");
  } finally {
    btn.innerHTML = orig;
    btn.disabled = false;
  }
}

/* ── CSRF Token ─────────────────────────────────────── */
function getCsrfToken() {
  const meta = document.querySelector('meta[name="csrf-token"]');
  if (meta) return meta.content;
  const input = document.querySelector('input[name="csrf_token"]');
  return input ? input.value : "";
}

/* ── Generic AI Query ───────────────────────────────── */
async function queryAI(endpoint, payload, resultContainerId, loadingText = "🌱 Analyzing…") {
  const container = document.getElementById(resultContainerId);
  if (!container) return null;

  container.innerHTML = `<div class="text-center py-4">
    <div class="ag-spinner"><span></span><span></span><span></span></div>
    <p class="mt-3 text-muted small">${loadingText}</p>
  </div>`;
  container.style.display = "block";

  try {
    const resp = await fetch(endpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCsrfToken()
      },
      body: JSON.stringify(payload)
    });

    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || "Request failed");

    const advice = data.advice || data.response || "";
    container.innerHTML = `
      <div class="d-flex justify-content-between align-items-start mb-3">
        <h6 class="text-success mb-0">🤖 AgriGenie Advice</h6>
        <div class="d-flex gap-2">
          <button class="btn btn-sm btn-outline-secondary"
            onclick="copyToClipboard(document.getElementById('${resultContainerId}').querySelector('.ai-content').innerText, this)">
            📋 Copy
          </button>
          <button class="btn btn-sm btn-outline-success"
            onclick="downloadReport('${endpoint.split('/').pop().replace(/-/g,' ').replace(/\b\w/g,c=>c.toUpperCase())}', document.getElementById('${resultContainerId}').querySelector('.ai-content').innerText)">
            📥 PDF
          </button>
        </div>
      </div>
      <div class="ai-content" style="line-height:1.7">${formatAIResponse(advice)}</div>
      <hr class="my-2">
      <small class="text-muted">Powered by IBM watsonx.ai Granite | Always verify with local KVK</small>
    `;
    return data;
  } catch (err) {
    container.innerHTML = `<div class="alert alert-danger">
      <strong>Error:</strong> ${err.message || "Failed to get AI response. Check your IBM credentials."}
    </div>`;
    showToast("Failed: " + err.message, "error");
    return null;
  }
}

/* ── Chat Session ───────────────────────────────────── */
let chatSessionId = "sess_" + Date.now();

async function sendChatMessage() {
  const input   = document.getElementById("chatInput");
  const messages= document.getElementById("chatMessages");
  const sendBtn = document.getElementById("chatSendBtn");
  const topic   = document.getElementById("chatTopic")?.value || "general";

  if (!input || !messages) return;
  const text = input.value.trim();
  if (!text) return;

  // Clear input
  input.value = "";
  input.style.height = "48px";
  sendBtn.disabled = true;

  // Add user message
  appendChatMessage("user", text);

  // Add typing indicator
  const typingId = "typing_" + Date.now();
  messages.insertAdjacentHTML("beforeend", `
    <div id="${typingId}" class="ag-message assistant">
      <div class="ag-message-avatar">🌱</div>
      <div class="ag-message-bubble">
        <div class="ag-spinner"><span></span><span></span><span></span></div>
      </div>
    </div>
  `);
  messages.scrollTop = messages.scrollHeight;

  try {
    const resp = await fetch("/api/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCsrfToken()
      },
      body: JSON.stringify({
        message: text,
        topic:   topic,
        session_id: chatSessionId
      })
    });
    const data = await resp.json();
    document.getElementById(typingId)?.remove();
    if (resp.ok) {
      appendChatMessage("assistant", data.response, data.timestamp);
    } else {
      appendChatMessage("assistant",
        "⚠️ " + (data.error || "Error getting response."));
    }
  } catch (err) {
    document.getElementById(typingId)?.remove();
    appendChatMessage("assistant", "⚠️ Network error. Please try again.");
  } finally {
    sendBtn.disabled = false;
    input.focus();
  }
}

function appendChatMessage(role, content, timestamp = null) {
  const messages = document.getElementById("chatMessages");
  if (!messages) return;
  const time  = timestamp || new Date().toLocaleTimeString([], {hour:"2-digit",minute:"2-digit"});
  const isUser= role === "user";
  const html  = `
    <div class="ag-message ${role}" style="animation:fadeInUp .25s ease">
      <div class="ag-message-avatar">${isUser ? "👤" : "🌱"}</div>
      <div>
        <div class="ag-message-bubble">
          ${isUser ? content : formatAIResponse(content)}
        </div>
        <div class="ag-message-time">${time}</div>
      </div>
    </div>`;
  messages.insertAdjacentHTML("beforeend", html);
  messages.scrollTop = messages.scrollHeight;
}

/* ── Quick Prompts ─────────────────────────────────── */
function sendQuickPrompt(text) {
  const input = document.getElementById("chatInput");
  if (input) {
    input.value = text;
    sendChatMessage();
  }
}

/* ── Auto-resize textarea ─────────────────────────── */
document.addEventListener("input", function (e) {
  if (e.target.id === "chatInput") {
    e.target.style.height = "48px";
    e.target.style.height = Math.min(e.target.scrollHeight, 120) + "px";
  }
});

document.addEventListener("keydown", function (e) {
  if (e.target.id === "chatInput" && e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendChatMessage();
  }
});

/* ── Mobile overlay close ────────────────────────── */
document.addEventListener("click", function (e) {
  if (window.innerWidth <= 1024) {
    const sidebar = document.querySelector(".ag-sidebar");
    const toggle  = document.querySelector(".ag-toggle-btn");
    if (sidebar && sidebar.classList.contains("mobile-open") &&
        !sidebar.contains(e.target) && !toggle?.contains(e.target)) {
      sidebar.classList.remove("mobile-open");
    }
  }
});

/* ── Number formatting ──────────────────────────── */
function fmtPrice(n) {
  if (n >= 100000) return "₹" + (n / 100000).toFixed(1) + "L";
  if (n >= 1000)   return "₹" + (n / 1000).toFixed(1) + "K";
  return "₹" + n;
}

/* ── RAG Status Indicator ─────────────────────────── */
async function checkRAGStatus() {
  try {
    const r = await fetch("/api/rag-status");
    const d = await r.json();
    const el = document.getElementById("ragStatusDot");
    if (el) {
      el.style.background = d.ready ? "#22c55e" : "#f59e0b";
      el.title = d.ready ? "Knowledge base ready" : "Loading knowledge base…";
    }
  } catch (_) {}
}

document.addEventListener("DOMContentLoaded", checkRAGStatus);
