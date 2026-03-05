import streamlit as st
import yfinance as yf
import pandas as pd
import time

# Cấu hình giao diện Web
st.set_page_config(page_title="Wyckoff Auto-Scanner", layout="wide")
st.title("🎯 Wyckoff Auto-Scanner 2026")
st.markdown("Hệ thống tự động quét các mã có dòng tiền lớn và siết nền theo Wyckoff.")

# DANH SÁCH "VŨ TRỤ" CỔ PHIẾU (Các mã thanh khoản lớn nhất VN, nơi cá mập hoạt động)
VN_UNIVERSE = [
    # Ngân hàng & Chứng khoán
    "VCB.VN", "BID.VN", "CTG.VN", "TCB.VN", "MBB.VN", "VPB.VN", "ACB.VN", "STB.VN", "SHB.VN", "HDB.VN", "VIB.VN", "LPB.VN",
    "SSI.VN", "VND.VN", "HCM.VN", "VCI.VN", "SHS.VN", "MBS.VN", "FTS.VN", "BSI.VN",
    # Bất động sản & KCN
    "VHM.VN", "VIC.VN", "VRE.VN", "NVL.VN", "DIG.VN", "DXG.VN", "PDR.VN", "KBC.VN", "NLG.VN", "CEO.VN", "HDG.VN",
    "GVR.VN", "IDC.VN", "SZC.VN", "VGC.VN", "PHR.VN",
    # Thép, Dầu khí, Hóa chất
    "HPG.VN", "HSG.VN", "NKG.VN", "VGS.VN",
    "PVD.VN", "PVS.VN", "BSR.VN", "GAS.VN", "PLX.VN",
    "DGC.VN", "DPM.VN", "DCM.VN", "CSV.VN",
    # Bán lẻ, Công nghệ, Năng lượng
    "FPT.VN", "MWG.VN", "PNJ.VN", "MSN.VN", "VNM.VN", "SAB.VN", "FRT.VN", "DGW.VN",
    "REE.VN", "PC1.VN", "GEX.VN", "VHC.VN", "ANV.VN"
]
# Ghi chú: Bạn có thể copy paste thêm hàng trăm mã khác vào danh sách này.

def scan_wyckoff(ticker):
    try:
        stock = yf.download(ticker, period="1y", interval="1d", progress=False)
        index = yf.download("^VNINDEX", period="1y", interval="1d", progress=False)
        if len(stock) < 100: return None

        combined = pd.merge(stock['Close'], index['Close'], left_index=True, right_index=True, suffixes=('_s', '_i'))
        rs_line = combined['Close_s'] / combined['Close_i']
        rs_sma20 = rs_line.rolling(window=20).mean()
        
        last_close = float(stock['Close'].iloc[-1])
        ma200 = float(stock['Close'].rolling(window=200).mean().iloc[-1])
        
        recent = stock.tail(30)
        tr_width = float((recent['High'].max() - recent['Low'].min()) / recent['Low'].min())
        recent_vol = float(recent['Volume'].mean())
        avg_vol = float(stock['Volume'].tail(50).mean())

        # LOGIC LỌC TỰ ĐỘNG
        if last_close > ma200 and rs_line.iloc[-1] > rs_sma20.iloc[-1] and tr_width < 0.12 and recent_vol < avg_vol:
            return {
                "Mã": ticker.replace(".VN", ""), # Cắt chữ .VN cho đẹp
                "Giá hiện tại": round(last_close, 2),
                "Siết nền": f"{round(tr_width*100, 2)}%",
                "Đánh giá": "🔥 Đạt chuẩn Tích lũy"
            }
    except:
        return None
    return None

st.write(f"Vũ trụ theo dõi hiện tại: **{len(VN_UNIVERSE)} mã thanh khoản lớn nhất**.")

if st.button("🚀 BẤM ĐỂ QUÉT TOÀN BỘ THỊ TRƯỜNG"):
    results = []
    
    # Tạo thanh tiến trình để bạn biết bot đang quét đến đâu
    progress_text = "Đang rà soát dữ liệu thị trường..."
    my_bar = st.progress(0, text=progress_text)
    
    for i, t in enumerate(VN_UNIVERSE):
        res = scan_wyckoff(t)
        if res: 
            results.append(res)
        # Cập nhật thanh tiến trình
        percent_complete = int(((i + 1) / len(VN_UNIVERSE)) * 100)
        my_bar.progress(percent_complete, text=f"Đang quét {t} ({percent_complete}%)")
        time.sleep(0.1) # Nghỉ một chút để không bị Yahoo chặn do request quá nhanh
        
    my_bar.empty() # Xóa thanh tiến trình khi xong
    
    if results:
        st.balloons()
        st.success(f"Tuyệt vời! Bot đã tìm thấy {len(results)} mã đạt chuẩn Wyckoff hôm nay:")
        st.dataframe(pd.DataFrame(results), use_container_width=True)
    else:
        st.warning("Hôm nay chưa có mã nào đạt chuẩn. Mọi thứ vẫn đang rủi ro hoặc chưa nén đủ chặt!")
