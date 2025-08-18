import requests
from bs4 import BeautifulSoup
import json
import pandas as pd
from datetime import datetime
import os
import time
import random

class MOFTaxScraper:
    def __init__(self):
        print("初始化財政部稅務爬蟲...")
        
        # 建立資料夾
        self.data_dir = "data"
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
        
        # 設定Session
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Referer': 'https://law.dot.gov.tw/'
        })
        
        self.base_url = "https://law.dot.gov.tw"
        
    def fetch_latest_rulings(self):
        """擷取最新函釋列表"""
        print("\n開始擷取最新函釋...")
        
        # 先訪問主頁
        main_response = self.session.get(f"{self.base_url}/", timeout=10)
        time.sleep(random.uniform(1, 2))
        
        # 訪問法規查詢頁面
        url = f"{self.base_url}/law-ch/home.jsp"
        params = {
            'id': '18',
            'mcustomize': 'newlaw_list.jsp',
            'sort': '1',
            'up_down': 'D'
        }
        
        response = self.session.get(url, params=params, timeout=30)
        
        if response.status_code == 200:
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.text, 'html.parser')
            return self.parse_rulings(soup)
        else:
            print(f"擷取失敗：{response.status_code}")
            return []
    
    def parse_rulings(self, soup):
        """解析函釋資料"""
        rulings = []
        
        # 方法1: 尋找表格資料
        tables = soup.find_all('table')
        print(f"找到 {len(tables)} 個表格")
        
        for table in tables:
            rows = table.find_all('tr')
            
            for row in rows[1:]:  # 跳過標題
                cells = row.find_all('td')
                
                if len(cells) >= 2:
                    ruling = {}
                    
                    # 提取文字內容
                    for i, cell in enumerate(cells):
                        text = cell.get_text(strip=True)
                        if text:
                            if i == 0:
                                ruling['number'] = text
                            elif i == 1:
                                ruling['date'] = text
                            elif i == 2:
                                ruling['title'] = text
                    
                    # 尋找連結
                    link = row.find('a', href=True)
                    if link:
                        ruling['url'] = self.base_url + link['href'] if not link['href'].startswith('http') else link['href']
                        if not ruling.get('title'):
                            ruling['title'] = link.get_text(strip=True)
                    
                    if ruling:
                        ruling['scraped_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        rulings.append(ruling)
        
        # 方法2: 如果沒有從表格找到，尋找連結
        if not rulings:
            print("從連結尋找函釋...")
            links = soup.find_all('a', href=True)
            
            for link in links:
                href = link.get('href', '')
                text = link.get_text(strip=True)
                
                # 過濾可能的法規連結
                if ('law' in href.lower() or '函' in text or '令' in text or '釋' in text) and len(text) > 5:
                    ruling = {
                        'title': text,
                        'url': self.base_url + href if not href.startswith('http') else href,
                        'scraped_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
                    rulings.append(ruling)
        
        print(f"共找到 {len(rulings)} 筆函釋資料")
        return rulings
    
    def save_results(self, rulings):
        """儲存結果"""
        if not rulings:
            print("無資料可儲存")
            return None
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # 儲存JSON
        json_file = os.path.join(self.data_dir, f'rulings_{timestamp}.json')
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(rulings, f, ensure_ascii=False, indent=2)
        
        # 儲存CSV
        csv_file = os.path.join(self.data_dir, f'rulings_{timestamp}.csv')
        df = pd.DataFrame(rulings)
        df.to_csv(csv_file, index=False, encoding='utf-8-sig')
        
        # 更新最新資料
        latest_file = os.path.join(self.data_dir, 'latest_rulings.json')
        with open(latest_file, 'w', encoding='utf-8') as f:
            json.dump(rulings, f, ensure_ascii=False, indent=2)
        
        print(f"\n✅ 已儲存 {len(rulings)} 筆資料")
        print(f"  JSON: {json_file}")
        print(f"  CSV: {csv_file}")
        
        return json_file
    
    def display_sample(self, rulings, count=5):
        """顯示範例資料"""
        print(f"\n📋 前 {min(count, len(rulings))} 筆資料：")
        print("-" * 50)
        
        for i, ruling in enumerate(rulings[:count], 1):
            print(f"\n{i}. {ruling.get('title', 'N/A')[:50]}")
            if ruling.get('date'):
                print(f"   日期: {ruling['date']}")
            if ruling.get('number'):
                print(f"   字號: {ruling['number']}")
            if ruling.get('url'):
                print(f"   連結: {ruling['url'][:50]}...")

def main():
    print("="*60)
    print("   財政部稅務函釋自動化爬蟲 v3.0")
    print("="*60)
    print(f"執行時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 初始化爬蟲
    scraper = MOFTaxScraper()
    
    # 擷取資料
    rulings = scraper.fetch_latest_rulings()
    
    if rulings:
        # 顯示範例
        scraper.display_sample(rulings)
        
        # 儲存結果
        scraper.save_results(rulings)
    else:
        print("\n未找到函釋資料")
    
    print("\n" + "="*60)
    print("執行完成！")
    print("="*60)

if __name__ == "__main__":
    main()
