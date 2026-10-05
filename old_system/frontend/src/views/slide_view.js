// Man 1/3/5 dang trinh chieu. Noi dung do backend gui xuong (content_manifest/slides.json),
// view nay khong chua chu nghia nao cua benh vien — sua noi dung thi sua file JSON.
//
// 3 loai slide theo dac ta ("1 doan video co truoc hoac slide trinh chieu (da co)"):
//   text  — chu go thang trong manifest
//   image — 1 tam anh trong content_manifest/media/
//   video — 1 doan video trong content_manifest/media/, phat lap va tat tieng
export function render(root, msg) {
  const slide = (msg.data || {}).slide;

  if (!slide) {
    root.appendChild(message(`Màn ${msg.screen_id}: chưa có nội dung slide trong slides.json`));
    return;
  }

  if (slide.kind === "image") {
    root.appendChild(mediaSlide(slide, "image"));
    return;
  }
  if (slide.kind === "video") {
    root.appendChild(mediaSlide(slide, "video"));
    return;
  }
  root.appendChild(textSlide(slide, msg.screen_id));
}

function textSlide(slide, screenId) {
  const wrap = document.createElement("div");
  Object.assign(wrap.style, {
    position: "relative",
    width: "100vw",
    height: "100vh",
    boxSizing: "border-box",
    padding: "6vh 6vw",
    display: "flex",
    flexDirection: "column",
    justifyContent: "center",
    fontFamily: "Segoe UI, sans-serif",
    color: "#fff",
    background: `linear-gradient(135deg, ${slide.accent}, #06121c)`,
  });

  const title = document.createElement("h1");
  title.textContent = slide.title;
  Object.assign(title.style, {
    fontSize: "min(7vw, 9vh)",
    margin: "0 0 1vh 0",
    lineHeight: "1.1",
  });
  wrap.appendChild(title);

  const subtitle = document.createElement("div");
  subtitle.textContent = slide.subtitle;
  Object.assign(subtitle.style, {
    fontSize: "min(3vw, 4vh)",
    opacity: "0.85",
    marginBottom: "4vh",
  });
  wrap.appendChild(subtitle);

  const list = document.createElement("ul");
  Object.assign(list.style, {
    fontSize: "min(2.6vw, 3.6vh)",
    lineHeight: "1.9",
    listStyle: "none",
    padding: "0",
    margin: "0",
  });
  for (const line of slide.bullets || []) {
    const li = document.createElement("li");
    // Dung ky tu bullet thay vi ::before de khong phai chen the <style> vao trang.
    li.textContent = "•  " + line;
    Object.assign(li.style, {
      marginBottom: "1.2vh",
      paddingLeft: "1.6em",
      textIndent: "-1.6em",
    });
    list.appendChild(li);
  }
  wrap.appendChild(list);

  const footer = document.createElement("div");
  footer.textContent = `Màn ${screenId}`;
  Object.assign(footer.style, {
    position: "absolute",
    right: "2vw",
    bottom: "2vh",
    fontSize: "1rem",
    opacity: "0.35",
  });
  wrap.appendChild(footer);

  return wrap;
}

function mediaSlide(slide, kind) {
  const wrap = document.createElement("div");
  Object.assign(wrap.style, {
    width: "100vw",
    height: "100vh",
    background: "#000",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    overflow: "hidden",
  });

  const el = document.createElement(kind === "video" ? "video" : "img");
  el.src = slide.src;
  Object.assign(el.style, { width: "100%", height: "100%", objectFit: "contain" });

  if (kind === "video") {
    el.autoplay = true;
    el.loop = true;
    // Bat buoc tat tieng: 5 man trong cung 1 hanh lang phat tieng chong nhau se rat kho chiu,
    // va trinh duyet cung chi cho tu dong phat khi da tat tieng.
    el.muted = true;
    el.playsInline = true;
  } else {
    el.alt = slide.title;
  }

  el.addEventListener("error", () => {
    wrap.innerHTML = "";
    wrap.appendChild(
      message(`Không tải được ${slide.src} — kiểm tra file trong content_manifest/media/`)
    );
  });

  wrap.appendChild(el);
  return wrap;
}

function message(text) {
  const box = document.createElement("div");
  box.textContent = text;
  Object.assign(box.style, {
    width: "100vw",
    height: "100vh",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    textAlign: "center",
    padding: "0 6vw",
    boxSizing: "border-box",
    background: "#06121c",
    color: "#fff",
    fontFamily: "Segoe UI, sans-serif",
    fontSize: "min(2.5vw, 3.5vh)",
  });
  return box;
}
