// Anh xa "view" trong state_update sang module render tuong ung.
// Moi view export 1 ham render(root, msg, client) tu ve, tu gan click handler cua no.
import { render as renderStandby } from "./views/standby_view.js";
import { render as renderMenu } from "./views/menu_view.js";
import { render as renderPromptChat } from "./views/prompt_chat_view.js";
import { render as renderSlide } from "./views/slide_view.js";
import { render as renderSlideControl } from "./views/slide_control_view.js";
import { render as renderChat } from "./views/chat_view.js";

const VIEW_RENDERERS = {
  standby: renderStandby,
  menu: renderMenu,
  prompt_chat: renderPromptChat,
  slide: renderSlide,
  slide_control: renderSlideControl,
  chat: renderChat,
};

export function renderView(root, msg, client) {
  const renderer = VIEW_RENDERERS[msg.view];
  root.innerHTML = "";
  if (!renderer) {
    const warn = document.createElement("pre");
    warn.style.color = "#f55";
    warn.textContent = `[PentaSync] View khong xac dinh: ${JSON.stringify(msg.view)}`;
    root.appendChild(warn);
    console.error("PentaSync: view khong xac dinh", msg);
    return;
  }
  renderer(root, msg, client);
}
