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


def parse_camera_indexes(value):
    """"0,1" 같은 값을 [0, 1]로 바꿉니다. 형식이 틀리거나 번호가 겹치면 None을 돌려줍니다."""
    try:
        indexes = [int(part) for part in value.split(",")]
    except ValueError:
        return None
    if min(indexes) < 0 or len(set(indexes)) != len(indexes):
        return None
    return indexes


if __name__ == "__main__":
    password = os.getenv("WEBCAM_PASSWORD", "")
    if len(password) < MIN_PASSWORD_LENGTH:
        print(f"[오류] .env 파일의 WEBCAM_PASSWORD를 {MIN_PASSWORD_LENGTH}자 이상으로 설정해주세요.")
        sys.exit(1)

    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "5177"))

    camera_indexes = parse_camera_indexes(os.getenv("CAMERA_INDEX", "0"))
    if camera_indexes is None:
        print("[오류] .env 파일의 CAMERA_INDEX는 0 또는 0,1처럼 겹치지 않는 번호로 입력해주세요.")
        sys.exit(1)

    cameras = [
        Camera(
            index=index,
            width=int(os.getenv("FRAME_WIDTH", "640")),
            height=int(os.getenv("FRAME_HEIGHT", "480")),
            fps=int(os.getenv("FPS", "15")),
            jpeg_quality=int(os.getenv("JPEG_QUALITY", "70")),
        )
        for index in camera_indexes
    ]
    app = create_app(
        cameras,
        password,
        max_viewers=int(os.getenv("MAX_VIEWERS", "3")),
        session_hours=float(os.getenv("SESSION_HOURS", "12")),
    )

    if host not in LOCAL_HOSTS:
        print(f"[주의] {host}에 직접 공개합니다. 비밀번호와 영상이 암호화되지 않으니 HTTPS 터널 사용을 권장합니다.")
    print(f"웹캠 서버: http://{host}:{port} (종료: Ctrl+C)", flush=True)
    print(f"사용할 카메라: {camera_indexes}. 시청자가 있을 때만 켜집니다.", flush=True)

    uvicorn.run(app, host=host, port=port, access_log=False, timeout_graceful_shutdown=2)
