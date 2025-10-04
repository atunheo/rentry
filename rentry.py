import streamlit as st
import pandas as pd
import requests
import io
import time
import logging
from typing import Dict, Any, Optional

# Cấu hình logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Rentry Bulk Poster", 
    page_icon="🐷", 
    layout="centered",
    initial_sidebar_state="expanded"
)

st.title("🐷 Rentry Bulk Poster")
st.write("Upload file Excel có cột **content**, app sẽ đăng từng bài lên [rentry.co](https://rentry.co).")

# Sidebar với thông tin
with st.sidebar:
    st.header("ℹ️ Thông tin")
    st.write("**Cách sử dụng:**")
    st.write("1. Chuẩn bị file Excel với cột 'content'")
    st.write("2. Upload file và xem preview")
    st.write("3. Nhấn 'Bắt đầu đăng'")
    st.write("4. Tải file kết quả")
    
    st.header("⚠️ Lưu ý")
    st.write("- Mỗi bài đăng cách nhau 3 giây")
    st.write("- Nếu API fail sẽ tự động chuyển sang form")
    st.write("- Kiểm tra kết quả trước khi tải file")

uploaded_file = st.file_uploader("📂 Chọn file Excel (.xlsx)", type=["xlsx"])
delay = st.number_input("⏱ Giãn cách giữa các bài (giây)", min_value=0.0, value=3.0, step=0.5)

# Headers giả lập trình duyệt
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://rentry.co",
    "Referer": "https://rentry.co/",
    "Connection": "keep-alive"
}

def validate_content(content: str) -> bool:
    """Kiểm tra content có hợp lệ không"""
    if not content or content.strip() == "":
        return False
    if len(content.strip()) < 10:
        return False
    if content.lower() in ["nan", "null", "none"]:
        return False
    return True

def post_rentry(content: str, max_retries: int = 2) -> Dict[str, Any]:
    """
    Đăng bài lên rentry bằng API, nếu fail thì fallback sang form submit
    """
    # Validate content
    if not validate_content(content):
        return {"error": "Content không hợp lệ hoặc quá ngắn"}
    
    data = {"text": content.strip()}
    logger.info(f"Đang đăng bài với {len(content)} ký tự")

    # --- API Mode với retry ---
    for attempt in range(max_retries):
        try:
            r = requests.post("https://rentry.co/api/new", data=data, headers=HEADERS, timeout=30)
            logger.info(f"API attempt {attempt + 1}: Status {r.status_code}")
            
            if r.status_code == 200:
                try:
                    result = r.json()
                    logger.info("API thành công")
                    return result
                except Exception as e:
                    logger.warning(f"API trả về không phải JSON: {e}")
                    if attempt == max_retries - 1:
                        return {"error": "API trả về không phải JSON", "raw": r.text[:200]}
            else:
                logger.warning(f"API failed với status {r.status_code}")
                if attempt == max_retries - 1:
                    # Thử fallback
                    return post_rentry_form(content)
                    
        except Exception as e:
            logger.error(f"API Exception attempt {attempt + 1}: {e}")
            if attempt == max_retries - 1:
                return {"error": f"API Exception: {e}"}
        
        # Delay trước khi retry
        if attempt < max_retries - 1:
            time.sleep(2)
    
    return {"error": "Tất cả attempts đều fail"}

def post_rentry_form(content: str) -> Dict[str, Any]:
    """
    Fallback: giả lập submit form web
    """
    logger.info("Chuyển sang form mode")
    try:
        r = requests.post("https://rentry.co", data={"text": content}, headers=HEADERS, timeout=30)
        logger.info(f"Form mode: Status {r.status_code}, URL: {r.url}")
        
        if r.status_code == 200 and "rentry.co/" in r.url:
            # Nếu thành công, link sẽ ở r.url
            return {"url": r.url, "edit_code": "Chỉ có khi dùng API", "method": "form"}
        else:
            return {"error": f"Form mode fail: {r.status_code}", "raw": r.text[:200]}
    except Exception as e:
        logger.error(f"Form Exception: {e}")
        return {"error": f"Form Exception: {e}"}

if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file)
        logger.info(f"Đã load file Excel với {len(df)} dòng")

        if "content" not in df.columns:
            st.error("❌ File Excel phải có cột tên là `content`.")
            st.write("**Các cột có sẵn:**", list(df.columns))
        else:
            st.write("📋 Xem trước dữ liệu:")
            st.dataframe(df.head())
            
            # Thống kê dữ liệu
            total_rows = len(df)
            valid_content = df["content"].apply(lambda x: validate_content(str(x))).sum()
            st.info(f"📊 Tổng: {total_rows} dòng, {valid_content} dòng hợp lệ")

            if st.button("🚀 Bắt đầu đăng", type="primary"):
                # Progress bar
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                results = []
                success_count = 0
                error_count = 0

                for idx, row in df.iterrows():
                    content = str(row["content"]).strip()
                    
                    # Update progress
                    progress = (idx + 1) / total_rows
                    progress_bar.progress(progress)
                    status_text.text(f"Đang xử lý dòng {idx + 1}/{total_rows}...")
                    
                    if not validate_content(content):
                        results.append({
                            "row": idx+1, 
                            "status": "❌ Content không hợp lệ", 
                            "url": None, 
                            "edit_code": None,
                            "error": "Content quá ngắn hoặc trống"
                        })
                        error_count += 1
                        continue

                    logger.info(f"Đang xử lý dòng {idx + 1}")
                    res = post_rentry(content)

                    if "url" in res:
                        results.append({
                            "row": idx+1,
                            "status": "✅ Thành công",
                            "url": res["url"],
                            "edit_code": res.get("edit_code", "N/A"),
                            "method": res.get("method", "API")
                        })
                        success_count += 1
                        logger.info(f"Dòng {idx + 1} thành công: {res['url']}")
                    else:
                        results.append({
                            "row": idx+1,
                            "status": f"❌ Lỗi",
                            "url": None,
                            "edit_code": None,
                            "error": str(res.get("error", "Unknown error"))
                        })
                        error_count += 1
                        logger.error(f"Dòng {idx + 1} lỗi: {res}")

                    # Giãn cách
                    if delay > 0 and idx < len(df) - 1:
                        time.sleep(delay)

                # Hoàn thành
                progress_bar.progress(1.0)
                status_text.text("Hoàn tất!")
                
                result_df = pd.DataFrame(results)
                
                # Hiển thị kết quả
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("✅ Thành công", success_count)
                with col2:
                    st.metric("❌ Lỗi", error_count)
                with col3:
                    st.metric("📊 Tổng", total_rows)
                
                st.success("🎉 Hoàn tất đăng bài!")
                st.dataframe(result_df)

                # Xuất Excel kết quả
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine="openpyxl") as writer:
                    result_df.to_excel(writer, index=False, sheet_name="Results")
                output.seek(0)

                st.download_button(
                    label="📥 Tải file kết quả",
                    data=output,
                    file_name=f"rentry_results_{int(time.time())}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                
    except Exception as e:
        st.error(f"❌ Lỗi khi đọc file Excel: {e}")
        logger.error(f"File read error: {e}")
