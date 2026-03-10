import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import time
import datetime
import io

st.set_page_config(page_title="GGU Master V29.1: Fort Knox", layout="wide")
st.title("🏛️ Hệ Thống GGU: Bản Bảo Mật Tối Đa (V29.1)")
st.markdown("Xuất file Excel (.xlsx) chuẩn hóa. Code đã bẻ dòng chống lỗi Copy/Paste.")

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
