import os
import sys

import uvicorn
from dotenv import load_dotenv

from camera import Camera
from server import create_app

MIN_PASSWORD_LENGTH = 6
LOCAL_HOSTS = ("127.0.0.1", "localhost", "::1")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))


if __name__ == "__main__":
    password = os.getenv("WEBCAM_PASSWORD", "")
    if len(password) < MIN_PASSWORD_LENGTH:
        print(f"[오류] .env 파일의 WEBCAM_PASSWORD를 {MIN_PASSWORD_LENGTH}자 이상으로 설정해주세요.")
        sys.exit(1)

    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "5177"))

    camera = Camera(
        index=int(os.getenv("CAMERA_INDEX", "0")),
        width=int(os.getenv("FRAME_WIDTH", "640")),
        height=int(os.getenv("FRAME_HEIGHT", "480")),
        fps=int(os.getenv("FPS", "15")),
        jpeg_quality=int(os.getenv("JPEG_QUALITY", "70")),
    )
    app = create_app(
        camera,
        password,
        max_viewers=int(os.getenv("MAX_VIEWERS", "3")),
        session_hours=float(os.getenv("SESSION_HOURS", "12")),
    )

    if host not in LOCAL_HOSTS:
        print(f"[주의] {host}에 직접 공개합니다. 비밀번호와 영상이 암호화되지 않으니 HTTPS 터널 사용을 권장합니다.")
    print(f"웹캠 서버: http://{host}:{port} (종료: Ctrl+C)", flush=True)
    print("시청자가 있을 때만 카메라가 켜집니다.", flush=True)

    uvicorn.run(app, host=host, port=port, access_log=False, timeout_graceful_shutdown=2)
