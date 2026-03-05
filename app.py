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
    
    # Tìm mức Đỉnh/Đáy trong 60 phiên gần nhất (Trading Range)
    recent_60 = df.tail(60)
    tr_high = recent_60['high'].max()
    tr_low = recent_60['low'].min()
    
    # LOGIC POE (PHA C, D, E)
    phase = None
    signal_strength = ""

    # 1. PHA E (Mark-up): Giá vượt Trading Range, MA50 > MA200, Volume vào mạnh
    if current_close > tr_high and current_close > df['MA50'].iloc[-1] > df['MA200'].iloc[-1]:
        if current_vol > df['Vol_MA20'].iloc[-1] * 1.5:
            phase = "Pha E (Breakout/Mark-up)"
            signal_strength = "🔥 Dòng tiền FOMO cực mạnh"

    # 2. PHA D (LPS/SOS): Đang tiến lên ranh giới trên của TR, đáy sau cao hơn đáy trước
    elif current_close > df['MA50'].iloc[-1] and current_close < tr_high:
        if current_vol > df['Vol_MA20'].iloc[-1] * 1.2: # Nến tăng Vol lớn (SOS)
            phase = "Pha D (SOS/Tiến về kháng cự)"
            signal_strength = "⚡ Dấu hiệu sức mạnh"
        elif current_vol < df['Vol_MA20'].iloc[-1] * 0.7: # Nến chỉnh Vol nhỏ (LPS)
            phase = "Pha D (LPS - Điểm hỗ trợ cuối)"
            signal_strength = "🛡️ Chỉnh cạn cung, an toàn"

    # 3. PHA C (Spring/Test): Giá quét qua hỗ trợ hoặc test lại đáy với Vol thấp
    elif current_close <= tr_low * 1.05 and current_close >= tr_low: # Quanh quẩn đáy hộp
        if current_vol < df['Vol_MA20'].iloc[-1] * 0.6: # Cạn cung cực đại
            phase = "Pha C (Test/Cạn cung)"
            signal_strength = "🤫 Cá mập đè giá, hết áp lực bán"

    if phase:
        return {
            "Mã": ticker,
            "Giá": current_close,
            "Giai đoạn Wyckoff": phase,
            "Động lượng (Volume)": signal_strength
        }
    return None

if st.button("🦅 QUÉT TOP-DOWN TOÀN THỊ TRƯỜNG"):
    st.write("Đang tải dữ liệu Real-time từ thị trường VN...")
    results = []
    
    for sector, tickers in SECTORS.items():
        st.markdown(f"### 🏭 Ngành: {sector}")
        sector_results = []
        
        for t in tickers:
            df = get_data(t)
            if df is not None:
                res = analyze_poe(df, t)
                if res:
                    sector_results.append(res)
                    results.append(res)
        
        if sector_results:
            st.table(pd.DataFrame(sector_results))
        else:
            st.info(f"Chưa có mã nào đạt POE tại ngành {sector} hôm nay.")
            
    if results:
        st.success(f"Tất cả hoàn tất! Đã tóm được {len(results)} mã có điểm POE đẹp.")
        st.balloons()
