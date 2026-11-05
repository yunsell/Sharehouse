# Webcam Stream

내 컴퓨터의 웹캠을 비밀번호로 보호된 웹페이지에서 실시간으로 보는 모듈입니다. Cloudflare Tunnel을 함께 쓰면 공유기 설정 없이 외부에서 접속할 수 있습니다.

## 설치

```bash
pip install -r requirements.txt
```

외부 접속에 쓸 cloudflared도 설치합니다 (Windows 기준). 설치 후 터미널을 새로 열어야 명령을 찾을 수 있습니다.

```bash
winget install --id Cloudflare.cloudflared
```

## 파일 구성

| 파일 | 내용 |
|------|------|
| `camera.py` | 웹캠을 읽어 JPEG로 변환하는 모듈 |
| `server.py` | 로그인과 영상 스트리밍을 제공하는 웹 서버 |
| `main.py` | `.env`를 읽어 서버를 실행하는 진입점 |
| `tunnel.py` | Cloudflare 임시 터널을 실행하고 주소를 `tunnel_url.txt`에 저장 |
| `start_webcam.bat` | Windows 서버 자동 실행용 스크립트 |
| `start_tunnel.bat` | Windows 터널 자동 실행용 스크립트 |
| `.env.example` | 설정 양식 |

## 실행

1. `.env.example`을 `.env`로 복사한 뒤 `WEBCAM_PASSWORD`를 6자 이상으로 입력합니다. 짧게 쓴다면 추측하기 어려운 무작위 조합을 사용하세요.
2. 서버를 실행합니다.

```bash
python main.py
```

3. 같은 컴퓨터의 브라우저에서 `http://127.0.0.1:5177`에 접속해 영상을 확인합니다.

## 웹캠 여러 대 보기

웹캠을 연결한 뒤 `.env`의 `CAMERA_INDEX`에 번호를 쉼표로 구분해 입력하고 서버를 재시작하면, 한 페이지에 화면이 나란히 나옵니다.

```
CAMERA_INDEX=0,1
```

- **카메라 번호:** 내장 카메라가 보통 0번입니다. 화면이 나오지 않는 번호가 있으면 다른 번호로 바꿔 봅니다.
- **데이터 사용량:** 카메라 수만큼 늘어납니다. 부담되면 `FPS`나 `JPEG_QUALITY`를 낮춥니다.
- **USB 연결:** USB 웹캠 여러 대를 같은 허브에 꽂으면 대역폭이 부족해 일부가 켜지지 않을 수 있습니다. 포트를 나눠 꽂거나 해상도를 낮춥니다.

## 외부에서 접속하기

서버를 켜 둔 채로 다른 터미널에서 실행합니다.

```bash
python tunnel.py
```

출력에 나오는 `https://...trycloudflare.com` 주소로 어디서든 접속할 수 있습니다. 같은 주소가 `tunnel_url.txt`에도 저장됩니다. 이 주소는 실행할 때마다 바뀌고, 터널을 끄면 외부 접속이 바로 끊깁니다.

고정 주소가 필요하면 Cloudflare에 등록한 도메인으로 [이름 있는 터널](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/)을 만듭니다. 이때 [Cloudflare Access](https://developers.cloudflare.com/cloudflare-one/policies/access/)로 허용할 이메일을 지정하면 비밀번호 앞에 보호 단계를 하나 더 둘 수 있습니다.

### 포트포워딩으로 접속하기

터널 대신 공유기 포트포워딩을 쓸 수도 있습니다. 이 방식은 비밀번호와 영상이 암호화되지 않으므로 공용 와이파이에서는 사용하지 마세요.

1. `.env`에서 `HOST=0.0.0.0`으로 바꾸고 서버를 재시작합니다.
2. 공유기에서 외부 포트를 이 컴퓨터의 내부 IP와 `PORT`로 연결합니다. 내부 IP는 공유기에서 고정해 두는 것을 권장합니다.
3. Windows 방화벽에서 해당 포트나 Python의 인바운드 연결을 허용합니다.
4. `http://공인IP:외부포트`로 접속합니다.

## 자동 실행 (Windows)

시작프로그램 폴더에 바로가기를 넣으면 Windows에 로그인할 때 서버와 터널이 최소화된 창으로 실행됩니다. 이 스크립트들은 저장소 최상위의 `.venv`를 사용합니다.

```powershell
$shell = New-Object -ComObject WScript.Shell
$startup = [Environment]::GetFolderPath('Startup')
foreach ($item in @(@('Webcam Server', 'start_webcam.bat'), @('Webcam Tunnel', 'start_tunnel.bat'))) {
    $link = $shell.CreateShortcut("$startup\$($item[0]).lnk")
    $link.TargetPath = (Resolve-Path ".\$($item[1])").Path
    $link.WorkingDirectory = (Get-Location).Path
    $link.WindowStyle = 7
    $link.Save()
}
```

- **외부 주소 확인:** 재부팅할 때마다 주소가 바뀝니다. 작업 표시줄의 `Webcam Tunnel` 창이나 `tunnel_url.txt`에서 확인합니다.
- **중지:** 작업 표시줄의 `Webcam Server`, `Webcam Tunnel` 창을 닫습니다. 터널 창만 닫으면 외부 접속만 끊깁니다.
- **자동 실행 해제:** 시작프로그램 폴더에서 두 바로가기를 삭제합니다.
- **로그인 필요:** 웹캠은 사용자 세션에서 접근하므로 전원을 켠 뒤 로그인해야 실행됩니다.
- **절전 모드:** 절전 상태에서는 접속되지 않습니다. 외부에서 보려면 전원을 연결하고 절전을 꺼 둡니다.

## 보안 동작

- **로컬 전용 실행:** 기본값은 `127.0.0.1`이라 터널을 거쳐야만 외부에서 접근할 수 있습니다.
- **비밀번호 필수:** 비밀번호가 없거나 6자 미만이면 서버가 시작되지 않습니다.
- **로그인 제한:** 5분 안에 5번 틀리면 5분 동안 모든 로그인이 차단됩니다. 이 제한은 접속자별이 아니라 서버 전체에 적용되므로, 공격을 받으면 본인도 로그인하지 못할 수 있습니다. 이때는 서버를 재시작하면 풀립니다.
- **세션 관리:** 로그아웃하거나 로그인 시간이 만료되면 보던 영상도 끊깁니다. 서버를 재시작하면 모두 로그아웃됩니다.
- **카메라 자동 제어:** 시청자가 있을 때만 카메라가 켜지고, 모두 나가면 3초 뒤 꺼집니다. 터널로 접속했다면 연결 종료가 늦게 전달되어 꺼지기까지 30초 정도 걸릴 수 있습니다. 로그아웃하면 바로 끊깁니다.
- **기록:** 로그인과 시청 내역은 서버 터미널에 출력됩니다. 영상은 저장하지 않으며, 음성은 전송하지 않습니다.

## 주의사항

카메라에 다른 사람이나 공용 공간이 찍힐 수 있다면 미리 알리고 동의를 받으세요. 동의 없는 촬영은 법적 문제가 될 수 있습니다. 쓰지 않을 때는 터널과 서버를 모두 끄는 것을 권장합니다.

## 문제 해결

| 증상 | 확인할 내용 |
|------|-------------|
| `카메라 0번을 열 수 없습니다` | Zoom 같은 다른 프로그램이 카메라를 쓰고 있는지, Windows 설정의 개인 정보 > 카메라에서 데스크톱 앱 접근이 허용됐는지 확인합니다. 연결된 번호가 맞는지 `CAMERA_INDEX`도 확인합니다. |
| 영상이 끊기거나 느림 | `.env`에서 `FPS`, `JPEG_QUALITY`, `FRAME_WIDTH`, `FRAME_HEIGHT`를 낮춥니다. |
| `cloudflared` 명령을 찾을 수 없음 | 터미널을 새로 엽니다. |
