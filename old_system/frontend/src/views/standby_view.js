// Che do cho: 5 man ghep lai thanh MOT khung hinh video duy nhat.
//
// Dac ta cam ro: "5 man can dong nhat khau trinh chieu, ko duoc 5 man 5 video doc lap".
//
// Cach cat: keo gian video cho rong bang ca 5 man (500vw) roi day sang trai dung
// screen_index x 100vw. Man thu i vi vay chi nhin thay lat cat [i x 100vw, (i+1) x 100vw].
// Trinh duyet tu composite lop video tren GPU — khong co phep tinh nao chay moi khung hinh.
//
// LUU Y hinh bi gian ngang: 5 man ghep lai co ti le ~8.9:1 con video la 16:9, nen keo cho phu
// kin thi con ca bi gian ngang ~5 lan. Day la lua chon TAM THOI da thong nhat voi khach
// (xem docs/architecture.md muc 5), khong phai loi.
//
// Dong bo: khong truyen frame. Server cap 1 moc t0 dung chung, moi man tu tinh
//     target = (now_server - t0) mod video.duration
// roi keo currentTime cua no ve dung moc do. Khac voi ban ve canvas truoc day, o day hinh anh
// lien nhau qua CA 4 duong ghep cung mot luc, nen lech thoi gian la thay ngay — phai chinh lien
// tuc chu khong dat mot lan roi thoi.

const SYNC_INTERVAL_MS = 500;
// Lech qua nguong nay thi nhay thang cho nhanh, duoi nguong thi chinh muot bang playbackRate.
const HARD_SEEK_SEC = 0.3;
// Duoi nguong nay coi nhu da khop, tra toc do phat ve binh thuong.
const IN_SYNC_SEC = 0.02;
const RATE_GAIN = 0.5;
const RATE_MIN = 0.85;
const RATE_MAX = 1.15;

export function render(root, msg) {
  const data = msg.data || {};
  const screenIndex = data.screen_index ?? 0;
  const screenCount = data.screen_count ?? 5;
  const videoSrc = data.video_src || "/standby-video";

  // Do lech dong ho: server_now duoc chup luc server gui message. Bo qua do tre truyen tin vi
  // ca 5 trinh duyet deu noi toi cung 1 backend qua localhost (do tre ~1ms, khong dang ke).
  const clockOffsetSec = (data.server_now ?? Date.now() / 1000) - Date.now() / 1000;
  const t0 = data.t0 ?? 0;

  const wrap = document.createElement("div");
  Object.assign(wrap.style, {
    position: "relative",
    width: "100vw",
    height: "100vh",
    overflow: "hidden",
    background: "#000",
  });

  const video = document.createElement("video");
  video.src = videoSrc;
  video.loop = true;
  video.playsInline = true;
  // Bat buoc tat tieng: 5 man trong cung 1 hanh lang phat tieng chong nhau se rat kho chiu, va
  // trinh duyet cung chi cho tu dong phat khi da tat tieng.
  video.muted = true;
  video.autoplay = true;
  video.preload = "auto";
  Object.assign(video.style, {
    position: "absolute",
    top: "0",
    left: `${-screenIndex * 100}vw`,
    width: `${screenCount * 100}vw`,
    height: "100vh",
    objectFit: "fill", // keo gian cho vua khung — chap nhan meo
  });

  wrap.appendChild(video);
  root.appendChild(wrap);

  // ---------- dong bo ----------

  function targetTime() {
    const duration = video.duration;
    if (!Number.isFinite(duration) || duration <= 0) return null;
    const elapsed = Date.now() / 1000 + clockOffsetSec - t0;
    return ((elapsed % duration) + duration) % duration;
  }

  function drift(target) {
    // Khoang cach theo VONG TRON: luc video vua lap lai, currentTime ve 0 con target con o gan
    // cuoi (hoac nguoc lai). Neu tru thang se ra sai so bang gan het do dai video roi nhay lung tung.
    const duration = video.duration;
    let d = target - video.currentTime;
    if (d > duration / 2) d -= duration;
    if (d < -duration / 2) d += duration;
    return d;
  }

  function resync() {
    const target = targetTime();
    if (target === null) return;

    const d = drift(target);
    if (Math.abs(d) > HARD_SEEK_SEC) {
      video.currentTime = target;
      video.playbackRate = 1;
      return;
    }
    if (Math.abs(d) < IN_SYNC_SEC) {
      video.playbackRate = 1;
      return;
    }
    // Cham hon moc chung (d > 0) -> phat nhanh len mot chut, va nguoc lai.
    video.playbackRate = Math.min(RATE_MAX, Math.max(RATE_MIN, 1 + d * RATE_GAIN));
  }

  video.addEventListener("loadedmetadata", () => {
    const target = targetTime();
    if (target !== null) video.currentTime = target;
    video.play().catch(() => {
      // Trinh duyet chan tu dong phat (rat kho xay ra vi da muted) — hien thong bao thay vi man den cam.
      showMessage(wrap, "Khong tu dong phat duoc video cho. Kiem tra cai dat tu dong phat cua trinh duyet.");
    });
  });

  video.addEventListener("error", () => {
    showMessage(
      wrap,
      `Khong tai duoc video cho (${videoSrc}). Kiem tra STANDBY_VIDEO_REL_PATH trong backend/app/config.py.`
    );
  });

  const syncTimer = setInterval(resync, SYNC_INTERVAL_MS);

  // state_router xoa root truoc khi render view moi -> video roi khoi DOM nhung setInterval van
  // song va the <video> van giai ma ngam. Phai tu dung lai, neu khong sau vai lan chuyen trang
  // thai se co nhieu vong dong bo chay chong nhau va an dan CPU.
  const observer = new MutationObserver(() => {
    if (!document.body.contains(video)) {
      clearInterval(syncTimer);
      video.pause();
      video.removeAttribute("src");
      video.load();
      observer.disconnect();
    }
  });
  observer.observe(root, { childList: true });
}

function showMessage(wrap, text) {
  wrap.innerHTML = "";
  const box = document.createElement("div");
  box.textContent = text;
  Object.assign(box.style, {
    width: "100%",
    height: "100%",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    textAlign: "center",
    padding: "0 6vw",
    boxSizing: "border-box",
    color: "#fff",
    fontFamily: "Segoe UI, sans-serif",
    fontSize: "min(2.2vw, 3vh)",
  });
  wrap.appendChild(box);
}
