from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.action_chains import ActionChains
import time
from PIL import Image
import pytesseract
import urllib.request 


# options
chrome_opt = Options()
chrome_opt.add_argument("--headless")
chrome_opt.add_argument("--incognito")

sleep_time = 0.7

def get_single():
  # 菜單連結
  url = "https://www.kfcclub.com.tw/menu"

  # 宣告driver
  driver = webdriver.Chrome(chrome_opt)
  driver.get(url)

  # 關掉彈窗(如果有)
  time.sleep(3)
  try:
    btn = driver.find_element(By.XPATH, "//button[@aria-label=\"Close Message\"]")
    btn.click()
    time.sleep(sleep_time)
  except NoSuchElementException:
    print("No advertisement found")

  ret = {"漢堡":{},"捲餅、燒餅":{},"蛋撻、點心":{},"大隻G":{},"飲料":{},"炸物":{},"其他":{}}

  S = "//div[@class=\"MuiPaper-root MuiPaper-elevation MuiPaper-rounded MuiPaper-elevation1 MuiCard-root styles_root__Ad4_u css-s18byi\"]"
  meals = driver.find_elements(By.XPATH, S)
  skip = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '餐', '桶', '盒']
  for meal in meals:
    S = ".//div[@class=\"styles_name__0Dkbt\"]"
    name = meal.find_element(By.XPATH, S).text
    S = ".//div[@class=\"styles_price__XDDoU\"]"
    price = meal.find_element(By.XPATH, S).text
    price = ''.join([i for i in price if i.isdigit()])
    bln = False
    for i in skip:
      if i in name:
        bln = True
        break
    if bln and not('%' in name):
      continue
    if('堡' in name):
      ret["漢堡"][name] = int(price)
    elif(('捲'in name) or ('燒'in name)):
      ret["捲餅、燒餅"][name] = int(price)
    elif('雞' in name):
      ret["大隻G"][name] = int(price)
    elif(("蛋撻" in name) or("冰淇淋" in name)or("比司吉" in name)or(("QQ球" in name))):
      ret["蛋撻、點心"][name] = int(price)
    elif(("咖啡" in name)or("拿鐵" in name)or("卡布奇諾" in name)or("茶" in name)or("柳橙汁" in name)or("可樂" in name)or("七喜" in name)):
      ret["飲料"][name] = int(price)
    elif(("起司球" in name)or("薯餅" in name)or("脆薯" in name)or("圈圈" in name)or("蝦塊" in name)or("蝦塊" in name)or("拼盤" in name)):
      ret["炸物"][name] = int(price)
    else:
      ret["其他"][name] = int(price)
  return ret
  
print(get_single())