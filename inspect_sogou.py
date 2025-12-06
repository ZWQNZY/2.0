import requests
from bs4 import BeautifulSoup
import json

def inspect_sogou(keyword):
    url = "https://www.sogou.com/sogou"
    params = {
        "query": keyword
    }
    
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
        response.encoding = 'utf-8'
        
        # Save to file for reference
        with open('sogou_results.html', 'w', encoding='utf-8') as f:
            f.write(response.text)
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Inspect potential result containers
        # Sogou usually puts results in div with class 'vrwrap' or 'rb'
        print("Searching for results...")
        
        results = soup.select('.vrwrap') + soup.select('.rb')
        print(f"Found {len(results)} potential results.")
        
        for i, result in enumerate(results[:3]):
            print(f"\nResult {i+1}:")
            print(f"Classes: {result.get('class')}")
            
            # Try to find title
            title_tag = result.find('h3')
            if title_tag:
                print(f"Title: {title_tag.get_text(strip=True)}")
                link = title_tag.find('a')
                if link:
                    print(f"Link: {link.get('href')}")
            
            # Try to find summary
            # Summaries can be in different places depending on the result type
            # Common places: .str_info, .ft, or just text div
            summary_div = result.find('div', class_='text-layout') or result.find('p', class_='str_info') or result.find('div', class_='ft')
            if summary_div:
                print(f"Summary: {summary_div.get_text(strip=True)[:100]}...")
            
            # Try to find image
            img_div = result.find('div', class_='r-img') or result.find('div', class_='u-img')
            if img_div:
                img = img_div.find('img')
                if img:
                    print(f"Image: {img.get('src')}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_sogou("成都")
