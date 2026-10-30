import os
import sys
from dotenv import load_dotenv
from mailer import send_bulk_from_excel

# 실행 파일(.exe)이면 exe가 있는 폴더, 스크립트면 .py가 있는 폴더 기준
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

load_dotenv(os.path.join(BASE_DIR, ".env"))


# 사용 예시
if __name__ == "__main__":
    try:
        # 환경변수에서 설정 로드
        sender_email = os.getenv("SENDER_EMAIL")
        sender_password = os.getenv("SENDER_PASSWORD")
        smtp_server = os.getenv("SMTP_SERVER", "smtps.hiworks.com")
        smtp_port = int(os.getenv("SMTP_PORT", 465))
        email_subject = os.getenv("EMAIL_SUBJECT", "[회사명] 뉴스레터")
        excel_path = os.getenv("EXCEL_PATH", "recipients.xlsx")
        html_path = os.getenv("HTML_PATH", "email_example.html")

        # 상대 경로면 실행 파일 기준으로 변환
        if not os.path.isabs(excel_path):
            excel_path = os.path.join(BASE_DIR, excel_path)
        if not os.path.isabs(html_path):
            html_path = os.path.join(BASE_DIR, html_path)

        if not sender_email or not sender_password:
            print("[오류] .env 파일에 SENDER_EMAIL / SENDER_PASSWORD를 입력해주세요.")
        elif not os.path.exists(excel_path):
            print(f"[오류] 수신자 엑셀 파일을 찾을 수 없습니다: {excel_path}")
        elif not os.path.exists(html_path):
            print(f"[오류] HTML 파일을 찾을 수 없습니다: {html_path}")
        else:
            # HTML 템플릿 읽기
            with open(html_path, "r", encoding="utf-8") as f:
                html_from_file = f.read()

            print(f"발신자: {sender_email}")
            print(f"수신자 목록: {excel_path}")
            print(f"메일 제목: {email_subject}\n")

            send_bulk_from_excel(
                sender_email=sender_email,
                sender_password=sender_password,
                excel_path=excel_path,
                subject=email_subject,
                html_template=html_from_file,
                name_col="A",   # 이름 컬럼
                email_col="B",  # 이메일 컬럼
                start_row=2,    # 데이터 시작 행 (1행은 헤더)
                delay=1,        # 발송 간격 (초)
                smtp_server=smtp_server,
                smtp_port=smtp_port,
            )
    except Exception as e:
        print(f"[오류] {e}")

    input("\n엔터 키를 누르면 종료됩니다...")
