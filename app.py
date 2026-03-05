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
    df['MA50'] = df['Close'].rolling(50).mean()
    df['Vol_MA20'] = df['Volume'].rolling(20).mean()
    
    # ---------------------------------------------------------
    # TÍNH TOÁN SỨC MẠNH TƯƠNG ĐỐI (RS) SO VỚI VN-INDEX
    # ---------------------------------------------------------
    # Khớp ngày giao dịch giữa cổ phiếu và Index
    combined = pd.merge(df['Close'], index_df['Close'], left_index=True, right_index=True, suffixes=('_s', '_i'))
    rs_line = combined['Close_s'] / combined['Close_i']
    rs_ma20 = rs_line.rolling(20).mean() # Đường trung bình của RS
    
    # Điều kiện tiên quyết: Cổ phiếu phải khỏe hơn Index (RS đang hướng lên)
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

    # Chỉ xét mua khi Sức mạnh tương đối (RS) ủng hộ, bỏ qua các mã đang yếu hơn thị trường
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

# --- GIAO DIỆN ---
st.markdown("### Quét các tín hiệu Wyckoff mạnh hơn thị trường chung")
if st.button("🦅 BẮT ĐẦU QUÉT"):
    results = []
    my_bar = st.progress(0, text="Đang tải dữ liệu VN-Index...")
    
    # Tải dữ liệu Index 1 lần để dùng chung
    index_df = get_index_data("6mo")
    
    if index_df is not None:
        total_tickers = sum(len(tickers) for tickers in SECTORS.values())
        count = 0
        
        for sector, tickers in SECTORS.items():
            for t in tickers:
                df = get_data(t, "6mo")
                if df is not None:
                    res = analyze_poe(df, index_df, t)
                    if res: results.append(res)
                count += 1
                my_bar.progress(count / total_tickers, text=f"Đang quét {t}...")
                time.sleep(0.1)
                
        my_bar.empty()
        if results:
            st.success(f"Quét xong! Tìm thấy {len(results)} mã thỏa mãn tiêu chí.")
            st.dataframe(pd.DataFrame(results))
            st.balloons()
        else:
            st.info("Chưa có mã nào thỏa mãn tiêu chuẩn Sức mạnh tương đối và Wyckoff hôm nay.")
    else:
        st.error("Lỗi tải dữ liệu VN-Index. Vui lòng thử lại sau.")

# Lưu ý: Phần code Tab 2 (Backtest) tạm thời mình rút gọn trong hiển thị này để bạn dễ copy phần lọc. 
# Nếu bạn cần chèn vào code cũ có sẵn Tab 2 thì chỉ cần chép đè hàm `analyze_poe` và bổ sung `get_index_data` là được.
