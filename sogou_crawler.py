import requests
from bs4 import BeautifulSoup
import time
import random

def parse_sogou_results(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    results = soup.select('.vrwrap') + soup.select('.rb')
    parsed_data = []
    
    for result in results:
        data = {"title": "N/A", "summary": "N/A", "url": "N/A", "cover_url": "N/A"}
        
        # Title and URL
        h3 = result.find('h3')
        if h3 and h3.find('a'):
            data["title"] = h3.find('a').get_text(strip=True)
            data["url"] = h3.find('a')['href']
            if data["url"].startswith('/'):
                 data["url"] = "https://www.sogou.com" + data["url"]
        
        # Image
        img_div = result.find('div', class_='r-img') or result.find('div', class_='u-img') or result.find('a', class_='u-img')
        if img_div:
            img = img_div.find('img')
            if img and img.get('src'):
                data["cover_url"] = img['src']
                if data["cover_url"].startswith('//'):
                    data["cover_url"] = "https:" + data["cover_url"]
            else:
                 data["cover_url"] = "无封面"
        else:
            data["cover_url"] = "无封面"
            
        # Summary
        summary_div = result.find('div', class_='text-layout') or result.find('p', class_='str_info') or result.find('div', class_='ft')
        if summary_div:
            data["summary"] = summary_div.get_text(strip=True)
        else:
            # Fallback to text if title is known
             full_text = result.get_text(strip=True)
             if data["title"] != "N/A":
                 data["summary"] = full_text.replace(data["title"], "").strip()[:150] + "..."
             else:
                 data["summary"] = full_text[:150] + "..."
        
        if data["title"] != "N/A":
            parsed_data.append(data)
            
    return parsed_data

def search_sogou(keyword, start_date=None, end_date=None):
    url = "https://www.sogou.com/sogou"
    params = {"query": keyword}
    
    headers = {
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36 Edg/142.0.0.0",
        "host": "www.sogou.com",
        "sec-ch-ua": '"Chromium";v="142", "Microsoft Edge";v="142", "Not_A Brand";v="99"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "cross-site",
        "sec-fetch-user": "?1",
        "upgrade-insecure-requests": "1"
    }
    
    try:
        response = requests.get(url, params=params, headers=headers)
        if response.status_code == 200:
            response.encoding = 'utf-8'
            return parse_sogou_results(response.text)
        else:
             print(f"Failed to retrieve data from Sogou. Status: {response.status_code}")
             return []
    except Exception as e:
        print(f"An error occurred during Sogou search: {e}")
        return []
