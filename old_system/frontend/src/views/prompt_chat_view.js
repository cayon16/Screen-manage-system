import { fullscreenContainer, bigButton } from "./_common.js";

// Man 4 sau khi bi "danh thuc cap doi" (WAKE_PAIR) nhung chua duoc cham truc tiep —
// chi hien 1 nut duy nhat, dung tinh than "chi co duy nhat tinh nang chat" cua dac ta.
export function render(root, msg, client) {
  const wrap = fullscreenContainer("#111");

  const btn = bigButton("Chạm để chat với Superdoc", "#22a35e");
  btn.style.fontSize = "2.5rem";
  btn.style.padding = "2rem 4rem";
  btn.onclick = (e) => {
    e.stopPropagation();
    client.touch("chat_button");
  };
  wrap.appendChild(btn);

  root.appendChild(wrap);
}
