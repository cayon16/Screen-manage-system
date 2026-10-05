Thư mục chứa ảnh và video dùng cho slide của màn 1, 3, 5.

Cách dùng: bỏ file vào đây, rồi trong slides.json khai báo slide với "kind" và "src".

    {
      "id": "noi_quy_anh",
      "kind": "image",
      "title": "Nội quy bệnh viện",
      "src": "noi_quy.png"
    }

    {
      "id": "gioi_thieu_video",
      "kind": "video",
      "title": "Giới thiệu bệnh viện",
      "src": "gioi_thieu.mp4"
    }

Lưu ý:
- "src" là TÊN FILE nằm ngay trong thư mục này, không phải đường dẫn đầy đủ.
- Video luôn được phát lặp và TẮT TIẾNG: 5 màn trong cùng một hành lang mà phát tiếng
  chồng lên nhau sẽ rất khó chịu.
- Ảnh nên đúng tỉ lệ màn hình (thường 16:9) để không bị viền đen hai bên.
- Nếu file khai trong slides.json không tồn tại, backend vẫn khởi động bình thường nhưng ghi
  cảnh báo vào pentasync_log.txt và màn hình đó hiện thông báo thiếu file.

File README.txt này cũng giữ cho thư mục không bị rỗng — thư mục rỗng hay bị mất khi nén zip
mang sang máy khác.
