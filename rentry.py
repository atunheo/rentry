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
    st.write("- **API** → **Session** → **Form** (3 phương thức)")
    st.write("- Tự động retry khi gặp lỗi 403/500")
    st.write("- Kiểm tra kết quả trước khi tải file")
    
    st.header("🔧 Phương thức đăng")
    st.write("1. **API Mode**: `rentry.co/api/new`")
    st.write("2. **Session Mode**: Duy trì cookies")
    st.write("3. **Form Mode**: 3 phương thức khác nhau")
    st.write("4. **Selenium Mode**: Giả lập trình duyệt thật")
    st.write("5. **Alternative**: dpaste.com, 0x0.st")
    
    st.header("⚠️ Yêu cầu hệ thống")
    st.write("- **Chrome/Chromium** cho Selenium")
    st.write("- **ChromeDriver** tự động tải")
    st.write("- **Internet** ổn định")

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
    # Giảm yêu cầu độ dài tối thiểu từ 10 xuống 3 ký tự
    if len(content.strip()) < 3:
        return False
    if content.lower() in ["nan", "null", "none", "undefined"]:
        return False
    return True

def post_rentry_with_session(content: str) -> Dict[str, Any]:
    """
    Thử đăng bài với session để duy trì cookies
    """
    logger.info("Thử với session mode")
    try:
        session = requests.Session()
        session.headers.update(HEADERS)
        
        # Lấy trang chủ trước để có cookies
        session.get("https://rentry.co", timeout=30)
        
        # Thử API với session
        r = session.post("https://rentry.co/api/new", data={"text": content}, timeout=30)
        logger.info(f"Session API: Status {r.status_code}")
        
        if r.status_code == 200:
            try:
                result = r.json()
                logger.info("Session API thành công")
                return result
            except Exception:
                pass
        
        # Thử form với session
        r = session.post("https://rentry.co", data={"text": content}, timeout=30)
        logger.info(f"Session Form: Status {r.status_code}, URL: {r.url}")
        
        if r.status_code == 200 and "rentry.co/" in r.url:
            return {"url": r.url, "edit_code": "Session mode", "method": "session"}
        
        return {"error": f"Session mode fail: {r.status_code}"}
        
    except Exception as e:
        logger.error(f"Session Exception: {e}")
        return {"error": f"Session Exception: {e}"}

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
                        # Thử session mode trước khi fallback form
                        session_result = post_rentry_with_session(content)
                        if "url" in session_result:
                            return session_result
                        return {"error": "API trả về không phải JSON", "raw": r.text[:200]}
            else:
                logger.warning(f"API failed với status {r.status_code}")
                if attempt == max_retries - 1:
                    # Thử session mode trước khi fallback form
                    session_result = post_rentry_with_session(content)
                    if "url" in session_result:
                        return session_result
                    # Thử form mode
                    form_result = post_rentry_form(content)
                    if "url" in form_result:
                        return form_result
                    # Thử selenium mode
                    selenium_result = post_rentry_selenium(content)
                    if "url" in selenium_result:
                        return selenium_result
                    # Thử alternative services
                    return post_rentry_alternative(content)
                    
        except Exception as e:
            logger.error(f"API Exception attempt {attempt + 1}: {e}")
            if attempt == max_retries - 1:
                # Thử session mode trước khi fallback form
                session_result = post_rentry_with_session(content)
                if "url" in session_result:
                    return session_result
                # Thử form mode
                form_result = post_rentry_form(content)
                if "url" in form_result:
                    return form_result
                # Thử selenium mode
                selenium_result = post_rentry_selenium(content)
                if "url" in selenium_result:
                    return selenium_result
                # Thử alternative services
                return post_rentry_alternative(content)
        
        # Delay trước khi retry
        if attempt < max_retries - 1:
            time.sleep(2)
    
    return {"error": "Tất cả attempts đều fail"}

def post_rentry_form(content: str) -> Dict[str, Any]:
    """
    Fallback: giả lập submit form web với nhiều phương thức
    """
    logger.info("Chuyển sang form mode")
    
    # Thử nhiều phương thức khác nhau
    methods = [
        {"url": "https://rentry.co", "data": {"text": content}},
        {"url": "https://rentry.co/", "data": {"text": content}},
        {"url": "https://rentry.co/new", "data": {"text": content}},
    ]
    
    for i, method in enumerate(methods):
        try:
            logger.info(f"Form method {i+1}: {method['url']}")
            
            # Headers khác nhau cho từng phương thức
            headers = HEADERS.copy()
            if i == 1:
                headers["Content-Type"] = "application/x-www-form-urlencoded"
            elif i == 2:
                headers["X-Requested-With"] = "XMLHttpRequest"
            
            r = requests.post(method["url"], data=method["data"], headers=headers, timeout=30)
            logger.info(f"Form method {i+1}: Status {r.status_code}, URL: {r.url}")
            
            if r.status_code == 200:
                # Kiểm tra response có chứa link rentry không
                if "rentry.co/" in r.url or "rentry.co/" in r.text:
                    # Tìm link trong response
                    import re
                    link_match = re.search(r'https://rentry\.co/[a-zA-Z0-9]+', r.text)
                    if link_match:
                        return {
                            "url": link_match.group(), 
                            "edit_code": "Chỉ có khi dùng API", 
                            "method": f"form_{i+1}"
                        }
                    elif "rentry.co/" in r.url:
                        return {
                            "url": r.url, 
                            "edit_code": "Chỉ có khi dùng API", 
                            "method": f"form_{i+1}"
                        }
            
            # Nếu không thành công, thử phương thức tiếp theo
            if i < len(methods) - 1:
                time.sleep(1)  # Delay giữa các attempts
                
        except Exception as e:
            logger.error(f"Form method {i+1} Exception: {e}")
            if i == len(methods) - 1:  # Lần cuối cùng
                return {"error": f"Tất cả form methods đều fail: {e}"}
    
    return {"error": f"Form mode fail: 403 - Tất cả phương thức đều bị từ chối"}

def post_rentry_selenium(content: str) -> Dict[str, Any]:
    """
    Phương thức Selenium: Giả lập trình duyệt thật
    """
    logger.info("Thử với Selenium mode")
    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.chrome.options import Options
        from selenium.common.exceptions import TimeoutException, WebDriverException
        
        # Cấu hình Chrome headless
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
        
        driver = None
        try:
            driver = webdriver.Chrome(options=chrome_options)
            driver.get("https://rentry.co")
            
            # Tìm textarea và nhập content
            wait = WebDriverWait(driver, 10)
            textarea = wait.until(EC.presence_of_element_located((By.NAME, "text")))
            textarea.clear()
            textarea.send_keys(content)
            
            # Tìm và click submit button
            submit_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            submit_button.click()
            
            # Chờ redirect và lấy URL
            wait.until(lambda driver: "rentry.co/" in driver.current_url)
            result_url = driver.current_url
            
            logger.info(f"Selenium thành công: {result_url}")
            return {"url": result_url, "edit_code": "Selenium mode", "method": "selenium"}
            
        except TimeoutException:
            logger.error("Selenium timeout - không tìm thấy element")
            return {"error": "Selenium timeout"}
        except WebDriverException as e:
            logger.error(f"Selenium WebDriver error: {e}")
            return {"error": f"Selenium WebDriver error: {e}"}
        finally:
            if driver:
                driver.quit()
                
    except ImportError:
        logger.warning("Selenium không được cài đặt")
        return {"error": "Selenium không khả dụng - cần cài đặt selenium"}
    except Exception as e:
        logger.error(f"Selenium Exception: {e}")
        return {"error": f"Selenium Exception: {e}"}

def post_rentry_alternative(content: str) -> Dict[str, Any]:
    """
    Phương thức thay thế: Thử các service paste khác
    """
    logger.info("Thử phương thức thay thế")
    
    # Thử dpaste.com
    try:
        import requests
        data = {"content": content, "syntax": "text"}
        r = requests.post("https://dpaste.com/api/v2/", data=data, timeout=30)
        if r.status_code == 201:
            result_url = r.text.strip()
            logger.info(f"Dpaste thành công: {result_url}")
            return {"url": result_url, "edit_code": "Dpaste mode", "method": "dpaste"}
    except Exception as e:
        logger.warning(f"Dpaste failed: {e}")
    
    # Thử 0x0.st
    try:
        files = {"file": content.encode()}
        r = requests.post("https://0x0.st", files=files, timeout=30)
        if r.status_code == 200:
            result_url = r.text.strip()
            logger.info(f"0x0.st thành công: {result_url}")
            return {"url": result_url, "edit_code": "0x0.st mode", "method": "0x0.st"}
    except Exception as e:
        logger.warning(f"0x0.st failed: {e}")
    
    return {"error": "Tất cả phương thức thay thế đều fail"}

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
            invalid_content = total_rows - valid_content
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("📊 Tổng dòng", total_rows)
            with col2:
                st.metric("✅ Hợp lệ", valid_content)
            with col3:
                st.metric("❌ Không hợp lệ", invalid_content)
            
            # Hiển thị các dòng không hợp lệ để debug
            if invalid_content > 0:
                st.warning(f"⚠️ Có {invalid_content} dòng không hợp lệ:")
                invalid_rows = []
                for idx, row in df.iterrows():
                    content = str(row["content"]).strip()
                    if not validate_content(content):
                        invalid_rows.append({
                            "Dòng": idx + 1,
                            "Content": content[:100] + "..." if len(content) > 100 else content,
                            "Độ dài": len(content)
                        })
                
                if invalid_rows:
                    st.dataframe(pd.DataFrame(invalid_rows))

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
                        # Debug info cho content không hợp lệ
                        debug_info = f"Content: '{content[:50]}...' (Length: {len(content)})"
                        results.append({
                            "row": idx+1, 
                            "status": "❌ Content không hợp lệ", 
                            "url": None, 
                            "edit_code": None,
                            "error": f"Content quá ngắn hoặc trống - {debug_info}"
                        })
                        error_count += 1
                        logger.warning(f"Dòng {idx + 1} content không hợp lệ: {debug_info}")
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
