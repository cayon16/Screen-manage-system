# Hướng dẫn test PentaSync trên máy thật

Cầm theo file này khi đứng trước các màn hình. Làm **đúng thứ tự từ trên xuống**.

Máy test: card **RTX 4070 Ti Super** (1 HDMI + 3 DisplayPort) + **1 HDMI trên mainboard**,
tổng 5 màn hiển thị. Toàn bộ buổi test mất khoảng **60–75 phút**, phần lâu nhất là mục D.

---

## Phần A — Làm ở nhà, TRƯỚC khi đi

### A1. Test tự động phải xanh hết

```bat
cd system\backend
..\.venv\Scripts\python -m pytest -q        :: kỳ vọng 176 passed
cd ..
.venv\Scripts\python -m pytest desktop\tests -q   :: kỳ vọng 151 passed
.venv\Scripts\python -m ruff check .              :: kỳ vọng All checks passed!
```

Có test đỏ thì **đừng mang đi**, sửa xong đã.

Còn thời gian thì chạy thêm các bài kiểm tra tay (chạm thật, giả lập 6 màn, kiểm bản exe) —
xem `test\README.md` hoặc `descryption.md` mục 10.

### A2. Đóng gói `PentaSync.exe`

```bat
cd system
.venv\Scripts\python -m pip install pyinstaller
.venv\Scripts\python packaging\build.py
```

Kết quả nằm ở `system\dist\PentaSync\` (~600 MB) — **mang nguyên thư mục này** (USB). Máy công ty
**không cần cài Python**, không cần mạng.

```
PentaSync\
  PentaSync.exe          ← chạy thật
  chay_thu_nhanh.bat     ← chạy với thời gian chờ ngắn để test (10 s / 10 s / 30 s)
  _internal\             ← chương trình, đừng sửa
  content_manifest\      ← nội dung slide + tên bệnh viện (slides.json) — sửa được
  video\                 ← video chờ — chép đè file cùng tên để đổi video
  data\                  ← database chat, log, lát video đã cắt sẵn (máy tự sinh)
```

Lát video chờ đã cắt sẵn cho **5 màn** được chép kèm trong `data\`, nên máy công ty khỏi phải cắt
lại (mất ~4 phút). Số màn khác 5 thì app tự cắt lại lần đầu, trong lúc chờ vẫn chiếu bình thường.

### A3. Thử bản exe ở thư mục khác trên chính máy bạn

Chép `dist\PentaSync` ra một thư mục khác, bấm `PentaSync.exe`, thấy video chờ lên hình là được.
Thoát bằng **Ctrl+Shift+Q** (xem mục C2).

### A4. Mang theo phương án dự phòng

Mang thêm thư mục `old_system\` (bản cũ chạy bằng Edge). Nếu app mới gặp sự cố trên máy thật, vẫn
chạy được bản cũ — xem cuối file, mục "Phương án dự phòng".

---

## Phần B — Chuẩn bị máy công ty (làm 1 lần)

### B1. Cắm màn

| Cổng | Số màn |
|---|---|
| Card RTX: 1 HDMI + 3 DisplayPort | 4 màn |
| HDMI trên mainboard | 1 màn |
| Màn cảm ứng | cắm thêm **cáp USB cảm ứng** từ màn về máy |

Card GeForce chỉ xuất được tối đa 4 màn, nên màn thứ 5 bắt buộc phải cắm mainboard.

### B2. BIOS — bật đồ hoạ tích hợp

Cổng HDMI mainboard chỉ lên hình khi đồ hoạ tích hợp của CPU được bật **song song** với card rời:

- Intel: `IGD Multi-Monitor` / `iGPU Multi-Monitor` = **Enabled**
- AMD: `Integrated Graphics` = **Forces** (hoặc tương tự)
- `Primary Display` / `Init Display First` = **PCIe / PEG** (card rời)

CPU phải có đồ hoạ tích hợp — Intel đuôi **F** (vd i5-13400F) **không có**, khi đó cổng HDMI
mainboard không bao giờ lên hình. Vào Windows, cài driver đồ hoạ tích hợp (Intel/AMD) nếu Device
Manager báo thiếu.

**Kiểm tra:** Settings → System → Display phải thấy đủ các màn đang cắm.

### B3. Sắp xếp màn trong Windows — QUAN TRỌNG NHẤT

App xếp thứ tự **trái → phải theo sơ đồ trong Settings → System → Display**, không theo cổng cắm.

1. Bấm **Identify** của Windows để biết ô nào là màn nào.
2. **Kéo các ô** cho đúng vị trí thật trên tường, trái sang phải, cùng một hàng.
3. Chọn màn **chính** (Make this my main display). Nếu có **6 màn** (5 màn hiển thị + màn của
   máy chính) thì màn chính sẽ thành **màn quản lý**.
4. Độ phân giải và tỉ lệ (scale) để tuỳ ý — app tự khớp từng màn.
5. Advanced display: để tất cả **60 Hz**.

### B4. Cảm ứng — chỉ cho Windows biết cảm ứng nào thuộc màn nào

Control Panel → **Tablet PC Settings** → **Setup…** → **Touch input** → chạm vào từng màn cảm ứng
theo hướng dẫn trên màn hình.

> Bỏ qua bước này thì Windows coi mọi cảm ứng thuộc màn chính: app **không nhận ra** màn nào là
> màn cảm ứng (gán vai trò sai), và chạm vào màn 4 sẽ bấm nhầm sang màn khác.

### B5. TV qua HDMI: tắt "overscan"

Nhiều TV tự phóng to và cắt mép hình — trông giống hệt lỗi lệch màn. Trong menu TV chọn chế độ
**Just Scan / Screen Fit / PC / 1:1**. Kiểm bằng lớp "Nhận diện màn" (mục C4).

### B6. Nguồn điện

Settings → Power: **Screen** và **Sleep** = **Never**. (App cũng tự giữ màn thức khi đang chạy —
màn DisplayPort mà ngủ là Windows gỡ nó khỏi danh sách màn.)

### B7. Tắt những thứ có thể nổi đè lên app

- **Lớp phủ hiệu năng** của phần mềm card đồ hoạ (NVIDIA App / GeForce Experience overlay, AMD
  Adrenalin), **Xbox Game Bar** (Settings → Gaming): tắt — chúng vẽ đè FPS/CPU lên màn toàn màn hình.
- **Thông báo:** Settings → System → Notifications → **Do not disturb** = On.
- **Vuốt từ mép màn cảm ứng** (mở Widgets / Notification Center đè lên app):
  - Settings → Bluetooth & devices → Touch → tắt **Three- and four-finger touch gestures**.
  - Tắt vuốt mép: mở **cmd bằng quyền Administrator**, chạy lệnh dưới rồi đăng xuất / đăng nhập lại:
    ```bat
    reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows\EdgeUI" /v AllowEdgeSwipe /t REG_DWORD /d 0 /f
    ```
- **Không khoá máy khi không dùng:** Settings → Accounts → Sign-in options → "If you've been away" = Never.

> Làm hết phần B **trước khi** mở app — app phủ kín mọi màn hiển thị. Muốn chỉnh Windows Settings
> khi app đang chạy thì thoát app trước (hoặc, nếu có màn chính riêng, dùng màn chính).

### B8. Chép app

Chép `PentaSync\` vào ổ đĩa, ví dụ `D:\PentaSync\`. Không cần cài gì thêm.

---

## Phần C — Chạy

### C1. Mở app

- **Test:** bấm `chay_thu_nhanh.bat` (im lặng 10 s → hỏi "còn ở đây không", thêm 10 s → tự kết thúc
  chat, 30 s không ai chạm → cả hệ thống về video chờ).
- **Chạy thật:** bấm `PentaSync.exe` (30 s / 30 s / 120 s).

Windows có thể chặn file exe chưa ký: bấm **More info → Run anyway**.

Lần đầu mở, app tự đặt **High performance** cho `PentaSync.exe` để mọi màn vẽ bằng card RTX.
Kiểm lại ở Settings → System → Display → **Graphics**: phải thấy `PentaSync.exe` = High performance.

Cổng 8000 đã có chương trình khác dùng thì app tự chọn cổng khác (xem dòng đầu log:
`PentaSync khởi động (backend http://127.0.0.1:<cổng>)`).

### C2. Phím tắt (bàn phím của máy chính)

Phím tắt **toàn cục** — bấm lúc nào cũng được, không cần chọn cửa sổ nào:

| Phím | Tác dụng |
|---|---|
| **Ctrl+Shift+M** | Mở / ẩn bảng điều khiển (có 6 màn thì bảng luôn nằm ở màn chính) |
| **Ctrl+Shift+I** | Nhận diện màn (10 giây) |
| **Ctrl+Shift+Q** | Thoát app |

Nếu chương trình khác đã giữ tổ hợp Ctrl+Shift thì app dùng **Ctrl+Alt+Shift** + cùng chữ cái —
dòng `Phím tắt:` trong log ghi rõ tổ hợp đang dùng. Trên bảng điều khiển còn có nút
**Thoát ứng dụng** (góc trên bên phải).

Các màn hiển thị **không bao giờ nhận bàn phím** (cố ý: để 2 người chạm màn 2 và màn 4 cùng lúc
không làm mất chạm của nhau), nên app không có nút trên thanh taskbar và không hiện trong Alt+Tab.

### C3. App gán vai trò thế nào

```
Tổng số màn ≥ 6 : màn chính của Windows = MÀN QUẢN LÝ, các màn còn lại hiển thị
Tổng số màn ≤ 5 : tất cả là màn hiển thị

Không màn nào cảm ứng → đánh số 1, 2, 3, 4, 5 lần lượt trái → phải
Có màn cảm ứng        → màn cảm ứng nhận 2 và 4 (trái → phải)
                         màn thường nhận 1, 3, 5 (trái → phải)
                         màn thừa nhận số còn trống nhỏ nhất
```

| Màn | Vai trò | Khi hệ thống thức |
|---|---|---|
| 1, 3, 5 | Trình chiếu, không nhận chạm | Slide |
| 2 | Điều khiển (cảm ứng) | Menu 2 ô: Thông tin bệnh viện / Chat |
| 4 | Chat (cảm ứng) | "Chạm để bắt đầu" |

Ví dụ 5 màn, cảm ứng ở vị trí 2 và 4 → đúng 1-2-3-4-5. Nếu cảm ứng nằm ở vị trí 1 và 3 thì thứ tự
sẽ là 2-1-4-3-5 — đây là **đúng quy tắc**, không phải lỗi.

### C4. Nhận diện màn (Ctrl+Shift+I)

Mỗi màn hiện số vai trò thật to, kèm độ phân giải, tỉ lệ, có cảm ứng không, tên thiết bị và
**tên card đồ hoạ**. Kiểm:

- [ ] **Viền xanh ôm sát cả 4 mép** mọi màn, 4 góc đen đủ cả. Bị cắt → TV đang overscan (B5).
- [ ] Số trên từng màn đúng quy tắc C3; "Cảm ứng: Có" đúng ở các màn cảm ứng.
- [ ] 4 màn ghi **NVIDIA GeForce RTX 4070 Ti SUPER**, 1 màn ghi tên đồ hoạ tích hợp (Intel/AMD).
- [ ] Bảng điều khiển (Ctrl+Shift+M) **không** có dòng chữ đỏ "Cảm ứng: …". Có thì làm lại B4.

---

## Phần D — Danh sách kiểm tra

### Nhóm 0 — Căn chỉnh (lỗi của bản cũ)

- [ ] **0.1** Mỗi màn hiển thị trọn nội dung của riêng nó, **không phần nào lấn sang màn bên**.
- [ ] **0.2** Làm lại 0.1 khi **đổi scale** của 1 màn (vd 100% → 150%) trong Windows Settings:
      sau ~3 giây app tự xếp lại, vẫn khớp.
- [ ] **0.3** Nếu các màn khác độ phân giải: từng màn vẫn khớp mép. (Giao diện giữ tỉ lệ 16:9; màn
      tỉ lệ khác sẽ có dải trắng hai bên — không méo chữ.)
- [ ] **0.4** Mở `data\pentasync_app_log.txt`: mỗi màn có 1 dòng `Màn N khớp \\.\DISPLAYx: cửa sổ (…) = màn (…)`,
      **không có** dòng `LỆCH`. (App tự đo vị trí thật của từng cửa sổ mỗi 5 giây và tự sửa nếu lệch.)
- [ ] **0.5** Bấm chuột / phím Windows trên màn chính cho menu Start bật lên rồi tắt: sau tối đa 5 giây
      **không màn hiển thị nào bị thanh taskbar che** ở mép dưới.

### Nhóm 1 — Chế độ chờ

- [ ] **1.1** Mọi màn chiếu video cá, không màn nào đen hay báo lỗi.
- [ ] **1.2** Đứng lùi ra nhìn cả dãy: con cá bơi **liền mạch** qua các đường ghép, không lệch thời gian.
      *(Cá bị giãn ngang là bình thường và đã thống nhất — cần video siêu rộng mới hết.)*
- [ ] **1.3** Không màn nào phát tiếng.
- [ ] **1.4** Màn cắm mainboard chạy mượt như 4 màn kia.

### Nhóm 2 — Đánh thức

- [ ] **2.1** Chạm **màn 2** → màn 2 hiện menu, màn 4 hiện "Chạm để bắt đầu", **màn 1/3/5 lên slide ngay**.
- [ ] **2.2** Chạm màn 1/3/5 → không có gì xảy ra.
- [ ] **2.3** Chờ về video chờ, chạm **màn 4** → màn 4 vào thẳng khung chat, màn 2 hiện menu, 1/3/5 lên slide.
- [ ] **2.4** Đang ở video chờ, **lắc chuột máy chính** → cả hệ thống thức dậy như 2.1.

### Nhóm 3 — Trình chiếu thông tin bệnh viện

- [ ] **3.1** Màn 2 bấm "Thông tin bệnh viện" → bảng 6 ô chia 3 cột (màn bên trái / giữa / bên phải),
      ô đang chiếu có viền xanh + "Đang chiếu".
- [ ] **3.2** Bấm lần lượt **từng ô trong 6 ô**: mỗi lần **đúng một màn** đổi nội dung, 2 màn kia đứng yên.
- [ ] **3.3** "Quay lại" → màn 2 về menu, màn 1/3/5 **giữ nguyên** slide.
- [ ] **3.4** "Chat với Superdoc" ngay trên bảng 6 ô → vào chat, slide 1/3/5 không bị ngắt.

### Nhóm 4 — Chat với Superdoc

- [ ] **4.1** Vào chat → thấy lời chào + 4 câu hỏi gợi ý. Chạm 1 câu gợi ý → gửi luôn, có trả lời.
- [ ] **4.2** Chạm **ô nhập** → bàn phím trượt lên. Chạm vùng hội thoại (hoặc phím **Ẩn**) → bàn phím ẩn.
- [ ] **4.3** Gõ Telex `beenhj vieenj mowr cuwar maays giowf` → hiện **"bệnh viện mở cửa mấy giờ"**.
      Phím **Hoa** viết hoa 1 chữ; **123** sang số; giữ **Xoá** thì xoá liên tục.
- [ ] **4.4** Bấm gửi → ô nhập khoá, hiện 3 chấm "đang soạn"; có trả lời thì mở lại. Bàn phím vẫn mở để hỏi tiếp.
- [ ] **4.5** Hỏi "Tôi bị đau bụng thì uống thuốc gì?" → **từ chối tư vấn**, hướng tới quầy tiếp đón.
- [ ] **4.6** **Hai người dùng cùng lúc:** 2 người **gõ nhanh cùng lúc** ở màn 2 và màn 4 (2 bàn phím mở
      song song) → không mất phím nào, chữ không nhảy sang màn kia, 2 đoạn chat riêng biệt, màn 1/3/5 vẫn chiếu slide.
- [ ] **4.6b** Một người **đặt tay giữ yên** trên màn 2, người kia bấm nút ở màn 4 → nút ở màn 4 vẫn ăn.
- [ ] **4.6c** Chạm **giữ lâu** (1–2 giây) vào một nút rồi nhả → nút vẫn ăn (người lớn tuổi hay bấm kiểu này).
      Chạm không hiện vòng tròn / ô vuông của Windows.
- [ ] **4.7** "Kết thúc" ở **màn 4** → màn 4 về "Chạm để bắt đầu"; chat ở màn 2 không bị ảnh hưởng.
- [ ] **4.8** "Kết thúc" ở **màn 2** → màn 2 về **menu**; màn 1/3/5 giữ nguyên slide.

### Nhóm 5 — Đổi chế độ giữa chừng (màn 2)

- [ ] **5.1** Đang chat ở màn 2, bấm "Xem thông tin bệnh viện" → hộp xác nhận.
- [ ] **5.2** "Huỷ, tiếp tục chat" → về chat, **đoạn hội thoại cũ còn nguyên**.
- [ ] **5.3** Bấm lại → "Đồng ý, kết thúc" → màn 2 sang bảng 6 ô, chat bị xoá sạch.

### Nhóm 6 — Tự dọn dẹp theo thời gian (dùng `chay_thu_nhanh.bat`)

- [ ] **6.1** Vào chat ở màn 4, hỏi 1 câu, rồi **đứng im**. ~10 giây sau hiện "Bạn còn muốn tiếp tục
      trò chuyện không?" với **số giây đếm ngược**.
- [ ] **6.2** Bấm "Tôi vẫn ở đây" (hoặc chạm bất kỳ đâu) → hộp biến mất, chat còn nguyên.
- [ ] **6.3** Đứng im lần nữa, không bấm gì → ~10 giây sau chat **tự kết thúc**, màn 4 về "Chạm để bắt đầu".
- [ ] **6.4** Đang gõ chậm một câu dài trên bàn phím → **không** bị hỏi "còn ở đây không" (mỗi lần chạm
      phím đều được tính là còn ở đây).
- [ ] **6.5** **Rời tay hoàn toàn** (không chạm màn, không động chuột/phím máy chính) 30 giây → mọi màn
      về video chờ.
      > Chỉ cần động vào chuột/bàn phím máy chính là đồng hồ đếm lại — đúng đặc tả, không phải lỗi.
      > Kể cả khi đang dùng bảng điều khiển bằng chuột.

### Nhóm 7 — Bảng điều khiển (Ctrl+Shift+M)

- [ ] **7.1** Bảng hiện đủ 5 thẻ màn: trạng thái (Video chờ / Menu / Đang chiếu / Đang chat…), độ phân
      giải, cảm ứng, tên card. Thẻ đổi theo ngay khi thao tác trên các màn.
- [ ] **7.2** Màn đang chat hiện "Có người đang trò chuyện" + thời gian chạy.
- [ ] **7.3** Mục "Đổi nội dung đang chiếu": bấm 1 ô → đúng màn đó đổi slide (không cần đụng màn 2).
- [ ] **7.4** **Đưa về video chờ** → mọi màn về video chờ, chat đang mở bị kết thúc.
- [ ] **7.5** **Tắt hẳn màn hình** → mọi màn **đen**. Chạm màn 2/4 và lắc chuột → **không** thức dậy.
- [ ] **7.6** **Bật lại màn hình** → về video chờ; chạm màn 2 → thức dậy bình thường.
- [ ] **7.7** **Reset hệ thống** → hỏi xác nhận → mọi chat kết thúc, slide về mặc định, các màn mở lại.
- [ ] **7.8** Ô "Hôm nay": số lượt chat tăng sau mỗi lần chat.
- [ ] **7.9** Nếu có 6 màn: bảng nằm cố định ở **màn chính**, 5 màn kia hiển thị bình thường.

### Nhóm 8 — Cắm / rút / tắt màn

- [ ] **8.1** Rút 1 màn (hoặc tắt nguồn màn DisplayPort). Sau ~3 giây app xếp lại: các màn còn lại nhận
      vai trò theo quy tắc C3, video chờ chia lại theo số màn mới.
- [ ] **8.2** Cắm lại → sau ~3 giây về như cũ.
- [ ] **8.3** Rút màn đang có người chat → chat đó kết thúc, các màn khác không ảnh hưởng.
      *(Số màn khác 5: lần đầu app phải cắt lại video ~4 phút; trong lúc đó vẫn chiếu bình thường.)*

### Nhóm 9 — Tự phục hồi

- [ ] **9.1** Task Manager → Details → có **2** tiến trình `PentaSync.exe`. Kết thúc tiến trình **nhỏ
      hơn** (backend) → các màn hiện "Đang kết nối hệ thống…" vài giây rồi tự trở lại.
- [ ] **9.2** Kết thúc tiến trình **lớn hơn** (app) → cả 2 tiến trình biến mất (không bỏ lại backend chạy ngầm).
      Mở lại `PentaSync.exe` → chạy bình thường.
- [ ] **9.3** Bấm `PentaSync.exe` lần nữa khi app đang chạy → không mở thêm bản thứ hai.

### Nhóm 10 — Tài nguyên

- [ ] **10.1** Để ở video chờ, Task Manager → **Details**: ghi CPU và RAM của 2 tiến trình `PentaSync.exe`.
      (Máy dev: tổng ~4–5% CPU, ~1,3 GB RAM.)
- [ ] **10.2** Tab **Performance → GPU**: card RTX phải có tải video; đồ hoạ tích hợp gần như rảnh.
- [ ] **10.3** Để chạy liên tục 15–20 phút: không ì dần, không nóng bất thường, cá vẫn liền mạch.

---

## Xử lý sự cố

| Hiện tượng | Nguyên nhân thường gặp | Cách xử lý |
|---|---|---|
| Màn cắm mainboard không lên hình | Đồ hoạ tích hợp chưa bật / CPU không có | B2 |
| Thứ tự màn sai | Sơ đồ màn trong Windows chưa đúng vị trí thật | B3, rồi chờ 3 giây (app tự xếp lại) |
| Không màn nào được coi là cảm ứng / chạm màn 4 ăn sang màn khác | Chưa chạy Tablet PC Settings | B4, rồi mở lại app |
| Viền "Nhận diện màn" bị cắt mép | TV overscan | B5 |
| Hình giật, cá đứt gãy | App đang vẽ bằng đồ hoạ tích hợp | Kiểm Graphics = High performance (C1), mở lại app. Xem log dòng `Adapter … using this adapter` |
| Màn hiện "Đang kết nối hệ thống…" mãi | Backend không chạy được (vd cổng 8000 bị chiếm) | Xem `data\pentasync_app_log.txt`; tắt chương trình đang chiếm cổng 8000 |
| Video chờ báo "Không phát được" | Thiếu `video\standby_wall.mp4` | Chép lại file vào đúng thư mục `video\` |
| Không bao giờ về video chờ | Có người động chuột/phím máy chính | Rời tay hoàn toàn |
| Phím tắt không ăn | Chương trình khác giữ tổ hợp phím | Xem dòng `Phím tắt:` trong log (có thể là Ctrl+Alt+Shift); hoặc dùng nút Thoát trên bảng điều khiển |
| Mép dưới màn bị taskbar che | Menu Start / taskbar vừa được bấm | Chờ ≤ 5 giây app tự đẩy lên lại; nếu là màn chính: bật "Automatically hide the taskbar" |
| Có chữ FPS/GPU/CPU đè trên màn | Lớp phủ của phần mềm card đồ hoạ / Game Bar | B7 |
| Vuốt từ mép màn cảm ứng mở ra bảng của Windows | Cử chỉ vuốt mép chưa tắt | B7 |
| Dòng đỏ "Cảm ứng: …" trên bảng điều khiển | Cảm ứng chưa gán đúng màn | B4, rồi mở lại app |
| Log có dòng `LỆCH` lặp lại mãi | Driver / Windows không cho đặt cửa sổ đúng màn | Gửi log về; thử đổi scale màn đó về 100% |
| Mở exe không thấy gì | App đã đang chạy (chỉ cho 1 bản) | Task Manager → kết thúc `PentaSync.exe` cũ |
| Chat trả lời "cứng" | Không phải lỗi — mặc định dùng AI giả (`mock`) | Hỏi về giờ khám / cấp cứu / bảo hiểm / quy trình |

**Log** (ghi chi tiết theo thời gian, gửi kèm khi báo lỗi):
- `data\pentasync_app_log.txt` — app. Các dòng đáng xem: `Bố cục:` (màn nào vai trò gì, cảm ứng, card),
  `khớp` / `LỆCH` (vị trí cửa sổ), `Cảm ứng:` (cảnh báo gán cảm ứng), `Adapter … using this adapter`
  (card dùng để vẽ), `Phím tắt:`, và mọi dòng `ERROR` / `CRITICAL`.
- `data\pentasync_log.txt` — backend: trạng thái, chat, cắt video

---

## Cần ghi lại để báo về

1. Ảnh chụp **lớp nhận diện** của cả dãy màn (C4) và dòng `Bố cục:` trong `data\pentasync_app_log.txt`.
2. Con cá có **liền mạch** không (1.2); màn cắm mainboard có mượt không (1.4).
3. CPU / RAM / tải GPU ở video chờ (nhóm 10).
4. Mục nào **không đạt**, kèm ảnh chụp và 2 file log.
5. Model CPU (có đồ hoạ tích hợp không) và model từng màn (có cảm ứng không, cổng nào).

---

## Chat AI thật (Gemini) — tuỳ chọn, cần mạng

Mở **cmd** trong thư mục `PentaSync\` rồi gõ:

```bat
set SUPERDOC_PROVIDER=gemini
set GEMINI_API_KEY=<khoá của bạn>
PentaSync.exe
```

Đừng ghi khoá vào file nào trong thư mục app. Thiếu khoá hoặc mất mạng thì app tự lùi về AI giả.

## Những gì CHƯA có, đừng test

- **Chatbot Superdoc thật** — chưa có tài liệu API (đang dùng AI giả hoặc Gemini).
- **Nội dung slide thật** — 6 slide hiện tại là mẫu. Tên bệnh viện sửa ở `content_manifest\slides.json`
  (`"hospital_name"`), mở lại app để áp dụng.
- **Cá không bị giãn ngang** — cần video siêu rộng (~8,9:1), không phải sửa code.
- **Tự chạy khi bật máy** — muốn có thì đặt lối tắt `PentaSync.exe` vào thư mục Startup
  (Win+R → `shell:startup`).

## Phương án dự phòng (bản cũ chạy bằng Edge)

Chỉ dùng khi app mới không chạy được. Cần cài Python 3.10+ trên máy công ty:

```bat
cd old_system\backend
pip install -r requirements.txt
cd ..\launcher
python launcher.py --dry-run
python launcher.py
```

Bản cũ cần video chờ ở `old_system\video\standby_wall.mp4` (chép tay từ `system\video\`).

Bản cũ vẫn có lỗi lấn màn khi scale khác 100%, nên đặt scale mọi màn = **100%** trước khi chạy.
