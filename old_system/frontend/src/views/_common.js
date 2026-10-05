// Style dung chung giua nhieu view — tranh lap lai cung 1 khoi style o 4-5 file.

export function fullscreenContainer(background) {
  const div = document.createElement("div");
  Object.assign(div.style, {
    width: "100vw",
    height: "100vh",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    background,
    color: "#fff",
    fontFamily: "sans-serif",
    boxSizing: "border-box",
    textAlign: "center",
  });
  return div;
}

export function bigButton(label, color) {
  const btn = document.createElement("button");
  btn.textContent = label;
  Object.assign(btn.style, {
    fontSize: "2rem",
    padding: "1.5rem 3rem",
    borderRadius: "16px",
    border: "none",
    cursor: "pointer",
    background: color || "#2a63ff",
    color: "#fff",
  });
  return btn;
}
