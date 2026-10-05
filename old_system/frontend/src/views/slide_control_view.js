// Man 2 o che do Trinh chieu — bang dieu khien 6 nut (3 man thu dong x 2 slide).
// Bam 1 nut = ghim slide do len dung man phu trach no; man 2 khong tu trinh chieu gi.
export function render(root, msg, client) {
  const data = msg.data || {};
  const buttons = data.buttons || [];
  const current = data.current || {};

  const wrap = document.createElement("div");
  Object.assign(wrap.style, {
    width: "100vw",
    height: "100vh",
    boxSizing: "border-box",
    padding: "4vh 4vw",
    display: "flex",
    flexDirection: "column",
    background: "#0e1621",
    color: "#fff",
    fontFamily: "Segoe UI, sans-serif",
  });

  const title = document.createElement("h1");
  title.textContent = "Thông tin bệnh viện";
  title.style.margin = "0";
  title.style.fontSize = "min(4vw, 5vh)";
  wrap.appendChild(title);

  const hint = document.createElement("div");
  hint.textContent = "Chạm vào nội dung bạn muốn xem — nội dung sẽ hiện lên màn hình tương ứng.";
  Object.assign(hint.style, { opacity: "0.7", margin: ".8rem 0 2.5rem", fontSize: "1.2rem" });
  wrap.appendChild(hint);

  // Nhom nut theo man phu trach, de nguoi dung hieu ngay nut nao dieu khien man nao.
  const byScreen = new Map();
  for (const b of buttons) {
    if (!byScreen.has(b.screen_id)) byScreen.set(b.screen_id, []);
    byScreen.get(b.screen_id).push(b);
  }

  const grid = document.createElement("div");
  Object.assign(grid.style, {
    flex: "1",
    display: "grid",
    gridTemplateColumns: `repeat(${byScreen.size || 1}, 1fr)`,
    gap: "2vw",
  });

  for (const [screenId, group] of byScreen) {
    const column = document.createElement("div");
    Object.assign(column.style, { display: "flex", flexDirection: "column", gap: "1.5vh" });

    const label = document.createElement("div");
    label.textContent = `Màn ${screenId}`;
    Object.assign(label.style, {
      fontSize: "1.1rem",
      opacity: "0.55",
      textTransform: "uppercase",
      letterSpacing: ".08em",
    });
    column.appendChild(label);

    for (const b of group) {
      const isActive = current[String(screenId)] === b.slide_id;
      const btn = document.createElement("button");
      btn.textContent = b.title;
      Object.assign(btn.style, {
        flex: "1",
        fontSize: "min(1.8vw, 2.6vh)",
        padding: "1.5rem 1rem",
        borderRadius: "14px",
        border: isActive ? "3px solid #6ec1ff" : "3px solid transparent",
        background: isActive ? "#1d4b7a" : "#1b2735",
        color: "#fff",
        cursor: "pointer",
        textAlign: "left",
      });
      btn.onclick = (e) => {
        e.stopPropagation(); // chan handler generic_wake o main.js
        client.send({ type: "select_slide", screen_id: msg.screen_id, slide_id: b.slide_id });
      };
      column.appendChild(btn);
    }

    grid.appendChild(column);
  }
  wrap.appendChild(grid);

  const footer = document.createElement("div");
  Object.assign(footer.style, { display: "flex", gap: "1.5rem", marginTop: "3vh" });

  const chatBtn = document.createElement("button");
  chatBtn.textContent = "Chat với Superdoc";
  Object.assign(chatBtn.style, {
    fontSize: "1.5rem",
    padding: "1.2rem 2.4rem",
    borderRadius: "14px",
    border: "none",
    background: "#22a35e",
    color: "#fff",
    cursor: "pointer",
  });
  chatBtn.onclick = (e) => {
    e.stopPropagation();
    client.touch("menu_option_chat");
  };
  footer.appendChild(chatBtn);

  const backBtn = document.createElement("button");
  backBtn.textContent = "Quay lại menu";
  Object.assign(backBtn.style, {
    fontSize: "1.5rem",
    padding: "1.2rem 2.4rem",
    borderRadius: "14px",
    border: "none",
    background: "#3a4757",
    color: "#fff",
    cursor: "pointer",
  });
  backBtn.onclick = (e) => {
    e.stopPropagation();
    client.touch("menu_back");
  };
  footer.appendChild(backBtn);

  wrap.appendChild(footer);
  root.appendChild(wrap);
}
