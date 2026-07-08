import streamlit as st
import pandas as pd

# 💡 새로 추가된 핵심 함수: CSV 인코딩(글자 깨짐) 에러를 방어해 주는 똑똑한 읽기 함수
def load_csv(file):
    try:
        # 1. 기본 글로벌 방식(UTF-8)으로 먼저 읽어보기
        return pd.read_csv(file)
    except UnicodeDecodeError:
        # 2. 에러가 나면 한국어 윈도우 방식(CP949)으로 다시 읽기
        file.seek(0)
        return pd.read_csv(file, encoding='cp949')

# 점수를 등급으로 변환하는 함수
def calculate_grade(score):
    if pd.isna(score) or score == 0: 
        return None
    if score >= 90: return 'S'
    elif score >= 80: return 'A'
    elif score >= 70: return 'B'
    else: return 'C'

# 페이지 기본 설정
st.set_page_config(page_title="인사평가 점수 자동 취합", layout="wide")
st.title("📊 공기업 인사평가 점수 자동 취합 및 조정 시스템")

if 'merged_df' not in st.session_state:
    st.session_state['merged_df'] = pd.DataFrame()

# 1. 왼쪽 사이드바: 파일 업로드 영역
st.sidebar.header("1. 마스터 명단 업로드")
master_file = st.sidebar.file_uploader("직원 명단 업로드", type=["csv", "xlsx"], key="master")

if master_file is not None:
    if master_file.name.endswith('.csv'):
        df_master = load_csv(master_file) # 💡 위에서 만든 똑똑한 함수 적용
    else:
        df_master = pd.read_excel(master_file)
    st.session_state['merged_df'] = df_master
    st.sidebar.success("마스터 명단 세팅 완료!")

st.sidebar.divider()

st.sidebar.header("2. 단계별 점수 업로드")
step_names = ["1차평가", "2차평가", "BSC점수", "3차평가"]

for step in step_names:
    uploaded_file = st.sidebar.file_uploader(f"{step} 파일 업로드", type=["csv", "xlsx"], key=step)
    
    if uploaded_file is not None and not st.session_state['merged_df'].empty:
        if uploaded_file.name.endswith('.csv'):
            new_data = load_csv(uploaded_file) # 💡 여기도 적용
        else:
            new_data = pd.read_excel(uploaded_file)
        
        if '성명' in new_data.columns:
            new_data = new_data.drop(columns=['성명'])
            
        try:
            st.session_state['merged_df'] = pd.merge(st.session_state['merged_df'], new_data, on="사번", how="left")
            st.sidebar.success(f"{step} 병합 완료!")
        except KeyError:
            st.sidebar.error("업로드한 파일에 '사번' 열이 없습니다!")

# 2. 메인 화면: 데이터 처리 및 분석 영역
if not st.session_state['merged_df'].empty:
    df_final = st.session_state['merged_df'].copy()
    total_employees = len(df_final)
    
    prov_columns = [col for col in ['1차점수', '2차점수', 'BSC점수'] if col in df_final.columns]
    has_3rd = '3차점수' in df_final.columns
    
    # [STEP 1] 3차 평가 전 임시 총점 및 등급 계산
    if prov_columns:
        df_final['임시총점'] = df_final[prov_columns].sum(axis=1)
        df_final['임시등급'] = df_final['임시총점'].apply(calculate_grade)
        
        st.subheader("🔍 [3차 조정 전] 임시 등급 분포 모니터링")
        st.markdown("조정자(인사위원회 등)는 아래 비율의 **초과/미달 인원**을 확인하고 3차 점수를 부여하여 비율을 맞춰야 합니다.")
        
        dist = df_final['임시등급'].value_counts().reindex(['S', 'A', 'B', 'C'], fill_value=0)
        target_ratios = {'S': 0.2, 'A': 0.4, 'B': 0.3, 'C': 0.1}
        
        dist_df = pd.DataFrame({
            '규정 비율(%)': [target_ratios[g]*100 for g in ['S', 'A', 'B', 'C']],
            '규정 인원(명)': [int(total_employees * target_ratios[g]) for g in ['S', 'A', 'B', 'C']],
            '현재 인원(명)': dist,
        })
        dist_df['초과/미달(명)'] = dist_df['현재 인원(명)'] - dist_df['규정 인원(명)']
        
        st.dataframe(dist_df.T, use_container_width=True)

    # [STEP 2] 3차 평가 최종 점수 및 등급 계산
    if has_3rd:
        st.divider()
        st.subheader("🏆 [3차 조정 반영 후] 최종 등급 분포")
        
        df_final['최종총점'] = df_final['임시총점'] + df_final['3차점수']
        df_final['최종등급'] = df_final['최종총점'].apply(calculate_grade)
        
        final_dist = df_final['최종등급'].value_counts().reindex(['S', 'A', 'B', 'C'], fill_value=0)
        final_dist_df = pd.DataFrame({
            '규정 인원(명)': dist_df['규정 인원(명)'],
            '최종 확정 인원(명)': final_dist
        })
        final_dist_df['최종 초과/미달(명)'] = final_dist_df['최종 확정 인원(명)'] - final_dist_df['규정 인원(명)']
        
        st.dataframe(final_dist_df.T, use_container_width=True)

    st.divider()
    st.subheader("📝 세부 직원별 점수 명부")
    st.dataframe(df_final, use_container_width=True)
    
    csv = df_final.to_csv(index=False).encode('utf-8-sig')
    st.download_button(
        label="📥 현재 명부 다운로드 (엑셀/CSV)",
        data=csv,
        file_name="인사평가_점수취합본.csv",
        mime="text/csv",
    )
else:
    st.info("👈 왼쪽 사이드바에서 마스터 명단 파일을 가장 먼저 업로드해주세요.")