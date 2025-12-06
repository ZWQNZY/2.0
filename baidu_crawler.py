import requests
from bs4 import BeautifulSoup

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

def search_baidu(keyword):
    """
    Searches Baidu for the given keyword using specific headers.
    Returns a list of results or None.
    """
    url = "https://www.baidu.com/s"
    
    params = {
        "wd": keyword
    }
    
    # Headers as provided in the user request
    headers = {
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "accept-encoding": "gzip, deflate",
        "accept-language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "cache-control": "max-age=0",
        "connection": "keep-alive",
        "cookie": "BAIDUID=2C3F0E9C9A8A893D9D13B5BE083F0DC2:FG=1; BAIDUID_BFESS=2C3F0E9C9A8A893D9D13B5BE083F0DC2:FG=1; ploganondeg=1; newlogin=1; BDUSS=t6U2JWMzh2OGtkMXF3QUFrVDQ0VVlyZy1tYTRFQ2dnYTRVYTFSZ0hEVldDRlJwSVFBQUFBJCQAAAAAAQAAAAEAAADDVwKa6arcxrV0NTY3AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAFZ7LGlWeyxpNE; BDUSS_BFESS=t6U2JWMzh2OGtkMXF3QUFrVDQ0VVlyZy1tYTRFQ2dnYTRVYTFSZ0hEVldDRlJwSVFBQUFBJCQAAAAAAQAAAAEAAADDVwKa6arcxrV0NTY3AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAFZ7LGlWeyxpNE; BIDUPSID=2C3F0E9C9A8A893D9D13B5BE083F0DC2; PSTM=1764867418; PAD_BROWSER=1; BD_UPN=12314753; BA_HECTOR=a12kagah00ah000h2g05ak0k81ak231kj3far24; ZFY=Lojl:BtGEGvRYpHzni2V8UMj0kqR82S:AjVakfuZPUsTA:C; BDRCVFR[feWj1Vr5u3D]=I67x6TjHwwYf0; BD_CK_SAM=1; PSINO=1; delPer=0; BDORZ=B490B5EBF6F3CD402E515D22BCDA1598; H_WISE_SIDS=63146_64007_65312_65590_66109_66207_66225_66257_66292_66393_66529_66554_66586_66580_66591_65792_66601_66605_66681_66691_66699_66686_66711_66621_66784_66791_66800_66806_66599_66812; H_PS_PSSID=63146_64007_65312_65590_66109_66207_66225_66257_66292_66393_66529_66554_66570_66586_66580_66591_65792_66601_66605_66681_66691_66699_66686_66711_66621_66784_66791_66800_66806_66599_66812; SMARTINPUT=%5Bobject%20Object%5D; H_PS_645EC=f782%2B5BltogCmer2gI%2FsFhN%2Fg%2BUqdrNxvfwNe9sVprero91WYRVw1MDzifs; baikeVisitId=6036d6ee-d874-493a-ac40-45725857886f",
        "host": "www.baidu.com",
        "sec-ch-ua": '"Chromium";v="142", "Google Chrome";v="142", "Not_A Brand";v="99"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "none",
        "sec-fetch-user": "?1",
        "upgrade-insecure-requests": "1",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36"
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

