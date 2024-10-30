import streamlit as st
import gspread
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import pandas as pd
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
import os

# 페이지 설정
st.set_page_config(
    page_title="국소 관리 시스템",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Streamlit Secrets에서 민감 정보 불러오기
spreadsheet_id = st.secrets["credentials"]["spreadsheet_id"]
email_user = st.secrets["email"]["user"]
email_password = st.secrets["email"]["password"]

# Google API 인증 설정
def initialize_google_services():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/drive.file"
    ]
    creds = service_account.Credentials.from_service_account_info(
        st.secrets["google_credentials"],
        scopes=scope
    )
    sheet = gspread.authorize(creds).open_by_key(spreadsheet_id).sheet1
    drive_service = build('drive', 'v3', credentials=creds)
    return sheet, drive_service

sheet, drive_service = initialize_google_services()

# 이메일 전송 함수
def send_email(to_email, subject, message):
    try:
        msg = MIMEMultipart()
        msg["From"] = email_user
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(message, "plain"))
        
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(email_user, email_password)
            server.send_message(msg)
        return True
    except Exception as e:
        st.error(f"이메일 전송 실패: {str(e)}")
        return False

# 파일 업로드 함수
def upload_file_to_drive(file):
    try:
        file_path = f"/tmp/{file.name}"
        with open(file_path, "wb") as f:
            f.write(file.getbuffer())
        
        file_metadata = {
            "name": f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.name}",
            "parents": ["your_drive_folder_id"]  # 실제 Google 드라이브 폴더 ID로 교체하세요
        }
        
        media = MediaFileUpload(
            file_path,
            mimetype=file.type,
            resumable=True
        )
        
        file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id"
        ).execute()
        
        os.remove(file_path)  # 임시 파일 삭제
        return f"https://drive.google.com/file/d/{file.get('id')}/view?usp=sharing"
    except Exception as e:
        st.error(f"파일 업로드 실패: {str(e)}")
        return None

# 메인 앱 UI
def main_app():
    st.title("국소 관리 시스템")
    
    # 탭 생성
    tabs = st.tabs(["데이터 검색", "새 데이터 등록", "정보 전송"])
    
    # 데이터 검색 탭
    with tabs[0]:
        st.subheader("데이터 검색 및 수정")
        search_email = st.text_input("검색할 이메일 주소")
        
        if st.button("검색"):
            records = sheet.get_all_records()
            df = pd.DataFrame(records)
            search_result = df[df["이메일"] == search_email]
            
            if not search_result.empty:
                st.write("검색 결과:", search_result)
                
                # 수정 폼
                with st.form("edit_form"):
                    row_index = search_result.index[0] + 2
                    location_name = st.text_input("국소명", value=search_result.iloc[0]["국소명"])
                    address = st.text_input("주소", value=search_result.iloc[0]["주소"])
                    contacts = st.text_input("담당자 및 연락처", value=search_result.iloc[0]["담당자 및 연락처"])
                    notes = st.text_area("특이사항", value=search_result.iloc[0]["특이사항"])
                    
                    if st.form_submit_button("수정사항 저장"):
                        try:
                            sheet.update(f"B{row_index}", location_name)
                            sheet.update(f"C{row_index}", address)
                            sheet.update(f"D{row_index}", contacts)
                            sheet.update(f"F{row_index}", notes)
                            st.success("데이터가 성공적으로 수정되었습니다!")
                        except Exception as e:
                            st.error(f"데이터 수정 실패: {str(e)}")
            else:
                st.warning("검색 결과가 없습니다.")
    
    # 새 데이터 등록 탭
    with tabs[1]:
        st.subheader("새로운 데이터 입력")
        
        with st.form("registration_form"):
            location_name = st.text_input("국소명")
            address = st.text_input("주소")
            
            # 담당자 정보 입력
            st.write("담당자 정보")
            contact_persons = []
            cols = st.columns(3)
            for i, col in enumerate(cols):
                with col:
                    name = st.text_input(f"담당자 {i+1} 이름", key=f"name_{i}")
                    phone = st.text_input(f"연락처 {i+1}", key=f"phone_{i}")
                    if name and phone:
                        contact_persons.append(f"{name} ({phone})")
            
            # 사진 업로드
            uploaded_files = st.file_uploader(
                "사진 파일을 업로드하세요 (최대 20장)",
                type=["jpg", "png", "jpeg"],
                accept_multiple_files=True
            )
            
            notes = st.text_area("특이사항")
            submit_button = st.form_submit_button("등록")
            
            if submit_button:
                if location_name and address and contact_persons:
                    try:
                        # 사진 업로드 처리
                        photo_links = []
                        if uploaded_files:
                            for file in uploaded_files[:20]:  # 최대 20장으로 제한
                                link = upload_file_to_drive(file)
                                if link:
                                    photo_links.append(link)
                        
                        # 데이터 저장
                        sheet.append_row([
                            location_name,
                            address,
                            ", ".join(contact_persons),
                            ", ".join(photo_links),
                            notes
                        ])
                        
                        st.success("데이터가 성공적으로 등록되었습니다!")
                    except Exception as e:
                        st.error(f"데이터 등록 실패: {str(e)}")
                else:
                    st.error("필수 항목을 모두 입력해주세요.")
    
    # 정보 전송 탭
    with tabs[2]:
        st.subheader("정보 전송")
        
        with st.form("email_form"):
            recipient_email = st.text_input("전송할 이메일 주소")
            search_email = st.text_input("전송할 데이터의 이메일")
            
            if st.form_submit_button("검색 및 전송"):
                if recipient_email and search_email:
                    records = sheet.get_all_records()
                    df = pd.DataFrame(records)
                    search_result = df[df["이메일"] == search_email]
                    
                    if not search_result.empty:
                        data = search_result.iloc[0]
                        message = f"""
                        국소명: {data['국소명']}
                        주소: {data['주소']}
                        담당자 및 연락처: {data['담당자 및 연락처']}
                        사진 링크: {data['사진 링크']}
                        특이사항: {data['특이사항']}
                        """
                        
                        if send_email(recipient_email, "국소 정보", message):
                            st.success("이메일이 성공적으로 전송되었습니다!")
                        else:
                            st.error("이메일 전송에 실패했습니다.")
                    else:
                        st.warning("검색된 데이터가 없습니다.")
                else:
                    st.error("이메일 주소를 입력해주세요.")

# 메인 실행 부분
def main():
    main_app()

if __name__ == "__main__":
    main()

