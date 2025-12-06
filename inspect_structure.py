from bs4 import BeautifulSoup

def inspect():
    with open("baidu_result.html", "r", encoding="utf-8") as f:
        html = f.read()
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # Find the main container for results
    content_left = soup.find('div', id='content_left')
    if not content_left:
        print("Could not find div#content_left")
        return

    print("Found content_left. Iterating over children...")
    
    # Iterate over result containers
    results = content_left.find_all('div', class_='c-container')
    print(f"Found {len(results)} results with class 'c-container'")
    
    for i, result in enumerate(results[3:6]): # Inspect 4-6
        print(f"\n--- Result {i+4} ---")
        # Dump HTML
        print(result.prettify()[:1000])

if __name__ == "__main__":
    inspect()
