import streamlit as st
st.title('나의 첫 웹앱에 오신걸 환영합니다')
st.write('by 정선황😊')
import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.express as px
import plotly.graph_objects as go

# 1. 페이지 기본 설정 (넓은 화면 레이아웃)
st.set_page_config(
    page_title="전국 고령화 및 인구 변화 분석",
    page_icon="🗺️",
    layout="wide"
)

st.title("🗺️ 전국 시군구 고령화 및 인구 변화 분석")
st.markdown("최신 연도 기준 고령화율과 과거 대비 인구 증감율을 구간별로 나누어 비교 분석합니다.")

# 데이터 URL 정의
POPULATION_URL = "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz"
GEOJSON_URL = "https://raw.githubusercontent.com/greatsong/modudata/main/data/boundaries/sigungu_kr.geojson"

# 2. GeoJSON 데이터 불러오기 (캐싱)
@st.cache_data
def load_geojson():
    response = requests.get(GEOJSON_URL)
    return response.json()

# 3. 인구 데이터 불러오기 및 전처리 (캐싱)
@st.cache_data
def load_and_process_data():
    # 코드를 10자리 문자로 안전하게 읽기
    df = pd.read_csv(POPULATION_URL, dtype={'코드': str})
    df['코드'] = df['코드'].str.zfill(10)
    df['sigungu_code'] = df['코드'].str[:5]
    
    min_year = df['연도'].min()
    max_year = df['연도'].max()
    
    # 전체 인구 및 고령 인구 계산
    total_pop_cols = [c for c in df.columns if c.startswith('계_')]
    senior_pop_cols = [f'계_{i}세' for i in range(65, 100)] + ['계_100세 이상']
    senior_pop_cols = [c for c in senior_pop_cols if c in df.columns]
    
    df[total_pop_cols] = df[total_pop_cols].apply(pd.to_numeric, errors='coerce').fillna(0)
    df['총인구'] = df[total_pop_cols].sum(axis=1)
    df['고령인구'] = df[senior_pop_cols].sum(axis=1)
    
    # 연도별, 시군구별 그룹화
    yearly_sigungu = df.groupby(['연도', 'sigungu_code']).agg({
        '시도': 'first',
        '시군구': 'first',
        '총인구': 'sum',
        '고령인구': 'sum'
    }).reset_index()
    
    # 과거(min_year) 데이터 추출
    df_past = yearly_sigungu[yearly_sigungu['연도'] == min_year][['sigungu_code', '총인구']]
    df_past = df_past.rename(columns={'총인구': '과거총인구'})
    
    # 현재(max_year) 데이터 추출
    df_current = yearly_sigungu[yearly_sigungu['연도'] == max_year].copy()
    df_current = df_current.rename(columns={'총인구': '현재총인구', '고령인구': '현재고령인구'})
    
    # 과거와 현재 데이터 병합
    df_merged = pd.merge(df_current, df_past, on='sigungu_code', how='left')
    
    # 지표 계산: 고령화율(%) 및 인구증감율(%)
    df_merged['고령화율'] = (df_merged['현재고령인구'] / df_merged['현재총인구'] * 100).round(2)
    df_merged['인구증감율'] = ((df_merged['현재총인구'] - df_merged['과거총인구']) / df_merged['과거총인구'] * 100).round(2)
    
    # [1] 고령화율 5단계 구간화
    aging_bins = [-np.inf, 19.0, 23.0, 28.0, 38.0, np.inf]
    aging_labels = ['19% 미만', '19% ~ 23% 미만', '23% ~ 28% 미만', '28% ~ 38% 미만', '38% 이상']
    df_merged['고령화율_구간'] = pd.cut(df_merged['고령화율'], bins=aging_bins, labels=aging_labels, right=False)
    
    # [2] 인구증감율 5단계 구간화
    growth_bins = [-np.inf, -10.0, 0.0, 10.0, 20.0, np.inf]
    growth_labels = ['-10% 미만 (감소 심화)', '-10% ~ 0% 미만 (소폭 감소)', '0% ~ 10% 미만 (소폭 증가)', '10% ~ 20% 미만 (증가)', '20% 이상 (증가 심화)']
    df_merged['인구증감율_구간'] = pd.cut(df_merged['인구증감율'], bins=growth_bins, labels=growth_labels, right=False)
    
    return df_merged, min_year, max_year

# 데이터 로딩
with st.spinner("데이터를 분석 중입니다..."):
    geojson_data = load_geojson()
    df_sigungu, start_year, end_year = load_and_process_data()

st.caption(f" 기준 기간: {start_year}년 ~ {end_year}년")

# 4. 지도 나란히 배치 (두 개의 컬럼 생성)
col_map1, col_map2 = st.columns(2)

# --- 지도 1: 고령화율 단계구분도 (왼쪽) ---
with col_map1:
    st.subheader("🔴 시군구별 고령화율")
    aging_labels_order = ['19% 미만', '19% ~ 23% 미만', '23% ~ 28% 미만', '28% ~ 38% 미만', '38% 이상']
    color_map_aging = {
        '19% 미만': '#fef0d9', '19% ~ 23% 미만': '#fdcc8a', 
        '23% ~ 28% 미만': '#fc8d59', '28% ~ 38% 미만': '#e34a33', '38% 이상': '#b30000'
    }
    
    fig_aging = px.choropleth(
        df_sigungu,
        geojson=geojson_data,
        locations='sigungu_code',
        featureidkey='properties.코드',
        color='고령화율_구간',
        category_orders={'고령화율_구간': aging_labels_order},
        color_discrete_map=color_map_aging,
        hover_name='시군구',
        hover_data={'시도': True, '고령화율': ':.2f', 'sigungu_code': False, '고령화율_구간': False},
        labels={'고령화율': '고령화율(%)', '고령화율_구간': '고령화 구간'}
    )
    fig_aging.update_geos(fitbounds="locations", visible=False)
    fig_aging.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0}, height=500)
    st.plotly_chart(fig_aging, use_container_width=True)

# --- 지도 2: 인구증감율 단계구분도 (오른쪽) ---
with col_map2:
    st.subheader(f"🔵 인구 증감율 ({start_year}년 대비)")
    growth_labels_order = ['-10% 미만 (감소 심화)', '-10% ~ 0% 미만 (소폭 감소)', '0% ~ 10% 미만 (소폭 증가)', '10% ~ 20% 미만 (증가)', '20% 이상 (증가 심화)']
    color_map_growth = {
        '-10% 미만 (감소 심화)': '#d7191c',       
        '-10% ~ 0% 미만 (소폭 감소)': '#fdae61',   
        '0% ~ 10% 미만 (소폭 증가)': '#abd9e9',    
        '10% ~ 20% 미만 (증가)': '#2c7bb6',        
        '20% 이상 (증가 심화)': '#053061'          
    }

    fig_growth = px.choropleth(
        df_sigungu,
        geojson=geojson_data,
        locations='sigungu_code',
        featureidkey='properties.코드',
        color='인구증감율_구간',
        category_orders={'인구증감율_구간': growth_labels_order},
        color_discrete_map=color_map_growth,
        hover_name='시군구',
        hover_data={'시도': True, '인구증감율': ':.2f', 'sigungu_code': False, '인구증감율_구간': False},
        labels={'인구증감율': '인구증감율(%)', '인구증감율_구간': '인구증감 구간'}
    )
    fig_growth.update_geos(fitbounds="locations", visible=False)
    fig_growth.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0}, height=500)
    st.plotly_chart(fig_growth, use_container_width=True)

st.markdown("---")

# 5. 상관관계 그래프 (산점도 + 선형회귀 선) - 이상치 제거 적용
st.subheader("📈 고령화율과 인구 증감율의 상관관계")

# 결측치 제거
df_valid = df_sigungu.dropna(subset=['고령화율', '인구증감율'])

# [수정됨] 인구증감율 60% 이상인 너무 튀는 이상치(Outlier) 제외
df_filtered = df_valid[df_valid['인구증감율'] < 60]
outlier_count = len(df_valid) - len(df_filtered)

if outlier_count > 0:
    st.info(f"💡 분석의 정확도를 높이기 위해 인구 증감율이 60% 이상인 극단적 수치(이상치) **{outlier_count}개** 지역은 상관관계 산점도 및 추세선에서 제외되었습니다.")

# 이상치를 제외한 데이터로 선형회귀(Numpy polyfit)를 계산합니다.
slope, intercept = np.polyfit(df_filtered['고령화율'], df_filtered['인구증감율'], 1)

# 회귀방정식 문자열 생성
sign = "+" if intercept >= 0 else "-"
equation_text = f"y = {slope:.2f}x {sign} {abs(intercept):.2f}"

st.markdown(f"**선형 회귀 함수(추세선):** `{equation_text}` (x: 고령화율, y: 인구증감율)")

# 필터링된 데이터(df_filtered)로 산점도 그리기
fig_scatter = px.scatter(
    df_filtered,
    x='고령화율',
    y='인구증감율',
    color='시도',       
    hover_name='시군구',
    hover_data={'현재총인구': ':,', '과거총인구': ':,', '시도': False},
    labels={
        '고령화율': '고령화율 (%)',
        '인구증감율': '인구 증감율 (%)',
        '현재총인구': '최신 총인구'
    },
    opacity=0.7
)

# 선형회귀 추세선 좌표 계산 (x의 양끝값 사용)
line_x = np.array([df_filtered['고령화율'].min(), df_filtered['고령화율'].max()])
line_y = slope * line_x + intercept

# 산점도 위에 선형회귀선 추가
fig_scatter.add_trace(
    go.Scatter(
        x=line_x, 
        y=line_y, 
        mode='lines', 
        name=f'선형회귀 추세선<br>({equation_text})',
        line=dict(color='black', width=3, dash='dash')
    )
)

# 기준선 추가 (인구 증감율 0% 기준)
fig_scatter.add_hline(y=0, line_dash="solid", line_color="rgba(255,0,0,0.3)", annotation_text="인구 증감 0% 기준선")
fig_scatter.update_layout(height=550)

st.plotly_chart(fig_scatter, use_container_width=True)

st.markdown("---")

# 6. 하단 데이터 표 출력 (고령화율 기준 상/하위)
st.subheader("📊 시군구 상세 데이터 요약")

col_table1, col_table2 = st.columns(2)
display_cols = ['시도', '시군구', '고령화율', '인구증감율', '현재총인구']

with col_table1:
    st.markdown("##### 🔴 고령화율 상위 10개 지역")
    top_10 = df_sigungu.sort_values(by='고령화율', ascending=False).head(10)[display_cols]
    st.dataframe(
        top_10.reset_index(drop=True),
        use_container_width=True,
        column_config={
            "고령화율": st.column_config.NumberColumn("고령화율 (%)", format="%.2f%%"),
            "인구증감율": st.column_config.NumberColumn("인구증감율 (%)", format="%.2f%%"),
            "현재총인구": st.column_config.NumberColumn("총인구 (명)", format="%d"),
        }
    )

with col_table2:
    st.markdown("##### 🔵 고령화율 하위 10개 지역")
    bottom_10 = df_sigungu.sort_values(by='고령화율', ascending=True).head(10)[display_cols]
    st.dataframe(
        bottom_10.reset_index(drop=True),
        use_container_width=True,
        column_config={
            "고령화율": st.column_config.NumberColumn("고령화율 (%)", format="%.2f%%"),
            "인구증감율": st.column_config.NumberColumn("인구증감율 (%)", format="%.2f%%"),
            "현재총인구": st.column_config.NumberColumn("총인구 (명)", format="%d"),
        }
    )
