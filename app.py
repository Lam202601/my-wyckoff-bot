import streamlit as st
import yfinance as yf
import pandas as pd
import time

st.set_page_config(page_title="Wyckoff Pro: Sức Mạnh Tương Đối", layout="wide")
st.title("🦅 Wyckoff Scanner: RS & POE Tối Ưu")

SECTORS = {
    "Ngân hàng": ["VCB.VN", "BID.VN", "CTG.VN", "TCB.VN", "MBB.VN"],
    "Chứng khoán": ["SSI.VN", "VND.VN", "HCM.VN", "VCI.VN", "SHS.VN"],
    "Thép": ["HPG.VN", "HSG.VN", "NKG.VN"],
    "Bất động sản": ["VHM.VN", "VIC.VN", "DXG.VN", "DIG.VN", "KBC.VN", "PDR.VN"],
    "Bán lẻ & Công nghệ": ["FPT.VN", "MWG.VN", "PNJ.VN", "FRT.VN", "DGW.VN"]
}

@st.cache_data(ttl=900)
def get_data(ticker, period="1y"):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period)
        if len(df) < 60: return None
        return df
    except:
        return None

# Tải thêm dữ liệu VN-Index để làm thước đo chuẩn
@st.cache_data(ttl=900)
def get_index_data(period="1y"):
    try:
        return yf.Ticker("^VNINDEX").history(period=period)
    except:
        return None

def analyze_poe(df, index_df, ticker):
    df = df.copy()
    index_df = index_df.copy()
    
    # 1. FIX LỖI TIMEZONE: Ép bỏ múi giờ để gộp dữ liệu không bị rỗng
    df.index = pd.to_datetime(df.index).tz_localize(None)
    index_df.index = pd.to_datetime(index_df.index).tz_localize(None)

    df['MA50'] = df['Close'].rolling(50).mean()
    df['Vol_MA20'] = df['Volume'].rolling(20).mean()
    
    # ---------------------------------------------------------
    # TÍNH TOÁN SỨC MẠNH TƯƠNG ĐỐI (RS) SO VỚI VN-INDEX
    # ---------------------------------------------------------
    combined = pd.merge(df['Close'], index_df['Close'], left_index=True, right_index=True, suffixes=('_s', '_i'))
    
    # CHỐT CHẶN AN TOÀN: Nếu dữ liệu gộp bị lỗi hoặc không đủ 20 phiên, bỏ qua mã này
    if len(combined) < 20: 
        return None 
        
    rs_line = combined['Close_s'] / combined['Close_i']
    rs_ma20 = rs_line.rolling(20).mean()
    
    is_rs_strong = rs_line.iloc[-1] > rs_ma20.iloc[-1]
    # ---------------------------------------------------------

    current_close = float(df['Close'].iloc[-1])
    current_vol = float(df['Volume'].iloc[-1])
    current_open = float(df['Open'].iloc[-1])
    
    recent_60 = df.tail(60)
    tr_high = float(recent_60['High'].max())
    tr_low = float(recent_60['Low'].min())
    
    if tr_low == 0: return None
    
    box_height = tr_high - tr_low
    box_percent = box_height / tr_low 
    bottom_zone = tr_low + (box_height * 0.25)
    
    phase = None
    vung_mua_poe = ""
    dieu_kien = ""
    cat_lo = ""

    # Chỉ xét mua khi Sức mạnh tương đối (RS) ủng hộ
    if is_rs_strong:
        # 1. SWING TRADE (PHA A/B)
        if box_percent >= 0.10 and current_close <= bottom_zone and current_close >= tr_low:
            if current_vol < float(df['Vol_MA20'].iloc[-1]) * 0.7:
                phase = "Pha A/B (Swing Range)"
                vung_mua_poe = f"Quanh {round(tr_low, 2)} - {round(bottom_zone, 2)}"
                dieu_kien = "Volume cạn kiệt, nến xanh rút chân."
                cat_lo = f"Thủng {round(tr_low * 0.97, 2)}"

        # 2. PHA E (Breakout)
        elif current_close > tr_high and current_close > float(df['MA50'].iloc[-1]):
            if current_vol > float(df['Vol_MA20'].iloc[-1]) * 1.5:
                phase = "Pha E (Breakout)"
                vung_mua_poe = f"Chờ test lại {round(tr_high, 2)}"
                dieu_kien = "Test đỉnh vol thấp (No Supply)."
                cat_lo = f"Thủng {round(tr_high * 0.95, 2)}"
                
        # 3. PHA D (SOS)
        elif current_close > float(df['MA50'].iloc[-1]) and current_close < tr_high:
            if current_vol > float(df['Vol_MA20'].iloc[-1]) * 1.2:
                phase = "Pha D (SOS)"
                vung_mua_poe = f"Chờ LPS quanh {round(float(df['MA50'].iloc[-1]), 2)}"
                dieu_kien = "Chỉnh nhẹ về MA50, vol cạn."
                cat_lo = f"Thủng {round(float(df['MA50'].iloc[-1]) * 0.96, 2)}"
                
        # 4. PHA C (Spring)
        elif current_close <= tr_low * 1.02:
            if current_close > current_open and current_vol > float(df['Vol_MA20'].iloc[-1]):
                phase = "Pha C (Spring)"
                vung_mua_poe = f"Mua tại {round(current_close, 2)}"
                dieu_kien = "Xác nhận rút chân thành công."
                cat_lo = f"Thủng {round(tr_low * 0.95, 2)}"

    if phase:
        return {
            "Mã": ticker.replace(".VN", ""), 
            "Giá HT": round(current_close, 2), 
            "Khung TR (Đáy-Đỉnh)": f"{round(tr_low, 2)} - {round(tr_high, 2)}",
            "Tín hiệu": phase,
            "RS": "💪 Khỏe hơn VNI",
            "Điểm Mua (POE)": vung_mua_poe,
            "Cắt Lỗ (SL)": cat_lo
        }
    return None
