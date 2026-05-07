import pytest
import re
import subprocess
import time
import socket
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
 
APP_URL = "http://localhost:8501"
 
 
def wait_for_port(host, port, timeout=30):
    """Wait until the app is actually accepting connections before proceeding."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except (ConnectionRefusedError, OSError):
            time.sleep(1)
    raise RuntimeError(f"App did not start on {host}:{port} within {timeout}s")
 
 
# ─────────────────────────────────────────────
# SETUP: start app, wait until it's ready, then open browser
# ─────────────────────────────────────────────
@pytest.fixture(scope="module")
def driver():
    # Start Streamlit app in the background
    app_process = subprocess.Popen(
        ["streamlit", "run", "front_end.py", "--server.headless", "true"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
 
    # Wait until port 8501 is actually open before launching browser
    wait_for_port("localhost", 8501, timeout=30)
    time.sleep(3)  # extra buffer for full JS render
 
    options = webdriver.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1280,800")
    options.add_argument("--disable-gpu")
    # NOTE: NOT using --headless so Chrome 146 renders JS properly
    # The browser window will briefly appear and close when tests finish
 
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )
    driver.get(APP_URL)
    time.sleep(5)  # wait for Streamlit JS to fully render
 
    yield driver
 
    driver.quit()
    app_process.terminate()
 
 
# ─────────────────────────────────────────────
# 1. INPUT VALIDATION TESTS (no browser needed)
# ─────────────────────────────────────────────
EMAIL_PATTERN = r'^[\w\.-]+@[\w\.-]+\.\w+$'
 
def is_valid_email(email):
    return bool(re.match(EMAIL_PATTERN, email))
 
def is_valid_name(name):
    return len(name) >= 2
 
def is_valid_phone(phone):
    return len(phone) >= 10
 
def is_valid_customer_id(cid):
    return len(cid) >= 2
 
 
class TestInputValidation:
 
    def test_valid_email(self):
        assert is_valid_email("john.doe@example.com") == True
 
    def test_invalid_email_no_at(self):
        assert is_valid_email("johndoeexample.com") == False
 
    def test_invalid_email_no_domain(self):
        assert is_valid_email("johndoe@") == False
 
    def test_invalid_email_empty(self):
        assert is_valid_email("") == False
 
    def test_valid_phone(self):
        assert is_valid_phone("1234567890") == True
 
    def test_invalid_phone_too_short(self):
        assert is_valid_phone("12345") == False
 
    def test_valid_name(self):
        assert is_valid_name("John Doe") == True
 
    def test_invalid_name_too_short(self):
        assert is_valid_name("J") == False
 
    def test_invalid_name_empty(self):
        assert is_valid_name("") == False
 
    def test_valid_customer_id(self):
        assert is_valid_customer_id("123456") == True
 
    def test_invalid_customer_id(self):
        assert is_valid_customer_id("1") == False
 
 
# ─────────────────────────────────────────────
# 2. UI TESTS
# ─────────────────────────────────────────────
class TestUIInteractions:
 
    def test_page_title_visible(self, driver):
        """Check the app title loads correctly"""
        WebDriverWait(driver, 30).until(
            lambda d: "Credit Risk Loan Prediction App" in d.page_source
        )
        assert "Credit Risk Loan Prediction App" in driver.page_source
 
    def test_all_input_fields_present(self, driver):
        """Check that key input fields are present on the page"""
        WebDriverWait(driver, 30).until(
            lambda d: "Loan Amount" in d.page_source
        )
        assert "Loan Amount" in driver.page_source
        assert "FICO Score" in driver.page_source
        assert "Annual Income" in driver.page_source
        assert "Loan Term" in driver.page_source
        assert "Home Ownership" in driver.page_source
 
    def test_predict_button_exists(self, driver):
        """Check that the Predict button is present"""
        wait = WebDriverWait(driver, 30)
        predict_btn = wait.until(
            EC.presence_of_element_located((By.XPATH, "//button[contains(., 'Predict')]"))
        )
        assert predict_btn is not None
 
    def test_error_shown_for_invalid_email(self, driver):
        """Clicking Predict without valid inputs should show a validation error"""
        wait = WebDriverWait(driver, 30)
        predict_btn = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Predict')]"))
        )
        predict_btn.click()
        time.sleep(3)
        assert "Invalid email format" in driver.page_source or \
               "Enter valid customer" in driver.page_source