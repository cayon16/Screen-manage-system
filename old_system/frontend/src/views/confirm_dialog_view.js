// Overlay xac nhan — dung chung cho 2 tinh huong:
//   "mode_switch"   : Man 2 doi tu Chat sang Thong tin benh vien (phai bam ro Dong y / Huy)
//   "tier1_warning" : canh bao im lang truoc khi tu dong ket thuc doan chat
export function hideConfirm() {
  const overlay = document.getElementById("psync-overlay");
  if (!overlay) return;
  overlay.style.display = "none";
  overlay.innerHTML = "";
  overlay.onclick = null;
}

export function showConfirm(msg, client) {
  const overlay = document.getElementById("psync-overlay");
  if (!overlay) return;
  overlay.innerHTML = "";
  // Xoa handler cua hop thoai truoc: neu con sot lai, bam vao nen cua hop thoai "mode_switch"
  // se gui nham 1 tier1_ack cua phien cu.
  overlay.onclick = null;
  overlay.style.display = "flex";

  const box = document.createElement("div");
  Object.assign(box.style, {
    background: "#1c2733",
    color: "#fff",
    padding: "3rem 4rem",
    borderRadius: "20px",
    maxWidth: "70vw",
    textAlign: "center",
    fontFamily: "Segoe UI, sans-serif",
  });
  // Bam vao chinh hop thoai khong duoc lot xuong overlay ben duoi.
  box.onclick = (e) => e.stopPropagation();

  const text = document.createElement("p");
  text.style.fontSize = "1.8rem";
  text.style.margin = "0";
  text.textContent = msg.message;
  box.appendChild(text);

  const btnRow = document.createElement("div");
  Object.assign(btnRow.style, {
    display: "flex",
    gap: "1.5rem",
    justifyContent: "center",
    marginTop: "2.5rem",
  });

  if (msg.kind === "mode_switch") {
    btnRow.appendChild(
      makeButton("Đồng ý, kết thúc chat", "#22a35e", (e) => {
        e.stopPropagation();
        client.touch("confirm_yes");
        hideConfirm();
      })
    );
    btnRow.appendChild(
      makeButton("Hủy, tiếp tục chat", "#3a4757", (e) => {
        e.stopPropagation();
        client.touch("confirm_no");
        hideConfirm();
      })
    );
  } else {
    const ack = (e) => {
      e.stopPropagation();
      client.send({ type: "tier1_ack", screen_id: msg.screen_id, session_id: msg.session_id || "" });
      hideConfirm();
    };
    btnRow.appendChild(makeButton("Tôi vẫn ở đây", "#2a63ff", ack));
    // Man hinh cam ung o hanh lang: nguoi dung co xu huong cham dai chu khong nham nut.
    // Cham bat cu dau tren overlay deu tinh la "van con o day".
    overlay.onclick = ack;

    const countdown = document.createElement("div");
    Object.assign(countdown.style, { marginTop: "1.5rem", opacity: "0.6", fontSize: "1.1rem" });
    let remaining = msg.timeout_sec;
    countdown.textContent = `Đoạn chat sẽ tự kết thúc sau ${remaining} giây.`;
    box.appendChild(countdown);
    const tick = setInterval(() => {
      remaining -= 1;
      // Dung ngay khi hop thoai bi an HOAC bi thay bang hop thoai khac (box roi khoi DOM).
      if (remaining <= 0 || overlay.style.display === "none" || !overlay.contains(box)) {
        clearInterval(tick);
        return;
      }
      countdown.textContent = `Đoạn chat sẽ tự kết thúc sau ${remaining} giây.`;
    }, 1000);
  }

  box.appendChild(btnRow);
  overlay.appendChild(box);
}

function makeButton(label, color, onClick) {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.textContent = label;
  Object.assign(btn.style, {
    fontSize: "1.4rem",
    padding: "1.2rem 2.2rem",
    borderRadius: "12px",
    border: "none",
    cursor: "pointer",
    background: color,
    color: "#fff",
  });
  btn.onclick = onClick;
  return btn;
}
