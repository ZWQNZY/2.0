from sogou_crawler import search_sogou
import json

def test_sogou():
    print("Testing Sogou Crawler...")
    keyword = "成都"
    results = search_sogou(keyword)
    
    print(f"Found {len(results)} results.")
    
    if results:
        print("\nFirst Result:")
        print(json.dumps(results[0], indent=4, ensure_ascii=False))
        
        # Verify structure
        required_keys = ["title", "summary", "url", "cover_url"]
        for key in required_keys:
            if key not in results[0]:
                print(f"Missing key: {key}")
            else:
                print(f"Key '{key}' is present.")
                
        if results[0]["title"] == "N/A":
            print("Warning: Title is N/A")
        if results[0]["url"] == "N/A":
            print("Warning: URL is N/A")
            
    else:
        print("No results found.")

if __name__ == "__main__":
    test_sogou()
