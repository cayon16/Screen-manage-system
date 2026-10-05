import { WSClient } from "./ws_client.js";
import { renderView } from "./state_router.js";
import { showConfirm, hideConfirm } from "./views/confirm_dialog_view.js";
import { appendTurn, setError, resetHistory } from "./views/chat_view.js";

// screen_id lay tu URL /screen/{id} — duy nhat 1 nguon su that, khop voi cach backend
// (http_routes.py) phuc vu cung 1 index.html cho ca 5 man va de JS tu doc id tu path.
const SCREEN_ID = Number(location.pathname.split("/").filter(Boolean).pop());
const TOUCH_SCREENS = [2, 4]; // phai khop app/config.py TOUCH_SCREENS

const root = document.getElementById("psync-root");
const debugLabel = document.getElementById("psync-debug-label");

function setDebugLabel(text) {
  if (debugLabel) debugLabel.textContent = text;
}

setDebugLabel(`Man ${SCREEN_ID} - dang ket noi...`);

const client = new WSClient(SCREEN_ID);

// CHI Man 2/4 gan input handler o day — dung voi dac ta "Man 1/3/5 tuyet doi khong
// tuong tac". Cac nut cu the (menu, chat, thoat...) trong tung view phai goi
// event.stopPropagation() truoc khi client.touch(...) de khong bi handler nay
// gui THEM 1 lan "generic_wake" ngay sau khi vua chon 1 hanh dong cu the.
if (TOUCH_SCREENS.includes(SCREEN_ID)) {
  document.body.addEventListener("click", () => client.touch("generic_wake"));
}

client.onMessage((msg) => {
  if (msg.type === "state_update") {
    // Moi lan state doi la moi hop thoai cu deu het y nghia. Backend luon gui state_update
    // TRUOC confirm_prompt cua "mode_switch" nen thu tu nay khong lam mat hop thoai do.
    hideConfirm();
    setDebugLabel(`Man ${SCREEN_ID} - ${msg.state}`);
    renderView(root, msg, client);
  } else if (msg.type === "chat_message_ack") {
    // Ghi vao lich su TRUOC khi state_update ke tiep toi — controller luon gui ack roi moi
    // gui state_update, nen luot tra loi moi se co mat ngay trong lan render sau do.
    appendTurn(msg.session_id, msg.role, msg.text);
  } else if (msg.type === "error") {
    setError(msg.session_id, msg.message);
  } else if (msg.type === "session_closed") {
    resetHistory(null);
  } else if (msg.type === "confirm_prompt") {
    showConfirm(msg, client);
  } else {
    console.log("PentaSync message chua xu ly UI:", msg);
  }
});

client.connect();
