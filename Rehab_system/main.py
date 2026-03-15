import cv2
import numpy as np
from camera_module.pose_engine import PoseEngine
from camera_module.exercise_logic import RepCounter
from evaluation.session_data import EvaluationLogger


def draw_level_bar(frame, x, y, angle, side_color):
    """Vẽ thanh mức độ (HP bar) dựa trên góc co tay (Game Interaction)"""
    # Chuyển đổi góc: 30 độ (co hết cỡ) -> 100%, 160 độ (duỗi thẳng) -> 0%
    percent = np.interp(angle, [30, 160], [100, 0])
    bar_height = 150  # Độ cao thanh bar
    bar_width = 20

    # 1. Vẽ khung thanh bar (viền trắng)
    cv2.rectangle(frame, (x, y), (x + bar_width, y + bar_height), (255, 255, 255), 2)

    # 2. Tính toán phần tô màu (từ dưới lên trên)
    fill_h = int(np.interp(percent, [0, 100], [0, bar_height]))
    cv2.rectangle(frame, (x, y + bar_height - fill_h),
                  (x + bar_width, y + bar_height), side_color, -1)

    # 3. Hiển thị phần trăm
    cv2.putText(frame, f"{int(percent)}%", (x - 5, y - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)


def main():
    # --- MÀN HÌNH NHẬP HỒ SƠ ---
    print("=" * 30)
    print(" HE THONG PHUC HOI CHUC NANG ")
    print("=" * 30)
    user_name = input("Nhap ID hoac Ten Benh Nhan: ").strip()
    if not user_name: user_name = "User_Unknown"

    # --- KHỞI TẠO CÁC MODULE ---
    cap = cv2.VideoCapture(0)
    # RPi4 nên dùng complexity=0 hoặc 1
    engine = PoseEngine(complexity=1)
    counter_manager = RepCounter()
    logger = EvaluationLogger(user_id="SinhVien_VKU")

    frame_count = 0
    print("He thong dang chay... Nhan 'q' de thoat va luu bao cao.")

    while cap.isOpened():
        success, frame = cap.read()
        if not success:
            break

        # A. Xử lý hình ảnh cơ bản
        frame = cv2.flip(frame, 1)  # Lật ảnh giống gương
        h, w, _ = frame.shape

        # --- VẼ ĐỒNG HỒ BẤM GIỜ (TIMER) ---
        timer_str = counter_manager.get_elapsed_time()
        # Tạo nền đen cho đồng hồ (Header bar)
        cv2.rectangle(frame, (w // 2 - 60, 0), (w // 2 + 60, 40), (0, 0, 0), -1)
        # Vẽ chữ Timer
        cv2.putText(frame, timer_str, (w // 2 - 45, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
        cv2.putText(frame, "TIME", (w // 2 - 20, 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 255, 255), 1)

        # B. Nhận diện Pose
        results = engine.extract_landmarks(frame)

        if results.pose_landmarks:
            # Định nghĩa các khớp: (Tên hiển thị, Vai, Khuỷu, Cổ tay, Màu sắc)
            # Lưu ý: Đã đảo ngược nhãn 11-13-15 thành Right Arm sau khi flip ảnh
            arms = [
                ("Right Arm", 11, 13, 15, (255, 200, 0)),  # Màu vàng
                ("Left Arm", 12, 14, 16, (0, 255, 0))  # Màu xanh lá
            ]

            for side_name, s_idx, e_idx, w_idx, color in arms:
                lm = results.pose_landmarks.landmark

                # 1. Lấy tọa độ Pixel
                s = [lm[s_idx].x * w, lm[s_idx].y * h]
                e = [lm[e_idx].x * w, lm[e_idx].y * h]
                w_pt = [lm[w_idx].x * w, lm[w_idx].y * h]

                # 2. Tính góc khớp khuỷu
                angle = engine.calculate_angle(s, e, w_pt)

                # 3. Cập nhật logic đếm Rep (Dùng key 'left'/'right' nội bộ)
                side_key = "left" if "Left" in side_name else "right"
                reps, status = counter_manager.update(side_key, angle)

                # 4. Ghi Log dữ liệu (Cứ mỗi 3 frames ghi 1 lần để tối ưu CPU)
                #if frame_count % 3 == 0:
                #    logger.log_frame(side_name, angle, reps, status)

                # 5. HIỂN THỊ GIAO DIỆN GAME
                e_x, e_y = int(e[0]), int(e[1])

                # Vẽ thanh HP bar cạnh khuỷu tay
                draw_level_bar(frame, e_x + 30, e_y - 75, angle, color)

                # Vẽ thông số góc ngay tại khớp
                cv2.putText(frame, f"{int(angle)} deg", (e_x - 60, e_y + 20),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

                # Hiển thị bảng Reps cố định góc màn hình
                y_offset = 50 if "Right" in side_name else 110
                cv2.rectangle(frame, (10, y_offset - 30), (220, y_offset + 20), (0, 0, 0), -1)  # Nền đen cho dễ đọc
                cv2.putText(frame, f"{side_name}: {reps} Reps", (20, y_offset),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
                cv2.putText(frame, f"State: {status}", (20, y_offset + 15),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)

            # Vẽ bộ khung xương (Landmarks)
            engine.mp_drawing.draw_landmarks(
                frame, results.pose_landmarks, engine.mp_pose.POSE_CONNECTIONS,
                engine.mp_drawing.DrawingSpec(color=(245, 117, 66), thickness=2, circle_radius=2),
                engine.mp_drawing.DrawingSpec(color=(245, 66, 230), thickness=2, circle_radius=2)
            )

        # C. Hiển thị màn hình chính
        cv2.imshow("VKU Rehab System", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'): break

        frame_count += 1
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # --- KẾT THÚC VÀ LƯU TRỮ ---
    print("Dang phan tich du lieu va luu ho so y te...")

    # Lấy thống kê từ bộ đếm
    left_info = counter_manager.get_summary("left")
    right_info = counter_manager.get_summary("right")

    # Lưu báo cáo chuyên sâu vào thư mục riêng của người dùng
    logger.save_medical_report(left_info, right_info)

    cap.release()
    cv2.destroyAllWindows()
    print("Da thoat he thong an toan.")


if __name__ == "__main__":
    main()