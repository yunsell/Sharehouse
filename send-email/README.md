# Send Email

Python으로 엑셀 수신자 목록에 HTML 이메일을 발송하는 모듈입니다.

## 설치

```bash
pip install openpyxl python-dotenv
```

## 파일 구성

| 파일 | 내용 |
|------|------|
| `mailer.py` | 발송 함수 모듈 (import해서 사용) |
| `main.py` | 엑셀 + HTML 파일로 발송하는 실행 예시 |
| `email_example.html` | HTML 템플릿 예시 |
| `.env.example` | 설정 양식 |

## 함수로 사용하기

```python
from mailer import send_html_email, send_bulk_from_excel

# 한 명에게 발송
send_html_email(
    sender_email="your@email.com",
    sender_password="your_password",
    recipient_email="to@example.com",
    subject="[회사명] 안내 메일",
    html_content="<p>안녕하세요</p>",
    smtp_server="smtps.hiworks.com",  # 기본값
    smtp_port=465,                    # 기본값
)

# 엑셀 목록으로 대량 발송
result = send_bulk_from_excel(
    sender_email="your@email.com",
    sender_password="your_password",
    excel_path="recipients.xlsx",
    subject="[회사명] 안내 메일",
    html_template=open("email_example.html", encoding="utf-8").read(),
    name_col="A",   # 이름 컬럼
    email_col="B",  # 이메일 컬럼
    start_row=2,    # 헤더 제외
    delay=1,        # 발송 간격 (초)
)
print(result)  # {"success": 2, "fail": 0}
```

## 실행 예시로 사용하기

1. `.env.example`을 `.env`로 복사한 뒤 발신자 정보와 SMTP 설정을 입력합니다.
2. HTML 템플릿을 만들고 `HTML_PATH`에 지정합니다 (기본: `email_example.html`).
3. 수신자 엑셀을 만들고 `EXCEL_PATH`에 지정합니다 (기본: `recipients.xlsx`).
4. 실행합니다.

```bash
python main.py
```

## 엑셀 파일 형식

| A (이름) | B (이메일) |
|---------|-----------|
| 이름    | 이메일     |
| 홍길동  | hong@example.com |
| 김철수  | kim@example.com |

## 템플릿 변수

HTML 템플릿과 제목에서 사용 가능한 변수:
- `{name}` - 수신자 이름
- `{email}` - 수신자 이메일 (HTML만)
