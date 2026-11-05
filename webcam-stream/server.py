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
main { display: grid; gap: 16px; max-width: 960px; margin: 0 auto; padding: 0 16px 16px;
       grid-template-columns: repeat(auto-fit, minmax(min(100%, 320px), 1fr)); }
main.multi { max-width: 1600px; }
figure { margin: 0; min-width: 0; }
figcaption { padding-bottom: 6px; color: #aaa; font-size: 14px; }
figure img { display: block; width: 100%; background: #000; }
.status { text-align: center; color: #aaa; min-height: 1.5em; margin: 8px 0 0; }
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
<main class="{main_class}">{feeds}</main>
<script>
// 브라우저는 img 태그의 MJPEG가 끊겨도 오류를 알려주지 않으므로, 스트림을 직접 읽어 끊김을 감지합니다.
const FRAME_TIMEOUT_MS = 12000;
const RETRY_MS = 3000;
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function findMarker(bytes, second, from) {{
  for (let i = from; i < bytes.length - 1; i++) {{
    if (bytes[i] === 0xff && bytes[i + 1] === second) return i;
  }}
  return -1;
}}

function showFrame(video, frame) {{
  const previous = video.src;
  video.src = URL.createObjectURL(new Blob([frame], {{ type: "image/jpeg" }}));
  if (previous) URL.revokeObjectURL(previous);
}}

async function readStream(feed, signal, onFrame) {{
  const response = await fetch(feed, {{ signal }});
  if (response.status === 401) {{ location.href = "/login"; return; }}
  if (!response.ok) return;
  const reader = response.body.getReader();
  let buffer = new Uint8Array(0);
  while (true) {{
    const {{ done, value }} = await reader.read();
    if (done) return;
    const merged = new Uint8Array(buffer.length + value.length);
    merged.set(buffer);
    merged.set(value, buffer.length);
    buffer = merged;
    while (true) {{
      const start = findMarker(buffer, 0xd8, 0);
      const end = start < 0 ? -1 : findMarker(buffer, 0xd9, start + 2);
      if (end < 0) break;
      onFrame(buffer.slice(start, end + 2));
      buffer = buffer.slice(end + 2);
    }}
  }}
}}

async function play(figure) {{
  const video = figure.querySelector("img");
  const statusText = figure.querySelector(".status");
  while (true) {{
    const controller = new AbortController();
    let watchdog;
    const resetWatchdog = () => {{
      clearTimeout(watchdog);
      watchdog = setTimeout(() => controller.abort(), FRAME_TIMEOUT_MS);
    }};
    resetWatchdog();
    try {{
      await readStream(video.dataset.stream, controller.signal, (frame) => {{
        resetWatchdog();
        statusText.textContent = "";
        showFrame(video, frame);
      }});
    }} catch (e) {{}}
    clearTimeout(watchdog);
    controller.abort();
    statusText.textContent = "영상을 불러오지 못했습니다. 다시 연결하는 중입니다.";
    await sleep(RETRY_MS);
  }}
}}

document.querySelectorAll("figure").forEach(play);
</script></body></html>"""

FEED_TEMPLATE = """<figure>{caption}<img alt="{label} 영상" data-stream="/stream/{position}">
<p class="status"></p></figure>"""


def create_app(cameras, password, max_viewers=3, session_hours=12):
    """로그인과 MJPEG 스트리밍을 제공하는 FastAPI 앱을 만듭니다."""
    sessions = {}  # 토큰 -> 만료 시각. 서버를 재시작하면 모두 로그아웃됩니다.
    login_failures = []
    session_seconds = int(session_hours * 3600)
    password_bytes = password.encode("utf-8")

    @asynccontextmanager
    async def lifespan(app):
        for camera in cameras:
            camera.start()
        yield
        for camera in cameras:
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

    def viewer_page():
        # 카메라가 1대면 이름표 없이 화면 하나만 보여줍니다.
        feeds = []
        for position in range(len(cameras)):
            label = f"카메라 {position + 1}"
            caption = f"<figcaption>{label}</figcaption>" if len(cameras) > 1 else ""
            feeds.append(FEED_TEMPLATE.format(caption=caption, label=label, position=position))
        return VIEWER_PAGE.format(
            style=PAGE_STYLE,
            main_class="multi" if len(cameras) > 1 else "",
            feeds="".join(feeds),
        )

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        if not is_logged_in(request):
            return RedirectResponse("/login", status_code=303)
        return HTMLResponse(viewer_page())

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
        return {
            "cameras": [
                {"viewers": camera.viewers, "camera_on": camera.is_open} for camera in cameras
            ]
        }

    async def frames(camera, token, ip):
        count = camera.add_viewer()
        print(f"[시청] 카메라 {camera.index} 시작 ({ip}), 현재 {count}명", flush=True)
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
                    print(f"[시청] 카메라 {camera.index}의 새 프레임이 없어 연결을 끊습니다.", flush=True)
                    break
                await asyncio.sleep(camera.frame_interval / 2)
        finally:
            print(f"[시청] 카메라 {camera.index} 종료 ({ip}), 현재 {camera.remove_viewer()}명", flush=True)

    @app.get("/stream/{position}")
    async def stream(request: Request, position: int):
        if not is_logged_in(request):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        if not 0 <= position < len(cameras):
            return JSONResponse({"error": "camera not found"}, status_code=404)
        camera = cameras[position]
        if camera.viewers >= max_viewers:
            return JSONResponse({"error": "too many viewers"}, status_code=503)
        return StreamingResponse(
            frames(camera, request.cookies[COOKIE_NAME], client_ip(request)),
            media_type=f"multipart/x-mixed-replace; boundary={BOUNDARY}",
            headers={"X-Accel-Buffering": "no"},
        )

    return app
