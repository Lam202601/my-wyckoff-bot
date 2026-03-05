import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
# Thư viện dữ liệu chứng khoán VN xịn nhất hiện nay
from vnstock import stock_historical_data 

st.set_page_config(page_title="Wyckoff Top-Down Screener", layout="wide")
st.title("🦅 Wyckoff Top-Down POE Scanner")
st.markdown("Lọc Ngành dẫn dắt ➡️ Cổ phiếu Leader ➡️ Điểm vào lệnh Pha C, D, E")

# Phân loại ngành cơ bản (Bạn có thể bổ sung thêm)
SECTORS = {
    "Ngân hàng": ["VCB", "BID", "CTG", "TCB", "MBB", "ACB", "VPB", "STB"],
    "Chứng khoán": ["SSI", "VND", "HCM", "VCI", "SHS", "MBS", "FTS"],
    "Thép": ["HPG", "HSG", "NKG", "VGS"],
    "Bất động sản": ["VHM", "VIC", "DXG", "DIG", "KBC", "PDR", "NLG"],
    "Bán lẻ & Công nghệ": ["FPT", "MWG", "PNJ", "FRT", "DGW"]
}

# Hàm lấy dữ liệu từ vnstock
@st.cache_data(ttl=3600) # Lưu cache 1 giờ để web không bị đơ
def get_data(ticker, days=150):
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    try:
        # Tải dữ liệu O-H-L-C-V
        df = stock_historical_data(symbol=ticker, start_date=start_date, end_date=end_date, resolution="1D", type="stock")
        if df is not None and not df.empty:
            df['close'] = pd.to_numeric(df['close'])
            df['volume'] = pd.to_numeric(df['volume'])
            return df
    except:
        return None
    return None

def analyze_poe(df, ticker):
    # Tính toán các đường MA và Volume
    df['MA50'] = df['close'].rolling(50).mean()
    df['MA200'] = df['close'].rolling(200).mean()
    df['Vol_MA20'] = df['volume'].rolling(20).mean()
    
    current_close = df['close'].iloc[-1]
    current_vol = df['volume'].iloc[-1]
    
    # Kẻ Hộp Darvas / Trading Range trong 60 phiên gần nhất
    recent_60 = df.tail(60)
    tr_high = recent_60['high'].max()
    tr_low = recent_60['low'].min()
    box_height = tr_high - tr_low
    box_percent = box_height / tr_low # Tính tỷ lệ % biên độ của hộp
    
    # Định nghĩa ranh giới 25% sát đáy hộp
    bottom_zone = tr_low + (box_height * 0.25) 
    
    phase = None
    signal_strength = ""
    action = ""

    # ==========================================
    # 1. CHIẾN THUẬT SWING TRADE (PHA A / B)
    # ==========================================
    # Điều kiện: Biên độ hộp > 10%, giá đang nằm ở 25% biên dưới, và Volume cạn kiệt
    if box_percent >= 0.10 and current_close <= bottom_zone and current_close >= tr_low:
        if current_vol < df['Vol_MA20'].iloc[-1] * 0.7: # Cạn cung cực độ
            phase = "Pha A/B (Swing Range)"
            signal_strength = "📉 Giá chạm biên dưới SC/ST + Cạn cung"
            action = f"Mua Swing - Chốt lời quanh {round(tr_high, 2)}"

    # ==========================================
    # 2. CHIẾN THUẬT THEO XU HƯỚNG (PHA C, D, E)
    # ==========================================
    # PHA E (Mark-up): Vượt đỉnh hộp với Vol lớn
    elif current_close > tr_high and current_close > df['MA50'].iloc[-1]:
        if current_vol > df['Vol_MA20'].iloc[-1] * 1.5:
            phase = "Pha E (Breakout đỉnh)"
            signal_strength = "🔥 Dòng tiền FOMO cực mạnh"
            action = "Mua theo đà tăng"

    # PHA D (SOS/LPS): Vượt MA50, nằm ở nửa trên của hộp, Vol vào
    elif current_close > df['MA50'].iloc[-1] and current_close < tr_high:
        if current_vol > df['Vol_MA20'].iloc[-1] * 1.2:
            phase = "Pha D (SOS - Dấu hiệu sức mạnh)"
            signal_strength = "⚡ Dòng tiền lớn đẩy giá lên"
            action = "Nắm giữ / Mua thêm"

    # PHA C (Spring/Test): Giá quét thủng đáy hộp rồi rút chân
    elif current_close < tr_low * 1.02: # Rơi xuống dưới đáy hoặc sát mép dưới
        if df['close'].iloc[-1] > df['open'].iloc[-1] and current_vol > df['Vol_MA20'].iloc[-1]: 
            # Rút chân (đóng cửa > mở cửa) với Vol khá -> Cú lừa Spring
            phase = "Pha C (Spring/Cú rũ bỏ)"
            signal_strength = "🚨 Quét Stop-loss rút chân"
            action = "Mua rình rập"

    if phase:
        return {
            "Mã": ticker,
            "Giá": round(current_close, 2),
            "Giai đoạn": phase,
            "Tín hiệu": signal_strength,
            "Hành động": action
        }
    return None
