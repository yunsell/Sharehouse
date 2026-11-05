import os
import re
import shutil
import subprocess
import sys
import time

from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
URL_FILE = os.path.join(BASE_DIR, "tunnel_url.txt")
RETRY_SECONDS = 10
# 부팅 직후처럼 네트워크가 준비되기 전에는 터널 생성이 실패하므로 계속 다시 시도합니다.
URL_PATTERN = re.compile(r"https://(?!api\.)[a-z0-9-]+\.trycloudflare\.com")
DEFAULT_PATHS = (
    r"C:\Program Files (x86)\cloudflared\cloudflared.exe",
    r"C:\Program Files\cloudflared\cloudflared.exe",
)

load_dotenv(os.path.join(BASE_DIR, ".env"))


def find_cloudflared():
    found = shutil.which("cloudflared")
    if found:
        return found
    for path in DEFAULT_PATHS:
        if os.path.exists(path):
            return path
    return None


def clear_url_file():
    if os.path.exists(URL_FILE):
        os.remove(URL_FILE)


def run_once(cloudflared, port):
    """cloudflared를 실행하고 주소가 나오면 파일에 저장합니다. 터널이 끝나면 돌아옵니다."""
    process = subprocess.Popen(
        [cloudflared, "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{port}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    try:
        for line in process.stdout:
            print(line, end="", flush=True)
            match = URL_PATTERN.search(line)
            if match:
                url = match.group(0)
                with open(URL_FILE, "w", encoding="utf-8") as f:
                    f.write(url + "\n")
                print(f"\n[터널] 외부 접속 주소: {url}\n[터널] 저장 위치: {URL_FILE}\n", flush=True)
    finally:
        if process.poll() is None:
            process.terminate()
        process.wait()


if __name__ == "__main__":
    cloudflared = find_cloudflared()
    if not cloudflared:
        print("[오류] cloudflared를 찾을 수 없습니다. README의 설치 방법을 확인해주세요.")
        sys.exit(1)

    port = int(os.getenv("PORT", "5177"))
    try:
        while True:
            # 끊긴 터널의 주소가 남지 않도록 지운 뒤 시작합니다.
            clear_url_file()
            run_once(cloudflared, port)
            clear_url_file()
            print(f"[터널] 연결이 끝났습니다. {RETRY_SECONDS}초 뒤 다시 시도합니다.", flush=True)
            time.sleep(RETRY_SECONDS)
    except KeyboardInterrupt:
        clear_url_file()
