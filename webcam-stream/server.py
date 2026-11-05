import asyncio
import hmac
import secrets
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse

COOKIE_NAME = "webcam_session"
BOUNDARY = "frame"
# 이 시간 동안 새 프레임이 없으면 스트림을 끊습니다. 페이지가 다시 연결을 시도합니다.
STALL_TIMEOUT_SECONDS = 10
MAX_LOGIN_FAILURES = 5
LOGIN_LOCK_SECONDS = 300

PAGE_STYLE = """
:root { color-scheme: dark; }
* { box-sizing: border-box; }
body { margin: 0; min-height: 100vh; background: #111; color: #eee;
       font-family: system-ui, "Malgun Gothic", sans-serif; }
form.login { max-width: 320px; margin: 18vh auto 0; padding: 0 16px; display: grid; gap: 12px; }
input, button { font: inherit; padding: 10px 12px; border-radius: 6px; border: 1px solid #444; }
input { background: #1c1c1c; color: inherit; }
button { background: #2d2d2d; color: inherit; cursor: pointer; }
.error { color: #ff8a80; margin: 0; }
header { display: flex; justify-content: space-between; align-items: center;
         padding: 10px 16px; gap: 12px; }
header h1 { font-size: 16px; font-weight: 600; margin: 0; }
header form { margin: 0; }
main { padding: 0 16px 16px; }
main img { display: block; width: 100%; max-width: 960px; margin: 0 auto; background: #000; }
#status { text-align: center; color: #aaa; min-height: 1.5em; }
"""

LOGIN_PAGE = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>웹캠 로그인</title><style>{style}</style></head>
<body><form class="login" method="post" action="/login">
<h1>웹캠 로그인</h1>{error}
<input type="password" name="password" placeholder="비밀번호" autocomplete="current-password" autofocus required>
<button type="submit">로그인</button>
</form></body></html>"""

VIEWER_PAGE = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>웹캠</title><style>{style}</style></head>
<body>
<header><h1>웹캠</h1>
<form method="post" action="/logout"><button type="submit">로그아웃</button></form></header>
<main><img id="video" alt="웹캠 영상" src="/stream"><p id="status"></p></main>
<script>
const video = document.getElementById("video");
const statusText = document.getElementById("status");
video.addEventListener("load", () => {{ statusText.textContent = ""; }});
video.addEventListener("error", async () => {{
  statusText.textContent = "영상 연결이 끊겼습니다. 다시 연결하는 중입니다.";
  try {{
    const response = await fetch("/api/status");
    if (response.status === 401) {{ location.href = "/login"; return; }}
  }} catch (e) {{}}
  setTimeout(() => {{ video.src = "/stream?t=" + Date.now(); }}, 3000);
}});
</script></body></html>"""


def create_app(camera, password, max_viewers=3, session_hours=12):
    """로그인과 MJPEG 스트리밍을 제공하는 FastAPI 앱을 만듭니다."""
    sessions = {}  # 토큰 -> 만료 시각. 서버를 재시작하면 모두 로그아웃됩니다.
    login_failures = []
    session_seconds = int(session_hours * 3600)
    password_bytes = password.encode("utf-8")

    @asynccontextmanager
    async def lifespan(app):
        camera.start()
        yield
        camera.stop()

    # 자동 생성 API 문서는 외부에 공개하지 않습니다.
    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    def client_ip(request):
        # Cloudflare Tunnel 뒤에서는 실제 접속자 IP가 이 헤더로 전달됩니다 (기록용).
        return request.headers.get("cf-connecting-ip") or (
            request.client.host if request.client else "unknown"
        )

    def is_valid(token):
        if not token:
            return False
        expires_at = sessions.get(token)
        if expires_at is None:
            return False
        if expires_at <= time.time():
            sessions.pop(token, None)
            return False
        return True

    def is_logged_in(request):
        return is_valid(request.cookies.get(COOKIE_NAME))

    def is_locked():
        cutoff = time.time() - LOGIN_LOCK_SECONDS
        login_failures[:] = [t for t in login_failures if t > cutoff]
        return len(login_failures) >= MAX_LOGIN_FAILURES

    def login_page(error="", status_code=200):
        error_html = f'<p class="error">{error}</p>' if error else ""
        html = LOGIN_PAGE.format(style=PAGE_STYLE, error=error_html)
        return HTMLResponse(html, status_code=status_code)

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        if not is_logged_in(request):
            return RedirectResponse("/login", status_code=303)
        return HTMLResponse(VIEWER_PAGE.format(style=PAGE_STYLE))

    @app.get("/login", response_class=HTMLResponse)
    async def login_form(request: Request):
        if is_logged_in(request):
            return RedirectResponse("/", status_code=303)
        return login_page()

    @app.post("/login")
    async def login(request: Request, password: str = Form("")):
        ip = client_ip(request)
        if is_locked():
            print(f"[로그인] 잠금 상태에서 시도 차단 ({ip})", flush=True)
            return login_page("시도가 너무 많습니다. 5분 뒤 다시 시도해주세요.", 429)

        if not hmac.compare_digest(password.encode("utf-8"), password_bytes):
            login_failures.append(time.time())
            print(f"[로그인] 실패 ({ip})", flush=True)
            return login_page("비밀번호가 올바르지 않습니다.", 401)

        now = time.time()
        for token, expires_at in list(sessions.items()):
            if expires_at <= now:
                del sessions[token]

        token = secrets.token_urlsafe(32)
        sessions[token] = now + session_seconds
        print(f"[로그인] 성공 ({ip})", flush=True)

        response = RedirectResponse("/", status_code=303)
        is_https = (
            request.headers.get("x-forwarded-proto") == "https"
            or request.url.scheme == "https"
        )
        response.set_cookie(
            COOKIE_NAME,
            token,
            max_age=session_seconds,
            httponly=True,
            samesite="lax",
            secure=is_https,
        )
        return response

    @app.post("/logout")
    async def logout(request: Request):
        sessions.pop(request.cookies.get(COOKIE_NAME), None)
        response = RedirectResponse("/login", status_code=303)
        response.delete_cookie(COOKIE_NAME)
        return response

    @app.get("/api/status")
    async def status(request: Request):
        if not is_logged_in(request):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        return {"viewers": camera.viewers, "camera_on": camera.is_open}

    async def frames(token, ip):
        count = camera.add_viewer()
        print(f"[시청] 시작 ({ip}), 현재 {count}명", flush=True)
        last_seq = -1
        last_frame_at = time.monotonic()
        try:
            # 로그아웃하거나 세션이 만료되면 보던 영상도 바로 끊깁니다.
            while is_valid(token):
                seq, jpeg = camera.latest()
                if jpeg is not None and seq != last_seq:
                    last_seq = seq
                    last_frame_at = time.monotonic()
                    yield (
                        f"--{BOUNDARY}\r\nContent-Type: image/jpeg\r\n"
                        f"Content-Length: {len(jpeg)}\r\n\r\n"
                    ).encode("ascii") + jpeg + b"\r\n"
                elif time.monotonic() - last_frame_at > STALL_TIMEOUT_SECONDS:
                    print("[시청] 새 프레임이 없어 연결을 끊습니다.", flush=True)
                    break
                await asyncio.sleep(camera.frame_interval / 2)
        finally:
            print(f"[시청] 종료 ({ip}), 현재 {camera.remove_viewer()}명", flush=True)

    @app.get("/stream")
    async def stream(request: Request):
        if not is_logged_in(request):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        if camera.viewers >= max_viewers:
            return JSONResponse({"error": "too many viewers"}, status_code=503)
        return StreamingResponse(
            frames(request.cookies[COOKIE_NAME], client_ip(request)),
            media_type=f"multipart/x-mixed-replace; boundary={BOUNDARY}",
            headers={"X-Accel-Buffering": "no"},
        )

    return app
