import yt_dlp
import random
import os

def download_random_10_minutes(url, output_folder):
    # Tạo thư mục nếu nó chưa tồn tại trên máy
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        print(f"Đã tạo thư mục: {output_folder}")

    # Thời lượng muốn tải: 10 phút = 600 giây
    download_duration = 600 
    
    # 1. Cấu hình để lấy thông tin video
    ydl_opts_info = {
        'quiet': True,
        'noplaylist': True # Bỏ qua danh sách phát
    }

    print("Đang lấy thông tin video từ YouTube...")
    with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
            total_duration = info.get('duration', 0)
        except Exception as e:
            print(f"Lỗi khi lấy thông tin: {e}")
            return

    if total_duration == 0:
        print("Không thể xác định được thời lượng video (có thể là video trực tiếp).")
        return

    # 2. Tính toán khoảng thời gian ngẫu nhiên 10 phút
    if total_duration > download_duration:
        start_time = random.randint(0, total_duration - download_duration)
        end_time = start_time + download_duration
    else:
        start_time = 0
        end_time = total_duration

    print(f"Tổng thời lượng video: {total_duration} giây.")
    print(f"Đã chọn ngẫu nhiên đoạn từ {start_time}s đến {end_time}s.")

    # Tạo template đường dẫn lưu file đầu ra
    # Ví dụ: C:\Users\ADMIN\Desktop\...\Tên_video_random_100s_to_700s.mp4
    output_template = os.path.join(output_folder, f'%(title)s_random_{start_time}s_to_{end_time}s.%(ext)s')

    # 3. Cấu hình yt-dlp
    ydl_opts_download = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best', 
        'noplaylist': True,
        'download_ranges': yt_dlp.utils.download_range_func(None, [(start_time, end_time)]),
        'force_keyframes_at_cuts': True, 
        'outtmpl': output_template # Chuyển đường dẫn thư mục vào đây
    }

    # 4. Bắt đầu tải
    print(f"Bắt đầu tải xuống vào thư mục:\n{output_folder}")
    with yt_dlp.YoutubeDL(ydl_opts_download) as ydl:
        ydl.download([url])
    
    print("\n✅ Tải xuống hoàn tất! Hãy kiểm tra thư mục của bạn.")

if __name__ == "__main__":
    video_url = "https://www.youtube.com/watch?v=B30S0Vr9N9A&list=RDB30S0Vr9N9A"
    
    # Sử dụng chữ 'r' ở trước chuỗi (raw string) để Python không bị lỗi với các dấu \ trong đường dẫn Windows
    save_path = r"C:\Users\ADMIN\Desktop\python_code\python\outsource\system\video"
    
    download_random_10_minutes(video_url, save_path)