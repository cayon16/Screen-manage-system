import { fullscreenContainer, bigButton } from "./_common.js";

// Man 2 — menu dieu khien chinh (Luong A/B/C).
export function render(root, msg, client) {
  const wrap = fullscreenContainer("#111");
  wrap.style.gap = "2rem";

  const title = document.createElement("h1");
  title.textContent = "Xin chào, bạn muốn làm gì?";
  wrap.appendChild(title);

  const btnInfo = bigButton("Thông tin bệnh viện", "#2a63ff");
  btnInfo.onclick = (e) => {
    e.stopPropagation(); // tranh handler generic_wake o main.js gui them 1 lan sau click nay
    client.touch("menu_option_info");
  };
  wrap.appendChild(btnInfo);

  const btnChat = bigButton("Chat với Superdoc", "#22a35e");
  btnChat.onclick = (e) => {
    e.stopPropagation();
    client.touch("menu_option_chat");
  };
  wrap.appendChild(btnChat);

  root.appendChild(wrap);
}
