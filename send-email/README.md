# Send Email

Python으로 HTML 이메일을 발송하는 모듈입니다.

## 설치

```bash
pip install openpyxl
```

## 엑셀 파일 형식

| A (이름) | B (이메일) |
|---------|-----------|
| 이름    | 이메일     |
| 홍길동  | hong@example.com |
| 김철수  | kim@example.com |

## 사용법

```python
from main import send_bulk_from_excel

send_bulk_from_excel(
    sender_email="your@email.com",
    sender_password="your_app_password",
    excel_path="recipients.xlsx",
    subject="[회사명] 안내 메일",
    html_template=html_template,
    name_col="A",   # 이름 컬럼
    email_col="B",  # 이메일 컬럼
    start_row=2,    # 헤더 제외
    delay=1,        # 발송 간격 (초)
)
```

## 템플릿 변수

HTML 템플릿에서 사용 가능한 변수:
- `{name}` - 수신자 이름
- `{email}` - 수신자 이메일
