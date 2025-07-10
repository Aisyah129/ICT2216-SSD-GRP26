import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import time

@pytest.fixture
def driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(options=options)
    yield driver
    driver.quit()

def open_register_page(driver):
    driver.get("https://www.aisteadmai.shop/register/")
    time.sleep(10) 

# ✅ Test 1: Weak password (no special character)
def test_register_weak_password(driver):
    open_register_page(driver)
    driver.find_element(By.ID, "id_password").send_keys("Password123")  # no special char
    driver.find_element(By.ID, "id_confirm_password").send_keys("Password123")
    driver.find_element(By.ID, "id_name").send_keys("Valid Name")
    driver.find_element(By.ID, "id_location").send_keys("Singapore")
    driver.find_element(By.ID, "customCheckConsent").click()
    time.sleep(1)
    assert "Weak" in driver.page_source or "special character" in driver.page_source

# ✅ Test 2: Mismatched passwords
def test_register_mismatched_passwords(driver):
    open_register_page(driver)
    driver.find_element(By.ID, "id_password").send_keys("ValidPass!1")
    driver.find_element(By.ID, "id_confirm_password").send_keys("InvalidPass!2")
    driver.find_element(By.ID, "id_name").send_keys("Valid Name")
    driver.find_element(By.ID, "id_location").send_keys("Singapore")
    driver.find_element(By.ID, "customCheckConsent").click()
    time.sleep(1)
    assert "don't match" in driver.page_source or "do not match" in driver.page_source

# ✅ Test 3: Invalid name
def test_register_invalid_name(driver):
    open_register_page(driver)
    driver.find_element(By.ID, "id_password").send_keys("ValidPass!1")
    driver.find_element(By.ID, "id_confirm_password").send_keys("ValidPass!1")
    driver.find_element(By.ID, "id_name").send_keys("!@#$%^&*")
    driver.find_element(By.ID, "id_location").send_keys("Singapore")
    driver.find_element(By.ID, "customCheckConsent").click()
    time.sleep(1)
    assert "letters and spaces" in driver.page_source

# ✅ Test 4: Exceeding location length
def test_register_long_location(driver):
    open_register_page(driver)
    driver.find_element(By.ID, "id_password").send_keys("ValidPass!1")
    driver.find_element(By.ID, "id_confirm_password").send_keys("ValidPass!1")
    driver.find_element(By.ID, "id_name").send_keys("Valid Name")
    driver.find_element(By.ID, "id_location").send_keys("X" * 60)
    driver.find_element(By.ID, "customCheckConsent").click()
    time.sleep(1)
    assert len(driver.find_element(By.ID, "id_location").get_attribute("value")) <= 50
