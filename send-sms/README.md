# Send SMS

알리고(Aligo) API로 엑셀 수신자 목록에 대량 문자를 발송하는 모듈입니다.

## 설치

```bash
pip install requests openpyxl python-dotenv
```

## 사전 준비 (알리고 사이트)

1. API Key 발급
2. 발신번호 등록 (등록된 번호로만 발송 가능)
3. 발송 서버 IP 등록 (코드를 실행하는 PC의 공인 IP)
4. 충전

## 파일 구성

| 파일 | 내용 |
|------|------|
| `aligo_sms.py` | 발송 함수 모듈 (import해서 사용) |
| `main.py` | 엑셀 + 문자 파일로 발송하는 실행 예시 |
| `message_example.txt` | 문자 내용 예시 |
| `.env.example` | 설정 양식 |

## 함수로 사용하기

```python
from aligo_sms import get_remain, read_recipients, send_bulk_sms

# 인증 확인 (API 키, 아이디, IP 등록) + 잔여 건수
print(get_remain("API_KEY", "ALIGO_ID"))

# 엑셀에서 수신자 읽기 → [("홍길동", "01012345678"), ...]
recipients = read_recipients("recipients.xlsx", name_col="A", phone_col="B", start_row=2)

result = send_bulk_sms(
    api_key="API_KEY",
    user_id="ALIGO_ID",
    sender="0212345678",          # 등록된 발신번호
    recipients=recipients,
    msg_template="{name}님 안녕하세요.",
    title="[회사명] 안내",          # LMS일 때만 적용
    test_mode=True,               # True면 실제 발송 안 됨
)
print(result)  # {"success": 2, "fail": 0, "msg_type": "SMS", "msg_ids": [...]}
```

| 함수 | 설명 |
|------|------|
| `get_remain(api_key, user_id)` | 잔여 건수 조회. `result_code`가 1이면 인증 성공 |
| `read_recipients(excel_path, name_col, phone_col, start_row)` | 엑셀에서 `(이름, 번호)` 목록 읽기. 하이픈 제거, 앞자리 0 보정, 형식 오류·중복 제외 |
| `send_bulk_sms(...)` | 수신자별 치환 후 500건 단위로 발송. 90바이트 초과 시 자동 LMS |
| `normalize_phone(value)` | 번호를 `01012345678` 형태로 정리 (올바르지 않으면 `None`) |

## 실행 예시로 사용하기

1. `.env.example`을 `.env`로 복사한 뒤 `ALIGO_API_KEY`, `ALIGO_USER_ID`, `ALIGO_SENDER`를 입력합니다.
2. 문자 내용 파일을 만들고 `MSG_PATH`에 지정합니다 (기본: `message_example.txt`).
3. 수신자 엑셀을 만들고 `EXCEL_PATH`에 지정합니다 (기본: `recipients.xlsx`).
4. 실행합니다.

```bash
python main.py
```

인증 확인 → 잔여 건수와 미리보기 출력 → `y` 입력 시 발송합니다.

`TEST_MODE=Y`(기본값)이면 알리고 테스트모드로 요청하므로 실제로 발송되지 않습니다. 처음에는 엑셀에 본인 번호만 넣고 실제 발송으로 내용을 확인한 뒤, 실제 수신자 목록으로 바꾸는 것을 권장합니다.

## 엑셀 파일 형식

| A (이름) | B (전화번호) |
|---------|-------------|
| 이름    | 전화번호     |
| 홍길동  | 010-0000-0000 |

## 문자 내용

사용 가능한 변수:
- `{name}` - A열 이름
- `{phone}` - B열 전화번호 (하이픈 없이)

광고성 문자는 맨 앞에 `(광고)`, 끝에 무료 수신거부 방법을 넣어야 합니다.
