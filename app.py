import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import time
import datetime
import io

st.set_page_config(page_title="GGU Master V29: Fort Knox", layout="wide")
st.title("🏛️ Hệ Thống GGU: Bản Bảo Mật Tối Đa (V29)")
st.markdown("Xuất file định dạng Excel (.xlsx) tương thích hoàn hảo 100% với Google Sheets. Bảo mật tuyệt đối dữ liệu cá nhân.")

# TỪ ĐIỂN NGÀNH CHUẨN (264 MÃ TOÀN DIỆN)
DEFAULT_SECTORS = {
    "Ngân hàng": ["VCB","BID","CTG","TCB","MBB","STB","VPB","ACB","HDB","VIB","TPB","SHB","MSB","LPB","EIB","OCB","SSB","NAB","BAB","KLB","ABB","BVB","SGB","VAB","PGB"],
    "Chứng khoán": ["SSI","VND","HCM","VCI","SHS","MBS","FTS","BSI","CTS","AGR","VIX","ORS","VDS","BVS","TCI","TVS","VIG","APG","VFS","DSC","SBS","AAS","EVS","IVS"],
    "Bất động sản": ["VHM","VIC","VRE","DXG","DIG","PDR","NLG","NVL","CEO","HDC","KDH","NTL","TCH","IJC","CRE","SCR","HQC","DXS","KHG","HDG","SJS","NBB","ITC","QCG","VPI","TDC","IDJ","API","NHA","CSC"],
    "BĐS Khu công nghiệp": ["KBC","IDC","SZC","VGC","PHR","BCM","NTC","SIP","TIG","D2D","TIP","SNZ","SZL","ITA","LHG","MH3"],
    "Công nghệ & Viễn thông": ["FPT","VGI","CTR","CMG","ELC","FOX","TTN","VNZ","ITD","SGT","PIA","FOC","ICT"],
    "Bán lẻ & Đa ngành": ["MWG","PNJ","FRT","DGW","PET","HAX","VEA","TLG"], 
    "Thép & Sản phẩm thép": ["HPG","HSG","NKG","VGS","SMC","TLH","TVN","POM"],
    "Vật liệu xây dựng": ["HT1","BCC","KSB","DHA","VLB","VCS","PLC","PTB","BMP","NTP","AAA","CTI"],
    "Dầu khí": ["GAS","PVD","PVS","BSR","PLX","OIL","PVC","PSH","PVB","POS","PGC"],
    "Hóa chất & Phân bón": ["DGC","DCM","DPM","CSV","BFC","LAS","DDV","VTZ","PAT","BSL"],
    "Thực phẩm & Đồ uống": ["SAB","VNM","MSN","KDC","MCH","SBT","QNS","VSN","KDF","SLS","LSS"],
    "Thủy sản & Nông nghiệp": ["VHC","ANV","IDI","FMC","DBC","HAG","BAF","PAN","TAR","LTG","ASM","CMX","MPC","HNG","VSF","SJF"],
    "Vận tải & Logistics": ["GMD","HAH","VSC","PVT","VOS","VIP","VTO","PHP","SGP","MVN","DXP","TCL","PDN","VTP","ILB","STG"],
    "Hàng không & Du lịch": ["ACV","HVN","VJC","AST","SAS","SCD","SKG"], 
    "Điện, Thiết bị điện & Đa ngành": ["POW","REE","PC1","NT2","GEG","TV2","QTP","HND","BWE","TDM","GEX","PGV"],
    "Xây dựng & Đầu tư công": ["VCG","HHV","LCG","C4G","HBC","CTD","FCN","HUT","DPG","CII","L14","EVG","VEC","TCD","CTI","HTN","MST"],
    "Dệt may": ["TNG","VGT","GIL","MSH","STK","TCM","VGG","M10"],
    "Cao su tự nhiên": ["GVR","DRC","DRI","DPR","TRC","CSM","BRR"],
    "Bảo hiểm": ["BVH","BMI","MIG","PVI","VNR","PTI","BIC"],
    "Y tế & Dược phẩm": ["DHG","IMP","DVN","TRA","DBD","DCL","JVC"]
}
TICKER_TO_SECTOR = {t: sector for sector, tickers in DEFAULT_SECTORS.items() for t in tickers}

UPCOM_TICKERS = {"VGI","FOX","TTN","VNZ","VEA","OIL","MCH","QNS","ACV","SAS","DDV","VSN","ABB","BVB","KLB","VFS","PAT","VSF","SCD","SGB","VAB","PGB","SBS","AAS","MH3","TVN","POS","BSL","PGV","VGG","M10","BRR"}
HNX_TICKERS = {"SHS","MBS","BVS","VIG","CEO","IDC","TIG","PVS","PVC","LAS","TAR","HUT","L14","TNG","BAB","EVS","IVS","IDJ","API","CSC","SLS","MST","PTI"}

def get_exchange(ticker):
    if ticker in UPCOM_TICKERS: return "UPCoM"
    if ticker in HNX_TICKERS: return "HNX"
    return "HOSE" 

# --- THUẬT TOÁN TÍNH TOÁN LÕI ---
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
    return ppo - ppo.ewm(span=9, adjust=False).mean()

def get_sctr_score(df):
    close = df['Close']
    ema200 = close.ewm(span=200, adjust=False).mean().iloc[-1]
    score_ema200 = (((close.iloc[-1] - ema200) / ema200) * 100) * 0.30
    roc252 = close.pct_change(periods=252).iloc[-1] * 100 if len(close) > 252 else 0
    score_roc252 = roc252 * 0.30
    ema50 = close.ewm(span=50, adjust=False).mean().iloc[-1]
    score_ema50 = (((close.iloc[-1] - ema50) / ema50) * 100) * 0.15
    roc63 = close.pct_change(periods=63).iloc[-1] * 100 if len(close) > 63 else 0
    score_roc63 = roc63 * 0.15
    rsi21 = df['RSI21'].iloc[-1]
    score_rsi = rsi21 * 0.05 if not np.isnan(rsi21) else 0
    
    ppo_hist = calculate_ppo_hist(close)
    last_3_hist = ppo_hist.tail(3).values
    score_ppo = 0
    if len(last_3_hist) == 3 and not np.isnan(last_3_hist).any():
        slope = np.polyfit([0, 1, 2], last_3_hist, 1)[0]
        if slope > 1: score_ppo = 5.0
        elif slope < -1: score_ppo = 0.0
        else: score_ppo = 0.05 * ((slope + 1) * 50)
    
    return score_ema200 + score_roc252 + score_ema50 + score_roc63 + score_rsi + score_ppo

def analyze_ticker_data(ticker_df, min_volume, vsa_lookback, spring_lookback, max_penetration):
    if ticker_df is None or len(ticker_df) < 280: return None
    
    df = ticker_df.copy()
    df.index = pd.to_datetime(df.index).tz_localize(None)
    
    df['Vol_MA20'] = df['Volume'].rolling(20).mean()
    if float(df['Vol_MA20'].iloc[-1]) < min_volume: return None
    
    df['RSI21'] = calculate_rsi(df['Close'], 21)
    df['ROC252'] = df['Close'].pct_change(periods=252) * 100
    df['ROC63'] = df['Close'].pct_change(periods=63) * 100
    df['MA252'] = df['Close'].rolling(window=252).mean()
    
    score_current = get_sctr_score(df)
    score_past = get_sctr_score(df.iloc[:-10])
    
    current_close = float(df['Close'].iloc[-1])
    current_ma252 = df['MA252'].iloc[-1]
    current_rsi = df['RSI21'].iloc[-1]
    
    env_pct = (current_close - current_ma252) / current_ma252 * 100
    
    crossover_condition = (df['ROC252'] > 0) & (df['ROC252'] > df['ROC63'])
    streak = 0
    for val in crossover_condition.iloc[::-1]:
        if val: streak += 1
        else: break
            
    is_long_term_trend = streak >= 21
    
    trend_context = "➖ Đi ngang / Tích lũy"
    if env_pct <= -10 and current_rsi < 35:
        trend_context = f"🟢 Vùng Đảo Chiều Đáy (Env {env_pct:.1f}%)"
    elif env_pct >= 30 and current_rsi > 70:
        trend_context = f"🔴 Cảnh báo Đu đỉnh (Env +{env_pct:.1f}%)"
    elif is_long_term_trend and current_close > current_ma252:
        trend_context = "🚀 Tín hiệu vào Trend Dài Hạn"
    elif streak > 0 and streak < 21:
        trend_context = f"⏳ Chờ xác nhận Trend (Ngày {streak}/21)"
    
    df['Spread'] = df['High'] - df['Low']
    df['Avg_Spread'] = df['Spread'].rolling(20).mean()
    df['Close_Pos'] = np.where(df['Spread'] > 0, (df['Close'] - df['Low']) / df['Spread'], 0.5)
    df['Vol_High'] = df['Volume'] > (df['Vol_MA20'] * 1.2)
    df['Vol_Less_Than_Prev_2'] = (df['Volume'] < df['Volume'].shift(1)) & (df['Volume'] < df['Volume'].shift(2))
    df['Is_Down_Bar'] = df['Close'] < df['Open']
    df['Is_Up_Bar'] = df['Close'] > df['Open']
    
    past_63_days = df.tail(63)
    has_stopping_volume_past = False
    for i in range(len(past_63_days) - vsa_lookback):
        if past_63_days.iloc[i]['Is_Down_Bar'] and past_63_days.iloc[i]['Vol_High'] and past_63_days.iloc[i]['Close_Pos'] > 0.4:
            has_stopping_volume_past = True
            break

    scan_window = df.tail(vsa_lookback)
    latest_signal, signal_date, poe, sl, struct_eval = None, "", "", "", ""
    
    for i in range(len(scan_window)):
        idx = scan_window.index[i]
        bar = scan_window.iloc[i]
        current_loc = df.index.get_loc(idx)
        
        support_low = df['Low'].iloc[max(0, current_loc - spring_lookback) : current_loc].min() if current_loc > 0 else bar['Low']
        signal = None
        
        if bar['Is_Down_Bar'] and bar['Vol_High'] and bar['Close_Pos'] > 0.4:
            signal, poe, sl = "🔴 Stopping Vol", f"Quan sát {round(bar['Low'])}", f"Thủng {round(bar['Low']*0.95)}"
        elif bar['Is_Down_Bar'] and bar['Spread'] < bar['Avg_Spread'] and bar['Vol_Less_Than_Prev_2'] and bar['Close_Pos'] >= 0.4:
            signal, poe, sl = "🟢 No Supply", f"Mua vượt {round(bar['High'])}", f"Thủng {round(bar['Low']*0.98)}"
        elif bar['Low'] < support_low:
            penetration_pct = (support_low - bar['Low']) / support_low * 100
            if (penetration_pct <= max_penetration and bar['Close'] >= support_low and bar['Close_Pos'] >= 0.1 and bar['Volume'] > df['Vol_MA20'].iloc[current_loc]):
                signal, poe, sl = "🔥 Spring", f"Mua {round(bar['Close'])}", f"Thủng {round(bar['Low'])}"
        elif bar['Is_Up_Bar'] and bar['Spread'] > bar['Avg_Spread'] * 1.2 and bar['Vol_High'] and bar['Close_Pos'] >= 0.7:
            signal, poe, sl = "🚀 SOS", f"Chờ LPS {round(bar['Close'] - (bar['Spread']*0.3))}", f"Thủng {round(bar['Low'])}"

        if signal:
            latest_signal, signal_date, poe, sl = signal, idx.strftime("%d/%m/%Y"), poe, sl
            if signal in ["🟢 No Supply", "🔥 Spring"]:
                struct_eval = "🌟 Mua Vàng (Đã rũ SC)" if has_stopping_volume_past else "⏳ Sớm (Chưa có SC)"
            elif signal == "🔴 Stopping Vol":
                struct_eval = "👀 Watchlist (Đợi Test đáy)"
            elif signal == "🚀 SOS":
                struct_eval = "📈 Đánh Đẩy giá (Markup)"

    return {
        "Giá Hiện Tại": current_close, 
        "Thanh Khoản (20đ)": f"{int(df['Vol_MA20'].iloc[-1]):,}",
        "Score_Current": score_current,
        "Score_Past": score_past,
        "VSA_Signal": latest_signal,
        "Đánh giá Cấu trúc": struct_eval,
        "Vị thế Trend (MA252)": trend_context,
        "Ngày Tín Hiệu": signal_date,
        "POE": poe,
        "SL": sl
    }

# ==========================================
# KHỞI TẠO BỘ NHỚ (SESSION STATE)
# ==========================================
if 'app_data' not in st.session_state:
    st.session_state.app_data = None
if 'scan_time' not in st.session_state:
    st.session_state.scan_time = 0
if 'last_update_time' not in st.session_state:
    st.session_state.last_update_time = ""

# --- HÀM XUẤT FILE EXCEL (.xlsx) ---
def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='GGU_Master_Data')
    processed_data = output.getvalue()
    return processed_data

# ==========================================
# GIAO DIỆN WEB
# ==========================================
current_month = datetime.datetime.now().month
if current_month in [11, 12, 1]: st.info("🌱 **GIAI ĐOẠN HIỆN TẠI: GOM HÀNG CHỜ K
