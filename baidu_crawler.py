import requests
from bs4 import BeautifulSoup

from datetime import datetime
import time

def parse_baidu_results(html_content):
    """
    Parses Baidu search results using BeautifulSoup.
    Returns a list of dictionaries.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Baidu search results are usually wrapped in div with class 'c-container'
    results = soup.find_all('div', class_='c-container')
    
    parsed_data = []
    
    for result in results:
        data = {
            "title": "N/A",
            "summary": "N/A",
            "url": "N/A",
            "cover_url": "N/A"
        }
        
        # 1. Extract Title and URL
        h3 = result.find('h3')
        if h3:
            a_tag = h3.find('a')
            if a_tag:
                data["title"] = a_tag.get_text(strip=True)
                data["url"] = a_tag.get('href')
        
        # 2. Extract Cover URL
        img = result.find('img')
        if img and img.get('src'):
            data["cover_url"] = img.get('src')
        else:
            data["cover_url"] = "无封面"

        # 3. Extract Summary
        summary_div = result.find('div', class_='c-abstract')
        if not summary_div:
            summary_div = result.find('div', class_=lambda x: x and 'content-right' in x)
        
        if summary_div:
            data["summary"] = summary_div.get_text(strip=True)
        else:
            full_text = result.get_text(strip=True)
            if data["title"] != "N/A":
                data["summary"] = full_text.replace(data["title"], "").strip()[:100] + "..." 
            else:
                data["summary"] = full_text[:100] + "..."
        
        parsed_data.append(data)

    return parsed_data

def search_baidu(keyword, start_date=None, end_date=None):
    """
    Searches Baidu for the given keyword within a specific date range.
    Returns a list of results or None.
    :param keyword: Search keyword
    :param start_date: Start date string (YYYY-MM-DD)
    :param end_date: End date string (YYYY-MM-DD)
    """
    url = "https://www.baidu.com/s"
    
    params = {
        "wd": keyword
    }
    
    if start_date and end_date:
        try:
            # Parse dates
            s_dt = datetime.strptime(start_date, "%Y-%m-%d")
            e_dt = datetime.strptime(end_date, "%Y-%m-%d")
            
            # Convert to timestamps (Baidu uses seconds)
            # Start of start_date
            s_ts = int(s_dt.timestamp())
            # End of end_date (23:59:59)
            e_ts = int(e_dt.replace(hour=23, minute=59, second=59).timestamp())
            
            # Construct gpc parameter: stf={start},{end}|stftype=2
            params["gpc"] = f"stf={s_ts},{e_ts}|stftype=2"
            params["tfflag"] = "1"
        except ValueError:
            print(f"Invalid date format: {start_date} - {end_date}")
    
    # Headers - Simplified to avoid cookie issues and mimic a generic browser
    headers = {
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        response = requests.get(url, params=params, headers=headers)
        # print(f"Request URL: {response.url}")
        # print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            response.encoding = 'utf-8' 
            return parse_baidu_results(response.text)
        else:
            print("Failed to retrieve data.")
            return []
            
    except Exception as e:
        print(f"An error occurred: {e}")
        return []

if __name__ == "__main__":
    keyword = input("请输入搜索关键词 (默认为'成都'): ")
    if not keyword:
        keyword = "成都"
    results = search_baidu(keyword)
    for item in results:
        print(item)

