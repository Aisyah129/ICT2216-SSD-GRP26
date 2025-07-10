import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import time

# ✅ Fixture: Headless Chrome browser
@pytest.fixture
def driver():
    options = Options()
    options.add_argument("--headless")
    driver = webdriver.Chrome(options=options)
    yield driver
    driver.quit()



# ✅ Test 1: Age validation
def test_invalid_age_input(driver):
    login(driver)
    driver.get("https://www.aisteadmai.shop/profile/")
    driver.find_element(By.ID, "editProfileBtn").click()
    age = driver.find_element(By.NAME, "age")
    age.clear()
    age.send_keys("17")
    driver.find_element(By.ID, "saveProfileBtn").click()
    assert int(age.get_attribute("value")) < 18

# ✅ Test 2: Height too tall
def test_invalid_height_input(driver):
    login(driver)
    driver.get("https://www.aisteadmai.shop/profile/")
    driver.find_element(By.ID, "editProfileBtn").click()
    height = driver.find_element(By.NAME, "height_cm")
    height.clear()
    height.send_keys("300")
    driver.find_element(By.ID, "saveProfileBtn").click()
    assert int(height.get_attribute("value")) > 250

# ✅ Test 3: Invalid occupation pattern
def test_invalid_occupation_pattern(driver):
    login(driver)
    driver.get("https://www.aisteadmai.shop/profile/")
    driver.find_element(By.ID, "editProfileBtn").click()
    occ = driver.find_element(By.NAME, "occupation")
    occ.clear()
    occ.send_keys("###INVALID###")
    driver.find_element(By.ID, "saveProfileBtn").click()
    assert occ.get_attribute("pattern") is not None

# ✅ Test 4: Location maxlength
def test_exceed_location_length(driver):
    login(driver)
    driver.get("https://www.aisteadmai.shop/profile/")
    driver.find_element(By.ID, "editProfileBtn").click()
    loc = driver.find_element(By.NAME, "location")
    loc.clear()
    loc.send_keys("X" * 60)
    driver.find_element(By.ID, "saveProfileBtn").click()
    assert len(loc.get_attribute("value")) <= int(loc.get_attribute("maxlength"))

# ✅ Test 5: Hobbies invalid characters
def test_invalid_hobbies_characters(driver):
    login(driver)
    driver.get("https://www.aisteadmai.shop/profile/")
    driver.find_element(By.ID, "editProfileBtn").click()
    hobbies = driver.find_element(By.NAME, "hobbies")
    hobbies.clear()
    hobbies.send_keys("123!!!")
    driver.find_element(By.ID, "saveProfileBtn").click()
    assert hobbies.get_attribute("pattern") is not None
