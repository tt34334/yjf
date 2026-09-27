import csv
import time
import random
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from webdriver_manager.microsoft import EdgeChromiumDriverManager

# 项目根目录（本文件位于：项目根目录/可运行的程序（用PyCharm运行打开）/天气挖掘代码/本文件）
PROJECT_ROOT = Path(__file__).resolve().parents[2]
# 天气数据保存目录
WEATHER_OUTPUT_DIR = PROJECT_ROOT / "数据集" / "气候数据" / "城市数据"
WEATHER_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 页面下拉操作
def drop_page(bro):
    """执行页面滚动的操作"""
    for x in range(1, 10, 3):  # 1, 3, 5, 7, 9
        j = x / 9  # 1/9, 3/9, 5/9, 7/9, 9/9
        js = 'document.documentElement.scrollTop = document.documentElement.scrollHeight * %f' % j
        bro.execute_script(js)
        time.sleep(0.4)  # 等待页面渲染

# 数据解析和保存操作
def parse_data(bro, csv_write):
    try:
        lis = bro.find_elements(By.XPATH, '//ul[@class="thrui"]/li')
        print(f"找到 {len(lis)} 条数据")
        for li in lis:
            time_ = li.find_element(By.XPATH, './/div[@class="th200"]').text
            weather_time = time_.split(' ')[0]  # 日期
            week_ = time_.split(' ')[1]  # 周几
            max_ = li.find_element(By.XPATH, './div[2]').text  # 最高气温
            min_ = li.find_element(By.XPATH, './div[3]').text  # 最低气温
            weather_ = li.find_element(By.XPATH, './div[4]').text  # 天气
            wind_ = li.find_element(By.XPATH, './div[5]').text
            wind_direction = wind_.split(' ')[0]  # 风向
            wind_level = wind_.split(' ')[1]  # 风级

            # 根据天气描述生成随机湿度，并保留一位小数
            if "雨" in weather_:
                humidity = round(random.uniform(80, 100), 1)  # 雨天湿度较高
            elif "雾" in weather_:
                humidity = round(random.uniform(70, 80), 1)  # 雾天湿度较高但低于雨天
            elif "晴" in weather_:
                humidity = round(random.uniform(0, 40), 1)  # 晴天湿度较低
            elif "多云" in weather_:
                humidity = round(random.uniform(40, 70), 1)  # 多云湿度中等
            else:
                humidity = round(random.uniform(0, 100), 1)  # 其他情况湿度随机

            data_dict = {
                '日期': weather_time,
                '周几': week_,
                '最高气温': max_,
                '最低气温': min_,
                '天气': weather_,
                '风向': wind_direction,
                '风级': wind_level,
                '湿度': f"{humidity}%"  # 新增湿度字段（随机百分数，保留一位小数）
            }
            csv_write.writerow(data_dict)
            print(data_dict)
    except NoSuchElementException as e:
        print(f"解析数据时出错: {e}")

# 获取单个城市的数据
def get_one(city, csv_write, bro, data):
    try:
        url = f"https://lishi.tianqi.com/{city}/{data}.html"
        bro.get(url)
        bro.refresh()
        bro.maximize_window()
        bro.implicitly_wait(10)
        time.sleep(1)

        # 页面下拉操作
        drop_page(bro)

        # 点击更多，渲染出下半月的数据
        more_label = WebDriverWait(bro, 10).until(
            EC.element_to_be_clickable((By.XPATH, '//div[@class="lishidesc2"]'))
        )
        more_label.click()
        time.sleep(1)  # 等待数据渲染

        # 数据解析和保存操作
        parse_data(bro, csv_write)
    except TimeoutException as e:
        print(f"页面加载超时: {e}")
    except Exception as e:
        print(f"发生错误: {e}")

if __name__ == '__main__':
    ##############   添加配置项   ####################
    options = webdriver.EdgeOptions()
    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    prefs = {'credentials_enable_service': False, 'profile.password_manager_enabled': False}
    options.add_experimental_option('prefs', prefs)
    options.add_argument('--disable-blink-features=AutomationControlled')

    # 初始化 WebDriver
    service = Service(EdgeChromiumDriverManager().install())
    bro = webdriver.Edge(service=service, options=options)

    ##############   定义抓取的城市和时间段   ####################
    cities = [
        'yuxi', 'beijing', 'shanghai', 'guangzhou', 'chengdu',
        'jinan', 'qingdao', 'wuhan', 'nanjing', 'dalian',
        'changchun', 'shenzhen', 'tianjin', 'chongqing', 'suzhou',
        'zhengzhou', 'xian', 'changsha', 'guiyang', 'shijiazhuang', 'haerbin'
    ]  # 城市列表

    time_periods = ['202403', '202404', '202405']  # 时间段列表

    # 城市名称映射
    city_names = {
        'yuxi': '玉溪','beijing': '北京','shanghai': '上海','guangzhou': '广州','chengdu': '成都','jinan': '济南','qingdao': '青岛','wuhan': '武汉','nanjing': '南京','dalian': '大连',
        'changchun': '长春','shenzhen': '深圳','tianjin': '天津','chongqing': '重庆','suzhou': '苏州','zhengzhou': '郑州','xian': '西安','changsha': '长沙','guiyang': '贵阳',
        'shijiazhuang': '石家庄','haerbin': '哈尔滨'
    }

    for city in cities:
        for period in time_periods:
            # 动态生成文件名，使用中文城市名称，保存到项目数据集目录下
            file_path = WEATHER_OUTPUT_DIR / f"{city_names[city]}_{period}天气数据.csv"
            with open(file_path, mode='w', encoding='utf-8-sig', newline='') as f:
                csv_write = csv.DictWriter(f, fieldnames=[
                    '日期', '周几', '最高气温', '最低气温', '天气', '风向', '风级', '湿度'
                ])
                csv_write.writeheader()

                # 执行抓取
                get_one(city, csv_write, bro, period)

    bro.quit()  # 关闭浏览器