// Boc WebSocket toi /ws/{screenId}: tu ket noi lai (backoff tang dan), gui typed message.
// Khong tu quyet dinh state gi ca — chi chuyen tiep message tho toi listener dang ky qua onMessage().
export class WSClient {
  constructor(screenId) {
    this.screenId = screenId;
    this.socket = null;
    this._listeners = [];
    this._reconnectDelayMs = 1000;
    this._closedByUser = false;
  }

  onMessage(fn) {
    this._listeners.push(fn);
  }

  connect() {
    this._closedByUser = false;
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${proto}//${location.host}/ws/${this.screenId}`;
    const socket = new WebSocket(url);
    this.socket = socket;

    // Khong can gui "hello": backend gui state_update snapshot ngay khi chap nhan ket noi
    // (ClientConnectedCommand trong ws_routes.py), ke ca sau moi lan tu ket noi lai.
    socket.addEventListener("open", () => {
      this._reconnectDelayMs = 1000;
    });

    socket.addEventListener("message", (evt) => {
      let msg;
      try {
        msg = JSON.parse(evt.data);
      } catch (e) {
        console.error("PentaSync: nhan duoc message khong phai JSON", evt.data);
        return;
      }
      for (const fn of this._listeners) fn(msg);
    });

    socket.addEventListener("close", () => {
      if (this._closedByUser) return;
      setTimeout(() => this.connect(), this._reconnectDelayMs);
      this._reconnectDelayMs = Math.min(this._reconnectDelayMs * 2, 15000);
    });

    socket.addEventListener("error", () => {
      socket.close();
    });
  }

  send(payload) {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(payload));
    }
  }

  // Goi tat cho touch_event — target la ma dinh danh phan tu duoc cham (xem cluster_controller.py).
  touch(target) {
    this.send({ type: "touch_event", screen_id: this.screenId, target });
  }
}
