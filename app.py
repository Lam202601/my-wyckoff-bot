import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import time

st.set_page_config(page_title="GGU Master: Custom SCTR & VSA", layout="wide")
st.title("🏛️ Hệ Thống GGU: SCTR Top-Down & VSA Bar-by-Bar")
st.markdown("Bản nâng cấp GGU Custom (ROC 252, ROC 63, RSI 21) & Phân ngành chuẩn VN220.")

# TỪ ĐIỂN PHÂN LOẠI NGÀNH CHUẨN (Cập nhật Hệ sinh thái Tuấn Mượt & Tách nhóm Y tế/Bảo hiểm)
DEFAULT_SECTORS = {
    "Ngân hàng": ["VCB","BID","CTG","TCB","MBB","STB","VPB","ACB","HDB","VIB","TPB","SHB","MSB","LPB","EIB","OCB","SSB","NAB","BAB","KLB"],
    "Chứng khoán": ["SSI","VND","HCM","VCI","SHS","MBS","FTS","BSI","CTS","AGR","VIX","ORS","VDS","BVS","TCI","TVS","VIG","APG","VFS","DSC"],
    "Bất động sản": ["VHM","VIC","VRE","DXG","DIG","PDR","NLG","NVL","CEO","HDC","KDH","NTL","TCH","IJC","CRE","SCR","HQC","DXS","KHG","HDG","SJS","NBB","ITC","QCG","VPI","TDC"],
    "BĐS Khu công nghiệp": ["KBC","IDC","SZC","VGC","PHR","BCM","NTC","SIP","TIG","D2D","TIP","SNZ","SZL","ITA","LHG"],
    "Công nghệ & Viễn thông": ["FPT","VGI","CTR","CMG","ELC","FOX","TTN","VNZ","ITD","SGT"],
    "Bán lẻ": ["MWG","PNJ","FRT","DGW","PET","HAX"],
    "Thép & Sản phẩm thép": ["HPG","HSG","NKG","VGS","SMC","TLH"],
    "Vật liệu xây dựng": ["HT1","BCC","KSB","DHA","VLB","VCS","PLC","PTB","BMP","NTP","AAA"],
    "Dầu khí": ["GAS","PVD","PVS","BSR","PLX","OIL","PVC","PSH","PVB"],
    "Hóa chất & Phân bón": ["DGC","DCM","DPM","CSV","BFC","LAS","DDV","VTZ","PAT"],
    "Thực phẩm & Đồ uống": ["SAB","VNM","MSN","KDC","MCH","SBT","QNS"],
    "Thủy sản & Nông nghiệp": ["VHC","ANV","IDI","FMC","DBC","HAG","BAF","PAN","TAR","LTG","ASM","CMX","MPC","HNG"],
    "Vận tải & Logistics": ["GMD","HAH","VSC","PVT","VOS","VIP","VTO","PHP","SGP","MVN","DXP","TCL","PDN","VTP"],
    "Điện, Thiết bị điện & Đa ngành": ["POW","REE","PC1","NT2","GEG","TV2","QTP","HND","BWE","TDM","GEX"],
    "Xây dựng & Đầu tư công": ["VCG","HHV","LCG","C4G","HBC","CTD","FCN","HUT","DPG","CII","L14","EVG","VEC","TCD","CTI","HTN"],
    "Dệt may": ["TNG","VGT","GIL","MSH","STK","TCM"],
    "Cao su tự nhiên": ["GVR","DRC","DRI","DPR","TRC","CSM"],
    "Bảo hiểm": ["BVH","BMI","MIG","PVI","VNR"],
    "Y tế & Dược phẩm": ["DHG","IMP","DVN","TRA","DBD"]
}

TICKER_TO_SECTOR = {t: sector for sector, tickers in DEFAULT_SECTORS.items() for t in tickers}

# Lấy dữ liệu 2 năm (2y) để đủ nến tính toán đường ROC 252 ngày
@st.cache_data(ttl=3600)
def get_data(ticker, period="2y"): 
    try:
        df = yf.Ticker(ticker).history(period=period)
        # Yêu cầu tối thiểu 260 nến để tính ROC 252 và các MA
        if df is None or len(df) < 260: return None
        return df
    except:
        return None

# --- BỘ TOÁN TỬ CHUẨN GGU (ROMAN BOGOMAZOV) ---
def calculate_rsi(series, period=21):
    delta = series.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calculate_ppo_hist(close_series):
    ema12 = close_series.ewm(span=12, adjust=False).mean()
    ema26 = close_series.ewm(span=26, adjust=False).mean()
    ppo = (ema12 - ema26) / ema26 * 100
    ppo_signal = ppo.ewm(span=9, adjust=False).mean()
    return ppo - ppo_signal

def process_ultimate_wyckoff(df, min_volume, vsa_lookback):
    df = df.copy()
    df.index = pd.to_datetime(df.index).tz_localize(None)
    
    # 1. BỘ LỌC THANH KHOẢN
    df['Vol_MA20'] = df['Volume'].rolling(20).mean()
    current_vol_ma20 = float(df['Vol_MA20'].iloc[-1])
    if current_vol_ma20 < min_volume:
        return None
        
    close = df['Close']
    
    # ==============================================================
    # 2. CHẤM ĐIỂM SCTR CUSTOM (ROC 252 - ROC 63 - RSI 21)
    # ==============================================================
    
    # Long-Term (Trọng số 60%)
    ema200 = close.ewm(span=200, adjust=False).mean()
    score_ema200 = (((close.iloc[-1] - ema200.iloc[-1]) / ema200.iloc[-1]) * 100) * 0.30
    
    # Thay ROC 125 bằng ROC 252 (1 năm)
    roc252 = close.pct_change(periods=252).iloc[-1] * 100 if len(close) > 252 else 0
    score_roc252 = roc252 * 0.30
    
    # Medium-Term (Trọng số 30%)
    ema50 = close.ewm(span=50, adjust=False).mean()
    score_ema50 = (((close.iloc[-1] - ema50.iloc[-1]) / ema50.iloc[-1]) * 100) * 0.15
    
    # Thay ROC 20 bằng ROC 63 (1 quý)
    roc63 = close.pct_change(periods=63).iloc[-1] * 100 if len(close) > 63 else 0
    score_roc63 = roc63 * 0.15
    
    # Short-Term (Trọng số 10%)
    # Thay RSI 14 bằng RSI 21
    rsi21 = calculate_rsi(close, 21).iloc[-1]
    score_rsi = rsi21 * 0.05 if not np.isnan(rsi21) else 0
    
    ppo_hist = calculate_ppo_hist(close)
    last_3_hist = ppo_hist.tail(3).values
    score_ppo = 0
    if len(last_3_hist) == 3 and not np.isnan(last_3_hist).any():
        x = np.array([0, 1, 2])
        slope = np.polyfit(x, last_3_hist, 1)[0]
        if slope > 1: 
            score_ppo = 5.0
        elif slope < -1: 
            score_ppo = 0.0
        else: 
            score_ppo = 0.05 * ((slope + 1) * 50)
            
    # TỔNG ĐIỂM SCTR CUSTOM
    total_score = score_ema200 + score_roc252 + score_ema50 + score_roc63 + score_rsi + score_ppo

    # ==============================================================
    # 3. NHẬN DIỆN TÍN HIỆU VSA THEO TRADEGUIDER
    # ==============================================================
    df['Spread'] = df['High'] - df['Low']
    df['Avg_Spread'] = df['Spread'].rolling(20).mean()
    df['Close_Pos'] = np.where(df['Spread'] > 0, (df['Close'] - df['Low']) / df['Spread'], 0.5)
    df['Vol_High'] = df['Volume'] > (df['Vol_MA20'] * 1.2)
    df['Vol_Less_Than_Prev_2'] = (df['Volume'] < df['Volume'].shift(1)) & (df['Volume'] < df['Volume'].shift(2))
    df['Is_Down_Bar'] = df['Close'] < df['Open']
    df['Is_Up_Bar'] = df['Close'] > df['Open']
    
    scan_window = df.tail(vsa_lookback)
    latest_signal, signal_date, poe, sl = None, "", "", ""
    
    for i in range(len(scan_window)):
        idx = scan_window.index[i]
        bar = scan_window.iloc[i]
        support_20d = df['Low'].loc[:idx].tail(21).head(20).min()
        signal = None
        
        # Stopping Volume
        if bar['Is_Down_Bar'] and bar['Vol_High'] and bar['Close_Pos'] > 0.5:
            signal, poe, sl = "🔴 Stopping Vol", f"Quan sát quanh {round(bar['Low'], 2)}", f"Thủng {round(bar['Low']*0.95, 2)}"
        # No Supply
        elif bar['Is_Down_Bar'] and bar['Spread'] < bar['Avg_Spread'] and bar['Vol_Less_Than_Prev_2'] and bar['Close_Pos'] >= 0.5:
            signal, poe, sl = "🟢 No Supply", f"Mua vượt {round(bar['High'], 2)}", f"Thủng {round(bar['Low']*0.98, 2)}"
        # Spring
        elif bar['Low'] < support_20d and bar['Close_Pos'] >= 0.6 and bar['Vol_High']:
            signal, poe, sl = "🔥 Spring (Rũ Bỏ)", f"Mua quanh {round(bar['Close'], 2)}", f"Thủng {round(bar['Low']*0.97, 2)}"
        # SOS
        elif bar['Is_Up_Bar'] and bar['Spread'] > bar['Avg_Spread'] * 1.2 and bar['Vol_High'] and bar['Close_Pos'] >= 0.7:
            signal, poe, sl = "🚀 SOS (Cầu Lớn)", f"Chờ LPS về {round(bar['Close'] - (bar['Spread']*0.3), 2)}", f"Thủng {round(bar['Low'], 2)}"

        if signal:
            latest_signal, signal_date, final_poe, final_sl = signal, idx.strftime("%d/%m/%Y"), poe, sl

    return {
        "Giá Hiện Tại": round(close.iloc[-1], 2),
        "Thanh Khoản (20đ)": f"{int(current_vol_ma20):,}",
        "Total_Score": total_score,
        "VSA_Signal": latest_signal,
        "Ngày Tín Hiệu": signal_date,
        "POE": final_poe if latest_signal else "",
        "SL": final_sl if latest_signal else ""
    }

# ==========================================
# GIAO DIỆN WEB
# ==========================================
st.markdown("### 🦅 Radar Hợp Nhất: Top-Down Sector & Điểm Nổ Smart Money")
st.info("💡 Lõi SCTR đang sử dụng bộ tham số chu kỳ tài chính của Wyckoff Analytics: **ROC 252 (1 năm), ROC 63 (1 quý), RSI 21 (1 tháng)**.")

col1, col2, col3 = st.columns(3)
with col1:
    min_vol_input = st.number_input("LỌC THANH KHOẢN TỐI THIỂU:", min_value=10000, value=150000, step=50000)
with col2:
    lookback_input = st.number_input("TÌM TÍN HIỆU VSA (Số phiên qua):", min_value=1, value=10, max_value=20)
with col3:
    uploaded_file = st.file_uploader("Nạp CSV Mã tùy chọn (Cột 1 chứa mã)", type=["csv"])

if st.button("🚀 KÍCH HOẠT HỆ THỐNG TOP-DOWN"):
    raw_results = []
    
    tickers_to_scan = []
    if uploaded_file is not None:
        try:
            df_user = pd.read_csv(uploaded_file, header=None)
            raw_tickers = df_user.iloc[:, 0].dropna().astype(str).tolist()
            tickers_to_scan = [t.strip().upper() + ".VN" if not t.endswith(".VN") else t.strip().upper() for t in raw_tickers]
        except:
            st.error("Lỗi đọc file CSV.")
    else:
        tickers_to_scan = [t + ".VN" for tickers in DEFAULT_SECTORS.values() for t in tickers]
    
    if tickers_to_scan:
        my_bar = st.progress(0, text="Đang tải dữ liệu 2 năm và tính toán Custom SCTR...")
        total_tickers = len(tickers_to_scan)
        
        for i, t in enumerate(tickers_to_scan):
            df = get_data(t, "2y") # Lấy 2 năm dữ liệu để đủ tính ROC 252
            if df is not None:
                res = process_ultimate_wyckoff(df, min_vol_input, lookback_input)
