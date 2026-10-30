import os
import sys
from dotenv import load_dotenv
from aligo_sms import get_remain, read_recipients, send_bulk_sms

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
        api_key = os.getenv("ALIGO_API_KEY")
        user_id = os.getenv("ALIGO_USER_ID")
        sender = os.getenv("ALIGO_SENDER")
        sms_title = os.getenv("SMS_TITLE", "")
        excel_path = os.getenv("EXCEL_PATH", "recipients.xlsx")
        msg_path = os.getenv("MSG_PATH", "message_example.txt")
        msg_type = os.getenv("MSG_TYPE") or None
        test_mode = os.getenv("TEST_MODE", "Y").upper() != "N"

        # 상대 경로면 실행 파일 기준으로 변환
        if not os.path.isabs(excel_path):
            excel_path = os.path.join(BASE_DIR, excel_path)
        if not os.path.isabs(msg_path):
            msg_path = os.path.join(BASE_DIR, msg_path)

        if not api_key or not user_id or not sender:
            print("[오류] .env 파일에 ALIGO_API_KEY / ALIGO_USER_ID / ALIGO_SENDER를 입력해주세요.")
        elif not os.path.exists(excel_path):
            print(f"[오류] 수신자 엑셀 파일을 찾을 수 없습니다: {excel_path}")
        elif not os.path.exists(msg_path):
            print(f"[오류] 문자 내용 파일을 찾을 수 없습니다: {msg_path}")
        else:
            with open(msg_path, "r", encoding="utf-8") as f:
                msg_template = f.read().strip()

            recipients = read_recipients(
                excel_path,
                name_col="A",   # 이름 컬럼
                phone_col="B",  # 전화번호 컬럼
                start_row=2,    # 데이터 시작 행 (1행은 헤더)
            )

            remain = get_remain(api_key, user_id)
            if str(remain.get("result_code")) != "1":
                print(f"[오류] 알리고 인증 실패: {remain.get('message')}")
                print("       API 키, 아이디, 발송 서버 IP 등록을 확인해주세요.")
            elif not recipients:
                print("[오류] 발송할 수신자가 없습니다.")
            else:
                first_name, first_phone = recipients[0]
                preview = msg_template.replace("{name}", first_name).replace("{phone}", first_phone)

                print(f"발신번호: {sender}")
                print(f"수신자 목록: {excel_path} ({len(recipients)}명)")
                print(f"잔여 건수: SMS {remain.get('SMS_CNT')} / LMS {remain.get('LMS_CNT')}")
                print(f"모드: {'테스트 (실제 발송 안 됨)' if test_mode else '실제 발송'}")
                print(f"\n--- 미리보기 ({first_name or first_phone}) ---\n{preview}\n------------------------------\n")

                answer = input(f"{len(recipients)}명에게 발송할까요? (y/n): ").strip().lower()
                if answer == "y":
                    send_bulk_sms(
                        api_key=api_key,
                        user_id=user_id,
                        sender=sender,
                        recipients=recipients,
                        msg_template=msg_template,
                        title=sms_title,
                        msg_type=msg_type,
                        test_mode=test_mode,
                    )
                else:
                    print("발송을 취소했습니다.")
    except Exception as e:
        print(f"[오류] {e}")

    input("\n엔터 키를 누르면 종료됩니다...")
