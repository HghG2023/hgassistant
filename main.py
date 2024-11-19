# search_url -> get article links -> listing links for details -> data_dic
import os
import re
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import traceback  # 用于记录完整的错误信息
import time
from collections import defaultdict
from threading import Lock
from urllib.parse import urlencode

from urllib3 import Retry

# 设置请求头（例如模拟浏览器请求）
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
    'Accept': 'application/pdf',
    'Accept-Encoding': 'gzip, deflate',
}


# 定义下载函数
def download(tup, path):
    url, title = tup
    cleaned_title = clean_filename(title)[:25]  # 清理文件名并限制长度

    # 创建一个会话对象，可以使用相同的连接进行多个请求
    session = requests.Session()

    # 使用重试策略来处理网络不稳定等问题
    retry_strategy = Retry(
        total=3,  # 最多重试3次
        backoff_factor=1,  # 每次重试之间的延迟时间
        status_forcelist=[500, 502, 503, 504],  # 遇到这些状态码时重试
    )

    # 绑定重试策略到 session
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    path = os.path.join(path, 'PDF_Folder')
    os.makedirs(path)
    try:
        # 发送 GET 请求下载 PDF 文件
        response = session.get(url, headers=headers, timeout=10)

        # 检查响应是否成功
        if response.status_code == 200:
            # 保存为本地 PDF 文件
            p = os.path.join(path, f"{cleaned_title}.pdf")
            with open(p, "wb") as f:
                f.write(response.content)
            return True
        else:
            log_to_file("error_log.txt", f"下载失败，文章标题: {title}，链接：{url}, 状态码: {response.status_code}")
            return False

    except requests.exceptions.RequestException as e:
        log_to_file("error_log.txt", f"报错！文章标题: {title}，链接：{url}, erro:{e}")
        return False


# 定义清理文件名的函数
def clean_filename(filename):
    # 定义非法字符的正则表达式
    illegal_chars = r'[\/:*?"<>|]'
    # 替换为下划线
    return re.sub(illegal_chars, "_", filename)


# 记录日志到文件的函数
log_lock = Lock()


def log_to_file(file_path, message):
    with log_lock:
        with open(file_path, "a", encoding="utf-8") as file:
            file.write(f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}:\n{message}\n\n")


# 将字典写入 .txt 文件
def write_dict_to_txt(file_path, dictionary):
    try:
        with open(file_path, "a", encoding="utf-8") as file:
            json.dump(dictionary, file, indent=4, ensure_ascii=False)  # ensure_ascii=False 用于支持非 ASCII 字符
    except Exception as e:
        log_to_file("error_log.txt", f"Error writing dictionary to file: {e}")


def generate_url(queries, journals, article_type="research-article", year_from=1996, year_to=2024, page_count=100):
    """
    根据传入的参数生成所有可能的 search URL 组合。

    参数:
    - queries: 查询关键词列表（str 或 list[str]）
    - journals: 期刊名称列表（str 或 list[str]）
    - article_type: 文章类型，默认 "research-article"
    - year_from: 起始年份，默认 1996
    - year_to: 结束年份，默认 2024
    - page_count: 每页结果数，默认 100

    返回:
    - 所有可能组合的链接列表
    """
    base_url = "https://www.mdpi.com/search"

    # 确保 queries 和 journals 是列表
    if isinstance(queries, str):
        queries = [queries]
    if isinstance(journals, str):
        journals = [journals]

    urls = []

    # 生成所有 query 和 journal 的组合链接
    for query in queries:
        for journal in journals:
            params = {
                'q': query,
                'journal': journal,
                'article_type': article_type,
                'year_from': year_from,
                'year_to': year_to,
                'page_count': page_count,
                'sort': 'pubdate',
                'view': 'default'
            }
            url = f"{base_url}?{urlencode(params)}"
            urls.append(url)

    return urls


def wait_for_element(driver, by, value, timeout=10, condition="presence"):
    """
    通用等待函数，用于等待指定元素加载完成。

    参数:
    - driver: WebDriver 实例
    - by: 定位方式 (如 By.CSS_SELECTOR, By.ID, By.XPATH)
    - value: 定位的值 (如 '.title-link', 'element-id', '//div[@class="content"]')
    - timeout: 最大等待时间，默认为 10 秒
    - condition: 等待条件，可选值:
        - "presence": 等待元素存在于 DOM 中
        - "visibility": 等待元素在页面中可见
        - "clickable": 等待元素可点击

    返回:
    - 如果满足条件，返回元素或元素列表
    - 如果超时，返回 None
    """
    try:
        if condition == "presence":
            return WebDriverWait(driver, timeout).until(
                EC.presence_of_all_elements_located((by, value))
            )
        elif condition == "visibility":
            return WebDriverWait(driver, timeout).until(
                EC.visibility_of_all_elements_located((by, value))
            )
        elif condition == "clickable":
            return WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable((by, value))
            )
        else:
            raise ValueError("Unsupported condition type. Use 'presence', 'visibility', or 'clickable'.")
    except Exception as e:
        print(f"Error while waiting for element: {e}")
        return None


# 多线程执行的任务函数
def fetch_element_text(driver, by, value):
    """
    driver: WebDriver 实例。
    by: 定位元素的方法（例如，By.ID，By.CSS_SELECTOR）。
    value: 用于定位元素的选择器值。
    :return: 返回元素文本或属性的列表，如果未定义则返回消息。
    """
    elements = wait_for_element(driver, by, value, timeout=10, condition="presence")
    if not elements:
        return None

    # Define actions for each selector
    action_map = {
        '#abstract > div.html-content__container.content__container.content__container__combined-for-large__first.bright > article > div > h1': 'text',
        # title
        'profile-card-drop': 'text',  # authors
        'UD_ArticlePDF': 'href',  # pdf_download_link
        '#html-abstract > div': 'text',  # abstract
        'html-keywords': 'text',  # keywords
        '#abstract > div.html-content__container.content__container.content__container__combined-for-large__first.bright > article > div > div.additional-content > div.in-tab': 'text'
        # cite
    }
    action = action_map.get(value)
    # Perform the corresponding action
    if action == 'text':
        return [element.text for element in elements]
    elif action == 'href':
        return [element.get_attribute('href') for element in elements]
    else:
        return f"Selector not defined! by = {by}, value = {value}"


def get_all_title_links(urls):
    driver = create_driver()
    res = []
    for url in urls:
        try:
            driver.get(url)
            elements = wait_for_element(driver, By.CSS_SELECTOR, 'a.title-link', timeout=10, condition="presence")
            if not elements:
                log_to_file("error_log.txt", f"Failed to load elements from {url}")
                continue
            res.extend([element.get_attribute('href') for element in elements])
        except Exception as e:
            log_to_file("error_log.txt", f"Error in get_all_title_links for {url}: {traceback.format_exc()}, Error:{e}")
    driver.quit()
    return res


def get_details_of_article(url):
    try:
        tasks = {
            "title": (By.CSS_SELECTOR,
                      '#abstract > div.html-content__container.content__container.content__container__combined-for-large__first.bright > article > div > h1'),
            "author": (By.CLASS_NAME, 'profile-card-drop'),
            "pdf_download": (By.CLASS_NAME, 'UD_ArticlePDF'),
            "abstract": (By.CSS_SELECTOR, '#html-abstract > div'),
            "keywords": (By.ID, 'html-keywords'),
            "cites": (By.CSS_SELECTOR,
                      '#abstract > div.html-content__container.content__container.content__container__combined-for-large__first.bright > article > div > div.additional-content > div.in-tab'),
        }

        results = {}
        failed_tasks = {}
        driver = create_driver()
        driver.get(url)
        with ThreadPoolExecutor() as executor:
            future_to_task = {
                executor.submit(fetch_element_text, driver, by, value): name
                for name, (by, value) in tasks.items()
            }
            for future in as_completed(future_to_task):
                task_name = future_to_task[future]
                try:
                    result = future.result()
                    if result is None:
                        failed_tasks[task_name] = "No result returned"
                    else:
                        results[task_name] = result
                except Exception as e:
                    failed_tasks[task_name] = str(e)
                    log_to_file("error_log.txt", f"Error in task '{task_name}': {traceback.format_exc()}")

        if failed_tasks:
            bad_case = {
                "url": url,
                "failed_tasks": failed_tasks,
                "results": results
            }
            driver.quit()
            return bad_case, 0
        driver.quit()
        return results, 1

    except Exception as e:
        log_to_file("error_log.txt", f"Error fetching article details for {url}: {traceback.format_exc()}")
        return {"url": url, "error": str(e)}


def create_driver():
    chrome_options = Options()
    chromedriver_path = r"D:\Anaconda\chromedriver-win64\chromedriver.exe"
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    service = Service(chromedriver_path)
    return webdriver.Chrome(service=service, options=chrome_options)


def merge_dicts(main_dict, new_dict):
    """
    合并两个字典，将新字典的值合并到主字典中。
    如果键已经存在，则将值合并为列表。
    """
    for key, value in new_dict.items():
        main_dict[key].append(value)


def process_and_split_cites(df, path, cites_column='cites', output_file='all_info_of_articles.xlsx'):
    """
    处理 DataFrame，将 `cites` 列拆分为多列，分别对应不同的引用格式。

    参数:
    - df: 输入的 dict。
    - cites_column: 包含引用信息的列名，默认为 'cites'。
    - output_file: 保存结果的 Excel 文件路径，默认为 'split_cites.xlsx'。

    返回:
    - 处理后的 DataFrame。
    """

    # 定义分割函数
    def split_cites(cites):
        if not isinstance(cites, str):
            return pd.Series([None, None, None])
        parts = cites.split("\n")
        mdpi = "\n".join(parts[:2])  # MDPI and ACS Style
        ama = "\n".join(parts[2:4])  # AMA Style
        chicago = "\n".join(parts[4:])  # Chicago/Turabian Style
        return pd.Series([mdpi.strip(), ama.strip(), chicago.strip()])

    df = pd.DataFrame(df)
    # 检查 cites 列是否存在
    if cites_column not in df.columns:
        raise ValueError(f"Column '{cites_column}' not found in the DataFrame.")

    # 确保所有列中的列表转换为字符串
    df = df.applymap(lambda x: ', '.join(map(str, x)) if isinstance(x, list) else x)

    # 拆分 cites 列为多列
    new_columns = ['CITE_MDPI and ACS Style', 'CITE_AMA Style', 'CITE_Chicago/Turabian Style']
    df[new_columns] = df[cites_column].apply(split_cites)

    # 删除原始 cites 列（可选）
    df = df.drop(columns=[cites_column])

    # 保存到 Excel 文件
    output_ = os.path.join(path, output_file)
    df.to_excel(output_, index=False)
    print("Excel have been saved!")


def unique_folder():
    # 生成基于时间的唯一文件夹名称
    folder_name = time.strftime('%Y_%m_%d_%H_%M_%S', time.localtime())
    folder_path = os.path.join(os.getcwd(), folder_name)  # 使用当前工作目录作为根路径

    # 如果文件夹不存在，则创建它
    try:
        os.makedirs(folder_path)
    except FileExistsError:
        folder_path = os.path.join(os.getcwd(), folder_name + '_new')
        os.makedirs(folder_path)
    return folder_path


def main():
    errors = []
    # 根据需求如：关键词，期刊，生成链接
    path = unique_folder()

    def get_user_input(prompt):
        """
        获取用户输入，确保输入的内容不为空。
        """
        while True:
            user_input = input(prompt)  # 获取用户输入
            if user_input.strip():  # 判断是否为空（去掉前后空格）
                return user_input.strip()
            else:
                print("Input cannot be empty! Please enter a valid value.")

    # 初始列表为空时，通过用户输入获得有效列表
    qs = [
    "Centrifugal Fan Dynamic Characteristics Analysis",
    "Dynamic characteristics analysis",
    "Centrifugal fan fluid dynamics",
    "Finite element model establishment",
    "Dynamic response analysis",
    "Aerodynamic performance optimization",
    "Impeller-diffuser-volute casing interaction",
    "Centrifugal Fan Pneumatic Hydrostatic Balance Actuator Design",
    "Pneumatic actuator design",
    "Hydrostatic balance mechanism",
    "Centrifugal fan balance actuator",
    "Actuator structural design",
    "Pressure liquid balance actuator",
    "Finite Element Method-based Actuator Structure Optimization",
    "Finite element method (FEM)",
    "Actuator structure optimization",
    "Topology optimization",
    "Structural optimization algorithm",
    "Elasto-plastic topology optimization"
]
    journal = ['machines']
    counts = 0

    # 检查 qs 是否为空，并让用户重新输入
    if not qs:
        print("The 'qs' list is empty.")
        qs = get_user_input("Please enter search queries (comma separated): ").split(',')
    if not journal:
        print("The 'journal' list is empty.")
        qs = get_user_input("Please enter search queries (comma separated): ").split(',')

    search_url = generate_url(qs, journal, article_type="research-article", year_from=1996, year_to=2024,
                              page_count=100)

    # 根据链接，获取所有的文章链接
    urls_of_all_articles = get_all_title_links(search_url)

    merged_results = defaultdict(list)  # 用于存储成功结果的字典

    with ThreadPoolExecutor() as executor:
        # 提交任务
        futures = [executor.submit(get_details_of_article, url) for url in urls_of_all_articles]

        # 处理任务结果
        for future in as_completed(futures):
            print(counts+1)
            try:
                result = future.result()  # 获取任务结果
                if result[1] == 0:
                    errors.append(result[0])  # 如果 flag 是 0，添加到错误列表
                elif result[1] == 1:
                    merge_dicts(merged_results, result[0])  # 如果 flag 是 1，合并到结果字典
            except Exception as e:
                log_to_file("error_log.txt", f"Error writing dictionary to file: {e}")
                print("can't generate url ! makesure that you complicated all requests !")

    # 记录失败结果到文件
    f_c = os.path.join(path, 'failed_catching.txt')
    write_dict_to_txt(f_c, errors)

    process_and_split_cites(merged_results, path)

    print("Process finished !")
if __name__ == "__main__":
    main()