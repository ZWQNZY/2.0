import requests
from bs4 import BeautifulSoup
import time

def parse_sina_results(html_content):
    """
    Parses Sina search results using BeautifulSoup.
    Returns a list of dictionaries.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Sina search results are wrapped in div with class 'box-result'
    results = soup.select('.box-result')
    
    parsed_data = []
    
    for result in results:
        data = {
            "title": "N/A",
            "summary": "N/A",
            "url": "N/A",
            "cover_url": "N/A"
        }
        
        # 1. Extract Title and URL
        h2 = result.find('h2')
        if h2 and h2.find('a'):
            data["title"] = h2.find('a').get_text(strip=True)
            data["url"] = h2.find('a')['href']
        
        # 2. Extract Cover URL
        img_div = result.find('div', class_='r-img')
        if img_div and img_div.find('img'):
            data["cover_url"] = img_div.find('img')['src']
        else:
            data["cover_url"] = "无封面"

        # 3. Extract Summary
        content_p = result.find('p', class_='content')
        if content_p:
            data["summary"] = content_p.get_text(strip=True)
        else:
            # Fallback: get text excluding title and other metadata
            # This is a bit rough, but better than nothing
            full_text = result.get_text(strip=True)
            if data["title"] != "N/A":
                # Remove title from full text to get summary approximation
                data["summary"] = full_text.replace(data["title"], "").strip()[:150] + "..."
            else:
                data["summary"] = full_text[:150] + "..."
        
        parsed_data.append(data)

    return parsed_data

def search_sina(keyword, start_date=None, end_date=None):
    """
    Searches Sina for the given keyword.
    Date range is currently not supported by this simple implementation 
    as Sina's date parameters require more investigation, 
    but the interface is kept consistent with baidu_crawler.
    """
    url = "https://search.sina.com.cn/"
    
    params = {
        "c": "news",
        "q": keyword,
        "from": "home",
        "ie": "utf-8"
    }
    
    # Headers provided by user (simplified for python requests)
    headers = {
        "authority": "search.sina.com.cn",
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36 Edg/142.0.0.0"
    }

    try:
        response = requests.get(url, params=params, headers=headers)
        
        if response.status_code == 200:
            # Sina often uses utf-8, but requests might guess wrong
            response.encoding = 'utf-8' 
            return parse_sina_results(response.text)
        else:
            print(f"Failed to retrieve data from Sina. Status: {response.status_code}")
            return []
            
    except Exception as e:
        print(f"An error occurred during Sina search: {e}")
        return []

if __name__ == "__main__":
    keyword = "山东"
    results = search_sina(keyword)
    for item in results:
        print(item)