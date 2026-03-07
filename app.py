import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import time

st.set_page_config(page_title="GGU SCTR Screener", layout="wide")
st.title("🏛️ Hệ Thống GGU: StockCharts Technical Rank (SCTR)")
st.markdown("Xếp hạng sức mạnh cổ phiếu. Dùng SCTR > 70 để tìm các ứng viên Tái Tích Luỹ / Đẩy Giá chuẩn Wyckoff.")

# DANH SÁCH MÃ CỔ PHIẾU THANH KHOẢN TỐT THỊ TRƯỜNG VIỆT NAM (Vũ trụ xếp hạng)
MARKET_TICKERS = [
    "VCB","BID","CTG","TCB","MBB","STB","VPB","ACB","HDB","VIB","TPB","SHB","MSB","LPB","EIB","OCB","SSB",
    "SSI","VND","HCM","VCI","SHS","MBS","FTS","BSI","CTS","AGR","VIX","ORS","VDS","BVS",
    "HPG","HSG","NKG","VGS","SMC","TLH","HT1","BCC","KSB",
    "VHM","VIC","VRE","DXG","DIG","PDR","NLG","NVL","CEO","HDC","KDH","NTL","TCH","IJC","CRE","SCR","HQC",
    "KBC","IDC","SZC","VGC","PHR","BCM","NTC","SIP","D2D",
    "FPT","MWG","PNJ","FRT","DGW","PET","CMG","ELC","VGI","CTR",
    "GAS","PVD","PVS","BSR","PLX","DGC","DCM","DPM","CSV","GVR",
    "GMD","HAH","VSC","PVT","VOS",
    "POW","REE","PC1","NT2","GEG","TV2","HDG",
    "VHC","ANV","IDI","FMC","DBC","HAG","BAF","PAN","TAR",
    "VCG","HHV","LCG","C4G","HBC","CTD","FCN","HUT","CII",
    "TNG","VGT","GIL","MSH","BVH","BMI","MIG","DHG","BMP","NTP","VNM","MSN","SAB"
]

@st.cache_data(ttl=3600)
def get_data(ticker, period="1y"): 
    try:
        df = yf.Ticker(ticker).history(period=period)
        if len(df) < 200: return None
        return df
    except:
        return None

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_ppo_hist(close_series):
    ema12 = close_series.ewm(span=12, adjust=False).mean()
    ema26 = close_series.ewm(span=26, adjust=False).mean()
    ppo = (ema12 - ema26) / ema26 * 100
    ppo_signal = ppo.ewm(span=9, adjust=False).mean()
    ppo_hist = ppo - ppo_signal
    return ppo_hist

def calculate_sctr_components(df):
    close = df['Close']
    
    # 1. Long-Term (30% each)
    ema200 = close.ewm(span=200, adjust=False).mean()
    pct_above_ema200 = ((close.iloc[-1] - ema200.iloc[-1]) / ema200.iloc[-1]) * 100
    score_ema200 = pct_above_ema200 * 0.30
    
    roc125 = ((close.iloc[-1] - close.iloc[-125]) / close.iloc[-125]) * 100 if len(close) >= 125 else 0
    score_roc125 = roc125 * 0.30
    
    # 2. Medium-Term (15% each)
    ema50 = close.ewm(span=50, adjust=False).mean()
    pct_above_ema50 = ((close.iloc[-1] - ema50.iloc[-1]) / ema50.iloc[-1]) * 100
    score_ema50 = pct_above_ema50 * 0.15
    
    roc20 = ((close.iloc[-1] - close.iloc[-20]) / close.iloc[-20]) * 100 if len(close) >= 20 else 0
    score_roc20 = roc20 * 0.15
    
    # 3. Short-Term (5% each)
    rsi14 = calculate_rsi(close, 14).iloc[-1]
    score_rsi = rsi14 * 0.05 if not np.isnan(rsi14) else 0
    
    ppo_hist = calculate_ppo_hist(close)
    # Calculate 3-day slope of PPO-Hist (linear regression over last 3 points)
    last_3_hist = ppo_hist.tail(3).values
    if len(last_3_hist) == 3 and not np.isnan(last_3_hist).any():
        x = np.array([0, 1, 2])
        slope = np.polyfit(x, last_3_hist, 1)[0]
        
        # PPO Slope special rule
        if slope > 1:
            score_ppo = 5.0
        elif slope < -1:
            score_ppo = 0.0
        else:
            score_ppo = 0.05 * ((slope + 1) * 50)
    else:
        score_ppo = 0
        
    total_score = score_ema200 + score_roc125 + score_ema50 + score_roc20 + score_rsi + score_ppo
    
    return {
        "Giá Hiện Tại": round(close.iloc[-1], 2),
        "EMA200_Score": round(score_ema200, 2),
        "ROC125_Score": round(score_roc125, 2),
        "EMA50_Score": round(score_ema50, 2),
        "ROC20_Score": round(score_roc20, 2),
        "RSI_Score": round(score_rsi, 2),
        "PPO_Score": round(score_ppo, 2),
        "Total_Score": round(total_score, 2)
    }

# ==========================================
# GIAO DIỆN WEB
# ==========================================
st.markdown("### 🦅 Quét & Xếp Hạng Sức Mạnh Tương Đối (Top-Down GGU)")

col1, col2 = st.columns([1, 2])
with col1:
    st.info("Hệ thống sẽ tải dữ liệu của ~120 mã đại diện thị trường, tính toán điểm nội tại và xếp hạng SCTR chuẩn.")

if st.button("🚀 KÍCH HOẠT BỘ LỌC SCTR"):
    raw_results = []
    tickers_to_scan = [t + ".VN" for t in MARKET_TICKERS]
    total_tickers = len(tickers_to_scan)
    
    my_bar = st.progress(0, text="Đang tải dữ liệu và tính toán chỉ báo...")
    
    for i, t in enumerate(tickers_to_scan):
        df = get_data(t, "1y")
        if df is not None:
            scores = calculate_sctr_components(df)
            scores["Mã"] = t.replace(".VN", "")
            raw_results.append(scores)
        
        my_bar.progress((i + 1) / total_tickers, text=f"Đang phân tích: {t}...")
        time.sleep(0.01) # Tránh bị Yahoo chặn
        
    my_bar.empty()
    
    if raw_results:
        df_results = pd.DataFrame(raw_results)
        
        # TÍNH TOÁN XẾP HẠNG SCTR (Percentile Rank trong nhóm)
        df_results['SCTR'] = df_results['Total_Score'].rank(pct=True) * 100
        df_results['SCTR'] = df_results['SCTR'].round(1)
        
        # Sắp xếp từ mạnh nhất đến yếu nhất
        df_results = df_results.sort_values(by="SCTR", ascending=False).reset_index(drop=True)
        
        # Định dạng lại bảng hiển thị
        display_cols = ["Mã", "SCTR", "Giá Hiện Tại", "Total_Score", "ROC125_Score", "ROC20_Score"]
        df_display = df_results[display_cols]
        
        st.success(f"Hoàn tất! Đã xếp hạng SCTR cho {len(df_results)} mã cổ phiếu.")
        
        st.markdown("#### 🔥 TOP CỔ PHIẾU LÃNH ĐẠO (SCTR > 75)")
        st.markdown("*Đây là nhóm cổ phiếu mạnh nhất thị trường. Hãy mở biểu đồ của các mã này lên và dùng kiến thức Wyckoff của bạn để tìm Cấu trúc Tái Tích luỹ (Re-Accumulation) hoặc Điểm Spring.*")
        
        top_leaders = df_display[df_display['SCTR'] >= 75]
        st.dataframe(top_leaders.style.background_gradient(subset=['SCTR'], cmap='Greens'), use_container_width=True)
        
        with st.expander("Xem toàn bộ Bảng xếp hạng SCTR"):
            st.dataframe(df_results, use_container_width=True)
            
    else:
        st.error("Lỗi lấy dữ liệu từ Yahoo Finance. Vui lòng thử lại sau.")
