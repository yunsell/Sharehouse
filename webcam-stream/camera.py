import sys
import threading
import time

import cv2

# 마지막 시청자가 나간 뒤 카메라를 끄기까지 기다리는 시간 (새로고침 대비)
IDLE_GRACE_SECONDS = 3
RETRY_SECONDS = 1


class Camera:
    """웹캠을 읽어 최신 JPEG 한 장을 보관합니다. 시청자가 있을 때만 카메라를 켭니다."""

    def __init__(self, index=0, width=640, height=480, fps=15, jpeg_quality=70):
        self.index = index
        self.width = width
        self.height = height
        self.frame_interval = 1 / fps
        self.jpeg_quality = jpeg_quality

        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread = None
        self._viewers = 0
        self._last_viewer_at = float("-inf")
        self._seq = 0
        self._jpeg = None
        self._is_open = False

    def start(self):
        self._thread = threading.Thread(target=self._run, name="camera", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._wake.set()
        if self._thread:
            self._thread.join(timeout=5)

    def add_viewer(self):
        with self._lock:
            self._viewers += 1
            count = self._viewers
        self._wake.set()
        return count

    def remove_viewer(self):
        with self._lock:
            self._viewers = max(0, self._viewers - 1)
            self._last_viewer_at = time.monotonic()
            return self._viewers

    @property
    def viewers(self):
        with self._lock:
            return self._viewers

    @property
    def is_open(self):
        with self._lock:
            return self._is_open

    def latest(self):
        """(프레임 번호, JPEG 바이트)를 돌려줍니다. 카메라가 꺼져 있으면 JPEG는 None입니다."""
        with self._lock:
            return self._seq, self._jpeg

    def _should_run(self):
        with self._lock:
            if self._viewers > 0:
                return True
            return time.monotonic() - self._last_viewer_at < IDLE_GRACE_SECONDS

    def _open(self):
        # Windows 기본 백엔드(MSMF)는 여는 데 오래 걸려 DirectShow를 사용합니다.
        backend = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY
        capture = cv2.VideoCapture(self.index, backend)
        if not capture.isOpened():
            capture.release()
            return None
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        return capture

    def _set_open(self, is_open):
        with self._lock:
            self._is_open = is_open
            if not is_open:
                # 카메라가 꺼진 뒤 예전 화면이 전송되지 않도록 지웁니다.
                self._jpeg = None

    def _run(self):
        capture = None
        last_encoded = 0.0
        error_reported = False

        try:
            while not self._stop.is_set():
                if not self._should_run():
                    if capture is not None:
                        capture.release()
                        capture = None
                        self._set_open(False)
                        print("[카메라] 꺼짐", flush=True)
                    self._wake.clear()
                    # clear와 대기 사이에 들어온 시청자를 놓치지 않도록 다시 확인합니다.
                    if not self._should_run():
                        self._wake.wait(timeout=1)
                    continue

                if capture is None:
                    capture = self._open()
                    if capture is None:
                        if not error_reported:
                            print(
                                f"[오류] 카메라 {self.index}번을 열 수 없습니다. "
                                "다른 프로그램이 사용 중인지 확인해주세요.",
                                flush=True,
                            )
                            error_reported = True
                        time.sleep(RETRY_SECONDS)
                        continue
                    self._set_open(True)
                    error_reported = False
                    print("[카메라] 켜짐", flush=True)

                ok, frame = capture.read()
                if not ok:
                    print("[오류] 카메라에서 영상을 읽지 못했습니다. 다시 연결합니다.", flush=True)
                    capture.release()
                    capture = None
                    self._set_open(False)
                    time.sleep(RETRY_SECONDS)
                    continue

                # 프레임은 계속 읽어 버퍼를 비우고, 인코딩은 설정한 FPS만큼만 합니다.
                now = time.monotonic()
                if now - last_encoded < self.frame_interval:
                    continue
                last_encoded = now

                ok, encoded = cv2.imencode(
                    ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality]
                )
                if ok:
                    with self._lock:
                        self._seq += 1
                        self._jpeg = encoded.tobytes()
        finally:
            if capture is not None:
                capture.release()
            self._set_open(False)
