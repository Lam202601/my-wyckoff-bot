import streamlit as st
import yfinance as yf
import pandas as pd
import time

st.set_page_config(page_title="Wyckoff Swing & Top-Down", layout="wide")
st.title("🦅 Wyckoff Scanner: Swing & Top-Down")
st.markdown("Hệ thống lọc tự động: Điểm Swing (Pha A/B) & Điểm Breakout (Pha C,D,E)")

# Phân loại ngành với đuôi .VN cho Yahoo Finance
SECTORS = {
    "Ngân hàng": ["VCB.VN", "BID.VN", "CTG.VN", "TCB.VN", "MBB.VN"],
    "Chứng khoán": ["SSI.VN", "VND.VN", "HCM.VN", "VCI.VN", "SHS.VN"],
    "Thép": ["HPG.VN", "HSG.VN", "NKG.VN"],
    "Bất động sản": ["VHM.VN", "VIC.VN", "DXG.VN", "DIG.VN", "KBC.VN", "PDR.VN"],
    "Bán lẻ & Công nghệ": ["FPT.VN", "MWG.VN", "PNJ.VN", "FRT.VN", "DGW.VN"]
}

@st.cache_data(ttl=3600)
def get_data(ticker):
    try:
        # Sử dụng yf.Ticker() để dữ liệu luôn trả về chuẩn định dạng
        stock = yf.Ticker(ticker)
        df = stock.history(period="6mo")
        if len(df) < 60: return None
        return df
    except:
        return None

def analyze_poe(df, ticker):
    # Tính MA và Volume trung bình
    df['MA50'] = df['Close'].rolling(50).mean()
    df['Vol_MA20'] = df['Volume'].rolling(20).mean()
    
    current_close = float(df['Close'].iloc[-1])
    current_vol = float(df['Volume'].iloc[-1])
    current_open = float(df['Open'].iloc[-1])
    
    # Tìm mức Đỉnh/Đáy trong 60 phiên (Trading Range)
    recent_60 = df.tail(60)
    tr_high = float(recent_60['High'].max())
    tr_low = float(recent_60['Low'].min())
    
    if tr_low == 0: return None
    
    box_height = tr_high - tr_low
    box_percent = box_height / tr_low # Tỷ lệ biên độ hộp
    bottom_zone = tr_low + (box_height * 0.25) # Vùng 25% đáy hộp
    
    phase = None
    signal = ""
    action = ""

    # ==========================================
    # 1. CHIẾN THUẬT SWING TRADE (PHA A / B)
    # ==========================================
    if box_percent >= 0.10 and current_close <= bottom_zone and current_close >= tr_low:
        if current_vol < float(df['Vol_MA20'].iloc[-1]) * 0.7:
            phase = "Pha A/B (Swing Range)"
            signal = "📉 Chạm biên dưới + Cạn cung"
            action = f"Mua Swing, Target: {round(tr_high, 2)}"

    # ==========================================
    # 2. CHIẾN THUẬT THEO XU HƯỚNG (PHA C, D, E)
    # ==========================================
    # PHA E (Breakout)
    elif current_close > tr_high and current_close > float(df['MA50'].iloc[-1]):
        if current_vol > float(df['Vol_MA20'].iloc[-1]) * 1.5:
            phase = "Pha E (Breakout)"
            signal = "🔥 Dòng tiền FOMO mạnh"
            action = "Mua theo đà tăng"

    # PHA D (SOS/LPS)
    elif current_close > float(df['MA50'].iloc[-1]) and current_close < tr_high:
        if current_vol > float(df['Vol_MA20'].iloc[-1]) * 1.2:
            phase = "Pha D (SOS)"
            signal = "⚡ Dấu hiệu sức mạnh"
            action = "Nắm giữ / Mua thêm"

    # PHA C (Spring)
    elif current_close <= tr_low * 1.02:
        if current_close > current_open and current_vol > float(df['Vol_MA20'].iloc[-1]):
            phase = "Pha C (Spring)"
            signal = "🚨 Quét đáy rút chân"
            action = "Mua rình rập"

    if phase:
        return {
            "Mã": ticker.replace(".VN", ""),
            "Giá": round(current_close, 2),
            "Giai đoạn": phase,
            "Tín hiệu": signal,
            "Hành động": action
        }
    return None

if st.button("🦅 BẮT ĐẦU QUÉT THỊ TRƯỜNG"):
    results = []
    progress_text = "Đang tải dữ liệu từ Yahoo Finance..."
    my_bar = st.progress(0, text=progress_text)
    
    total_tickers = sum(len(tickers) for tickers in SECTORS.values())
    current_count = 0
    
    for sector, tickers in SECTORS.items():
        st.markdown(f"### 🏭 {sector}")
        sector_results = []
        
        for t in tickers:
            df = get_data(t)
            if df is not None:
                res = analyze_poe(df, t)
                if res:
                    sector_results.append(res)
                    results.append(res)
            
            current_count += 1
            my_bar.progress(current_count / total_tickers, text=f"Đang quét {t}...")
            time.sleep(0.1)
        
        if sector_results:
            st.table(pd.DataFrame(sector_results))
        else:
            st.info(f"Ngành {sector} đang lình xình, chưa có điểm mua đẹp.")
            
    my_bar.empty()
    if results:
        st.success(f"Quét xong! Đã tìm thấy {len(results)} mã tiềm năng.")
        st.balloons()
