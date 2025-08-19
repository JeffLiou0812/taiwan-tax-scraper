import requests
from bs4 import BeautifulSoup
import pandas as pd
import json
from datetime import datetime
import os
import time
import random

class SmartTaxScraper:
    def __init__(self):
        print("🤖 智慧稅務爬蟲 v1.0 啟動")
        print("="*60)
        
        self.data_dir = "data"
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8',
            'Referer': 'https://law.dot.gov.tw/'
        })
        
        self.base_url = "https://law.dot.gov.tw"
        self.history_file = os.path.join(self.data_dir, "smart_history.json")
        self.new_file = os.path.join(self.data_dir, "today_new.json")
        self.report_file = os.path.join(self.data_dir, "daily_report.json")
    
    def fetch_rulings(self):
        """擷取最新函釋"""
        print("📡 連線到財政部網站...")
        
        try:
            # 先訪問主頁建立session
            self.session.get(f"{self.base_url}/", timeout=10)
            time.sleep(random.uniform(1, 2))
            
            # 查詢函釋頁面
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
                print("✅ 成功連線")
                return self.parse_content(soup)
            else:
                print(f"❌ 連線失敗: {response.status_code}")
                return []
                
        except Exception as e:
            print(f"❌ 錯誤: {str(e)}")
            return []
    
    def parse_content(self, soup):
        """解析網頁內容"""
        rulings = []
        
        # 方法1: 從表格擷取
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')[1:]  # 跳過標題列
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 2:
                    ruling = self.extract_ruling_from_row(row, cells)
                    if ruling:
                        rulings.append(ruling)
        
        # 方法2: 從連結擷取（如果表格沒資料）
        if not rulings:
            links = soup.find_all('a', href=True)
            for link in links:
                if self.is_ruling_link(link):
                    ruling = self.extract_ruling_from_link(link)
                    if ruling:
                        rulings.append(ruling)
        
        print(f"📊 找到 {len(rulings)} 筆函釋")
        return rulings
    
    def extract_ruling_from_row(self, row, cells):
        """從表格列提取函釋資訊"""
        ruling = {}
        
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
            ruling['url'] = self.make_full_url(link['href'])
            if not ruling.get('title'):
                ruling['title'] = link.get_text(strip=True)
        
        if ruling.get('title') or ruling.get('number'):
            ruling['found_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ruling['id'] = self.generate_id(ruling)
            return ruling
        
        return None
    
    def extract_ruling_from_link(self, link):
        """從連結提取函釋資訊"""
        text = link.get_text(strip=True)
        href = link.get('href', '')
        
        ruling = {
            'title': text,
            'url': self.make_full_url(href),
            'found_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        ruling['id'] = self.generate_id(ruling)
        return ruling
    
    def is_ruling_link(self, link):
        """判斷是否為函釋連結"""
        text = link.get_text(strip=True)
        href = link.get('href', '')
        
        keywords = ['函', '令', '釋', '稅', 'law']
        return any(kw in text or kw in href.lower() for kw in keywords) and len(text) > 5
    
    def make_full_url(self, url):
        """建立完整URL"""
        if url and not url.startswith('http'):
            return self.base_url + url
        return url
    
    def generate_id(self, ruling):
        """產生唯一ID"""
        # 使用標題或字號作為ID
        text = ruling.get('title', '') or ruling.get('number', '')
        return str(hash(text))[-8:]
    
    def check_new_items(self, current_rulings):
        """檢查新函釋"""
        print("\n🔍 比對歷史記錄...")
        
        # 載入歷史記錄
        history = {}
        if os.path.exists(self.history_file):
            with open(self.history_file, 'r', encoding='utf-8') as f:
                history_list = json.load(f)
                history = {item['id']: item for item in history_list if 'id' in item}
                print(f"📚 歷史記錄: {len(history)} 筆")
        else:
            print("📚 首次執行，建立歷史記錄")
        
        # 找出新函釋
        new_rulings = []
        for ruling in current_rulings:
            if ruling['id'] not in history:
                new_rulings.append(ruling)
                print(f"  🆕 新發現: {ruling.get('title', 'N/A')[:40]}...")
        
        # 更新歷史記錄
        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(current_rulings, f, ensure_ascii=False, indent=2)
        
        return new_rulings
    
    def save_new_rulings(self, new_rulings):
        """儲存新函釋"""
        # 儲存今日新函釋
        with open(self.new_file, 'w', encoding='utf-8') as f:
            json.dump(new_rulings, f, ensure_ascii=False, indent=2)
        
        if new_rulings:
            # 儲存帶時間戳的檔案
            timestamp = datetime.now().strftime('%Y%m%d')
            filename = os.path.join(self.data_dir, f'new_{timestamp}.json')
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(new_rulings, f, ensure_ascii=False, indent=2)
            
            # 儲存CSV版本
            csv_file = os.path.join(self.data_dir, f'new_{timestamp}.csv')
            df = pd.DataFrame(new_rulings)
            df.to_csv(csv_file, index=False, encoding='utf-8-sig')
            
            print(f"💾 新函釋已儲存: {filename}")
    
    def generate_report(self, all_rulings, new_rulings):
        """產生執行報告"""
        report = {
            'execution_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_checked': len(all_rulings),
            'new_count': len(new_rulings),
            'status': 'success',
            'has_new': len(new_rulings) > 0,
            'new_titles': [r.get('title', 'N/A')[:50] for r in new_rulings[:5]]
        }
        
        with open(self.report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print("\n" + "="*60)
        print("📊 執行報告")
        print("="*60)
        print(f"執行時間: {report['execution_time']}")
        print(f"檢查數量: {report['total_checked']} 筆")
        print(f"新增函釋: {report['new_count']} 筆")
        
        if new_rulings:
            print("\n📢 新函釋摘要:")
            for i, ruling in enumerate(new_rulings[:5], 1):
                print(f"{i}. {ruling.get('title', 'N/A')[:50]}")
                if ruling.get('date'):
                    print(f"   日期: {ruling['date']}")
        else:
            print("\n✨ 今天沒有新函釋")
        
        return report

def main():
    scraper = SmartTaxScraper()
    
    # 擷取函釋
    all_rulings = scraper.fetch_rulings()
    
    if all_rulings:
        # 檢查新函釋
        new_rulings = scraper.check_new_items(all_rulings)
        
        # 儲存新函釋
        scraper.save_new_rulings(new_rulings)
        
        # 產生報告
        report = scraper.generate_report(all_rulings, new_rulings)
        
        # 設定退出碼（供GitHub Actions使用）
        if report['has_new']:
            print("\n🎯 任務完成 - 有新函釋")
        else:
            print("\n✅ 任務完成 - 無新函釋")
    else:
        print("\n⚠️ 未能擷取資料，請檢查網路或網站狀態")
        # 建立錯誤報告
        report = {
            'execution_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'error',
            'error': 'Failed to fetch data'
        }
        with open(scraper.report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
    
    print("="*60)
    print("🏁 程式結束")

if __name__ == "__main__":
    main()
