// Khung chat voi Superdoc — chi 1 doan chat, khong co phien khac, khong chon model, khong gui anh
// (dung pham vi dac ta yeu cau).
//
// Lich su hien thi duoc giu trong bien module CHU KHONG dung trong DOM: moi lan backend gui
// state_update, state_router xoa sach root roi render lai tu dau, neu doc lich su tu DOM thi
// moi lan nhu vay se mat het tin nhan. Lich su gan voi session_id — doi phien la xoa sach, dung
// yeu cau "xoa toan bo lich su chat" khi ket thuc.
let historySessionId = null;
let history = [];
let pendingError = null;

export function resetHistory(sessionId) {
  historySessionId = sessionId;
  history = [];
  pendingError = null;
}

export function appendTurn(sessionId, role, text) {
  if (sessionId !== historySessionId) return; // tin nhan den muon cua phien da dong
  history.push({ role, text });
}

export function setError(sessionId, text) {
  if (sessionId !== historySessionId) return;
  pendingError = text;
}

export function render(root, msg, client) {
  const data = msg.data || {};
  const sessionId = data.session_id || null;
  if (sessionId !== historySessionId) resetHistory(sessionId);

  const wrap = document.createElement("div");
  Object.assign(wrap.style, {
    width: "100vw",
    height: "100vh",
    boxSizing: "border-box",
    display: "flex",
    flexDirection: "column",
    background: "#10151c",
    color: "#f2f5f8",
    fontFamily: "Segoe UI, sans-serif",
  });

  wrap.appendChild(buildHeader(msg, client));

  const log = document.createElement("div");
  Object.assign(log.style, {
    flex: "1",
    overflowY: "auto",
    padding: "2vh 4vw",
    display: "flex",
    flexDirection: "column",
    gap: "1.4vh",
  });

  if (history.length === 0) {
    const greeting = bubble(
      "assistant",
      "Xin chào, tôi là Superdoc. Bạn cần hỏi gì về bệnh viện? Ví dụ: giờ khám, quy trình đăng ký, vị trí các khoa phòng."
    );
    log.appendChild(greeting);
  }
  for (const turn of history) log.appendChild(bubble(turn.role, turn.text));

  if (data.waiting_for_ai) log.appendChild(bubble("assistant", "Superdoc đang trả lời…", true));
  if (pendingError) log.appendChild(errorBanner(pendingError));

  wrap.appendChild(log);
  wrap.appendChild(buildComposer(msg, client, sessionId, data.waiting_for_ai));
  root.appendChild(wrap);

  // Sau khi da gan vao DOM moi cuon duoc xuong day.
  requestAnimationFrame(() => {
    log.scrollTop = log.scrollHeight;
  });
}

function buildHeader(msg, client) {
  const header = document.createElement("div");
  Object.assign(header.style, {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "2vh 4vw",
    borderBottom: "1px solid #23303e",
  });

  const title = document.createElement("div");
  title.textContent = "Superdoc — Trợ lý bệnh viện";
  Object.assign(title.style, { fontSize: "min(2.2vw, 3vh)", fontWeight: "600" });
  header.appendChild(title);

  const actions = document.createElement("div");
  Object.assign(actions.style, { display: "flex", gap: "1rem" });

  // Chi Man 2 moi co the doi sang che do Trinh chieu (Man 4 chuyen dung cho chat).
  if (msg.screen_id === 2) {
    actions.appendChild(
      smallButton("Xem Thông tin bệnh viện", "#3a4757", (e) => {
        e.stopPropagation();
        client.touch("menu_option_info");
      })
    );
  }
  actions.appendChild(
    smallButton("Kết thúc đoạn chat", "#c0392b", (e) => {
      e.stopPropagation();
      client.touch("exit_chat");
    })
  );

  header.appendChild(actions);
  return header;
}

function buildComposer(msg, client, sessionId, waiting) {
  const composer = document.createElement("form");
  Object.assign(composer.style, {
    display: "flex",
    gap: "1rem",
    padding: "2vh 4vw",
    borderTop: "1px solid #23303e",
  });

  const input = document.createElement("input");
  input.type = "text";
  input.placeholder = waiting ? "Đang chờ Superdoc trả lời…" : "Nhập câu hỏi của bạn…";
  input.autocomplete = "off";
  // Khoa o nhap trong luc cho AI: gui them 1 cau khi cau truoc chua co tra loi se tao 2 luot
  // "user" lien tiep trong lich su, Gemini that tu choi payload do. Backend cung chan lai.
  input.disabled = !sessionId || Boolean(waiting);
  Object.assign(input.style, {
    flex: "1",
    fontSize: "min(1.8vw, 2.6vh)",
    padding: "1.2rem 1.5rem",
    borderRadius: "12px",
    border: "1px solid #2c3a4a",
    background: "#182029",
    color: "#f2f5f8",
    outline: "none",
  });

  const sendBtn = smallButton("Gửi", "#2a63ff", null);
  sendBtn.type = "submit";
  sendBtn.style.fontSize = "min(1.8vw, 2.6vh)";
  sendBtn.style.padding = "1.2rem 2.5rem";

  composer.appendChild(input);
  composer.appendChild(sendBtn);

  composer.onsubmit = (e) => {
    e.preventDefault();
    e.stopPropagation();
    const text = input.value.trim();
    if (!text || !sessionId) return;
    appendTurn(sessionId, "user", text);
    pendingError = null;
    input.value = "";
    client.send({ type: "chat_message", screen_id: msg.screen_id, session_id: sessionId, text });
  };
  // Cham vao o nhap khong duoc kich hoat handler generic_wake toan trang.
  composer.onclick = (e) => e.stopPropagation();

  // Man hinh cam ung khong co ban phim vat ly -> tu bat ban phim ao bang cach focus.
  requestAnimationFrame(() => {
    if (!input.disabled) input.focus();
  });

  return composer;
}

function bubble(role, text, muted) {
  const row = document.createElement("div");
  Object.assign(row.style, {
    display: "flex",
    justifyContent: role === "user" ? "flex-end" : "flex-start",
  });

  const box = document.createElement("div");
  box.textContent = text;
  Object.assign(box.style, {
    maxWidth: "70%",
    fontSize: "min(1.7vw, 2.4vh)",
    lineHeight: "1.55",
    padding: "1.1rem 1.4rem",
    borderRadius: "16px",
    whiteSpace: "pre-wrap",
    background: role === "user" ? "#2a63ff" : "#1c2733",
    opacity: muted ? "0.6" : "1",
    fontStyle: muted ? "italic" : "normal",
  });

  row.appendChild(box);
  return row;
}

function errorBanner(text) {
  const box = document.createElement("div");
  box.textContent = text;
  Object.assign(box.style, {
    fontSize: "min(1.6vw, 2.2vh)",
    padding: "1rem 1.4rem",
    borderRadius: "12px",
    background: "#3a1c1c",
    border: "1px solid #7a2f2f",
    color: "#ffd7d7",
  });
  return box;
}

function smallButton(label, color, onClick) {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.textContent = label;
  Object.assign(btn.style, {
    fontSize: "1.2rem",
    padding: "1rem 1.8rem",
    borderRadius: "12px",
    border: "none",
    background: color,
    color: "#fff",
    cursor: "pointer",
  });
  if (onClick) btn.onclick = onClick;
  return btn;
}
