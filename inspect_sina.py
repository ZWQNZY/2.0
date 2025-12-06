import requests
from bs4 import BeautifulSoup

def inspect_sina(keyword):
    url = "https://search.sina.com.cn/"
    params = {
        "c": "news",
        "q": keyword,
        "from": "home",
        "ie": "utf-8"
    }
    
    headers = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(url, params=params, headers=headers)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        
        results = soup.select('.box-result')
        print(f"Found {len(results)} results.")
        
        for i, res in enumerate(results[:3]):
            print(f"--- Result {i+1} ---")
            h2 = res.find('h2')
            if h2 and h2.find('a'):
                print("Title:", h2.find('a').get_text(strip=True))
                print("URL:", h2.find('a')['href'])
            
            img = res.find('div', class_='r-img')
            if img and img.find('img'):
                print("Image:", img.find('img')['src'])
            
            content = res.find('p', class_='content')
            if content:
                print("Summary:", content.get_text(strip=True))
            else:
                # Fallback for summary
                print("Summary (fallback):", res.get_text(strip=True)[:100])
                
    except Exception as e:
        print(e)

if __name__ == "__main__":
    inspect_sina("山东")