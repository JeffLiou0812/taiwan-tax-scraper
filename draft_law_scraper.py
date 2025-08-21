#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
財政部法規草案爬蟲 - URL修正版
確保每個草案都有可用的連結

目標網站: https://law-out.mof.gov.tw/DraftForum.aspx
版本: 4.0 URL-Fixed
更新日期: 2025-08-21
"""

import requests
import json
import pandas as pd
from datetime import datetime, timezone, timedelta
import re
from pathlib import Path
import hashlib
import time
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, quote
import logging
from typing import Dict, List, Tuple, Optional

class DraftLawScraperFixed:
    """法規草案爬蟲 - URL修正版"""
    
    def __init__(self, data_dir="data", debug=True):
        """初始化爬蟲"""
        self.base_url = "https://law-out.mof.gov.tw"
        self.draft_page_url = "https://law-out.mof.gov.tw/DraftForum.aspx"
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        # 設定日誌
        self.setup_logging(debug)
        
        # 請求標頭
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        self.tz_taipei = timezone(timedelta(hours=8))
        self.session = requests.Session()
        self.session.headers.update(self.headers)
    
    def setup_logging(self, debug: bool):
        """設定日誌系統"""
        log_level = logging.DEBUG if debug else logging.INFO
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        self.logger = logging.getLogger(__name__)
    
    def fetch_draft_laws(self) -> List[Dict]:
        """爬取法規草案列表"""
        all_drafts = []
        
        try:
            self.logger.info("開始爬取法規草案...")
            
            # 發送請求
            response = self.session.get(self.draft_page_url, timeout=30)
            
            if response.status_code != 200:
                self.logger.error(f"HTTP {response.status_code}")
                return []
            
            # 解析頁面
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 尋找表格
            tables = soup.find_all('table')
            
            for table in tables:
                rows = table.find_all('tr')
                
                for row in rows[1:]:  # 跳過標題列
                    cells = row.find_all('td')
                    
                    if len(cells) >= 2:
                        draft = self.extract_draft_from_cells(cells, soup)
                        if draft:
                            all_drafts.append(draft)
            
            # 如果沒有找到表格資料，嘗試其他方式
            if not all_drafts:
                self.logger.warning("未從表格找到資料，嘗試其他解析方式...")
                # 尋找可能的草案項目
                items = soup.find_all(['div', 'li'], class_=re.compile(r'item|draft|law'))
                for item in items:
                    draft = self.extract_draft_from_element(item)
                    if draft:
                        all_drafts.append(draft)
            
            self.logger.info(f"成功爬取 {len(all_drafts)} 筆法規草案")
            
        except Exception as e:
            self.logger.error(f"爬取失敗: {e}")
            import traceback
            traceback.print_exc()
        
        return all_drafts
    
    def extract_draft_from_cells(self, cells, full_soup) -> Optional[Dict]:
        """從表格儲存格提取草案資訊"""
        try:
            draft = {
                'source': 'MOF_Taiwan_Draft',
                'scrape_time': datetime.now(self.tz_taipei).isoformat()
            }
            
            # 提取日期
            if len(cells) > 0:
                date_text = cells[0].get_text(strip=True)
                draft['announcement_date_roc'] = date_text
                draft['announcement_date'] = self.convert_roc_date(date_text)
            
            # 提取標題和連結
            if len(cells) > 1:
                title_cell = cells[1]
                draft['title'] = title_cell.get_text(strip=True)
                
                # 尋找連結
                link = title_cell.find('a')
                if link:
                    href = link.get('href', '')
                    onclick = link.get('onclick', '')
                    
                    # 嘗試各種方式提取URL
                    extracted_url = self.extract_url_from_link(href, onclick, full_soup)
                    draft['url'] = extracted_url
                else:
                    # 沒有直接連結，稍後會生成搜尋連結
                    draft['url'] = None
            
            # 提取截止日期
            if len(cells) > 2:
                end_date_text = cells[2].get_text(strip=True)
                draft['end_date_roc'] = end_date_text
                draft['end_date'] = self.convert_roc_date(end_date_text)
                draft['status'] = self.check_status(draft['end_date'])
            else:
                draft['status'] = '進行中'
            
            # 如果還是沒有URL，生成智能連結
            if not draft.get('url'):
                draft['url'] = self.generate_smart_url(draft)
                draft['url_type'] = 'generated'
            else:
                draft['url_type'] = 'original'
            
            # 生成唯一ID
            if draft.get('title'):
                draft['id'] = self.generate_unique_id(draft)
                return draft
                
        except Exception as e:
            self.logger.debug(f"提取錯誤: {e}")
        
        return None
    
    def extract_draft_from_element(self, element) -> Optional[Dict]:
        """從HTML元素提取草案資訊"""
        try:
            draft = {
                'source': 'MOF_Taiwan_Draft',
                'scrape_time': datetime.now(self.tz_taipei).isoformat()
            }
            
            text = element.get_text(strip=True)
            
            # 提取標題
            draft['title'] = text[:200] if len(text) > 200 else text
            
            # 提取日期
            date_match = re.search(r'\d{3}\.\d{1,2}\.\d{1,2}', text)
            if date_match:
                draft['announcement_date_roc'] = date_match.group()
                draft['announcement_date'] = self.convert_roc_date(date_match.group())
            
            # 尋找連結
            link = element.find('a')
            if link:
                href = link.get('href', '')
                draft['url'] = self.process_url(href)
            else:
                draft['url'] = self.generate_smart_url(draft)
            
            draft['status'] = '進行中'
            
            if draft.get('title'):
                draft['id'] = self.generate_unique_id(draft)
                return draft
                
        except Exception as e:
            self.logger.debug(f"元素提取錯誤: {e}")
        
        return None
    
    def extract_url_from_link(self, href, onclick, soup) -> Optional[str]:
        """從各種屬性中提取URL"""
        # 方法1: 直接使用href
        if href and href != '#' and not href.startswith('javascript:'):
            return self.process_url(href)
        
        # 方法2: 從onclick中提取
        if onclick:
            # 尋找window.open或類似的URL
            url_patterns = [
                r"window\.open\(['\"]([^'\"]+)['\"]",
                r"location\.href=['\"]([^'\"]+)['\"]",
                r"['\"]([^'\"]*join\.gov\.tw[^'\"]+)['\"]",
                r"['\"]([^'\"]*https?://[^'\"]+)['\"]"
            ]
            
            for pattern in url_patterns:
                match = re.search(pattern, onclick)
                if match:
                    return self.process_url(match.group(1))
        
        # 方法3: 搜尋頁面中的join.gov.tw連結
        join_links = soup.find_all('a', href=re.compile(r'join\.gov\.tw'))
        if join_links:
            # 返回第一個找到的join.gov.tw連結
            for link in join_links:
                if link.get('href'):
                    return link.get('href')
        
        return None
    
    def process_url(self, url: str) -> str:
        """處理和標準化URL"""
        if not url:
            return ""
        
        url = url.strip()
        
        # 處理相對路徑
        if not url.startswith(('http://', 'https://')):
            if url.startswith('/'):
                return f"{self.base_url}{url}"
            else:
                return f"{self.base_url}/{url}"
        
        return url
    
    def generate_smart_url(self, draft: Dict) -> str:
        """
        生成智能URL
        如果沒有找到直接連結，生成一個有用的替代連結
        """
        title = draft.get('title', '')
        
        # 優先順序：
        # 1. 如果標題包含特定關鍵字，可能在join.gov.tw
        if '意見' in title or '公告' in title or '預告' in title:
            # 生成join.gov.tw搜尋連結
            search_query = quote(title[:50])  # 限制長度
            return f"https://join.gov.tw/policies/search?q={search_query}"
        
        # 2. 生成Google搜尋連結（搜尋標題+網站）
        search_terms = f"{title} site:law-out.mof.gov.tw OR site:join.gov.tw OR site:mof.gov.tw"
        google_search = f"https://www.google.com/search?q={quote(search_terms)}"
        
        self.logger.info(f"為「{title[:30]}...」生成搜尋連結")
        
        return google_search
    
    def convert_roc_date(self, roc_date_str: str) -> Optional[str]:
        """轉換民國年為西元年"""
        if not roc_date_str:
            return None
        
        try:
            # 移除多餘字符
            date_str = roc_date_str.strip()
            
            # 嘗試不同的格式
            patterns = [
                r'(\d{2,3})\.(\d{1,2})\.(\d{1,2})',
                r'(\d{2,3})/(\d{1,2})/(\d{1,2})',
                r'(\d{2,3})年(\d{1,2})月(\d{1,2})日'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, date_str)
                if match:
                    year = int(match.group(1)) + 1911
                    month = int(match.group(2))
                    day = int(match.group(3))
                    return f"{year}-{month:02d}-{day:02d}"
        except:
            pass
        
        return None
    
    def check_status(self, end_date_str: str) -> str:
        """檢查草案狀態"""
        if not end_date_str:
            return "進行中"
        
        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
            if end_date < datetime.now():
                return "已結束"
            else:
                return "進行中"
        except:
            return "未知"
    
    def generate_unique_id(self, draft: Dict) -> str:
        """生成唯一識別碼"""
        content = f"{draft.get('title', '')}{draft.get('announcement_date', '')}"
        return hashlib.md5(content.encode('utf-8')).hexdigest()[:12]
    
    def compare_and_update(self, new_drafts: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """比對歷史記錄"""
        history_file = self.data_dir / "draft_history.json"
        
        # 讀取歷史
        if history_file.exists():
            try:
                with open(history_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)
            except:
                history = []
        else:
            history = []
        
        # 比對
        history_ids = {item['id'] for item in history if 'id' in item}
        new_items = []
        
        for draft in new_drafts:
            if draft.get('id') and draft['id'] not in history_ids:
                new_items.append(draft)
        
        # 更新歷史
        if new_items:
            history.extend(new_items)
            if len(history) > 500:  # 限制大小
                history = history[-500:]
            
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
        
        return new_items, history
    
    def save_results(self, drafts: List[Dict]) -> None:
        """儲存結果"""
        if not drafts:
            return
        
        timestamp = datetime.now(self.tz_taipei).strftime('%Y%m%d_%H%M%S')
        
        # JSON
        json_file = self.data_dir / f'drafts_{timestamp}.json'
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(drafts, f, ensure_ascii=False, indent=2)
        
        # CSV
        csv_file = self.data_dir / f'drafts_{timestamp}.csv'
        df = pd.DataFrame(drafts)
        df.to_csv(csv_file, index=False, encoding='utf-8-sig')
        
        self.logger.info(f"資料已儲存: {json_file.name} 和 {csv_file.name}")
    
    def generate_report(self, new_drafts: List[Dict], total_drafts: List[Dict]) -> Dict:
        """生成報告"""
        report = {
            'execution_time': datetime.now(self.tz_taipei).isoformat(),
            'total_drafts': len(total_drafts),
            'new_drafts': len(new_drafts),
            'has_new': len(new_drafts) > 0,
            'status_summary': {},
            'url_statistics': {
                'with_original_url': sum(1 for d in total_drafts if d.get('url_type') == 'original'),
                'with_generated_url': sum(1 for d in total_drafts if d.get('url_type') == 'generated'),
                'total': len(total_drafts)
            }
        }
        
        # 統計狀態
        if total_drafts:
            df = pd.DataFrame(total_drafts)
            if 'status' in df.columns:
                report['status_summary'] = df['status'].value_counts().to_dict()
        
        # 儲存報告
        report_file = self.data_dir / "draft_report.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        return report

def main():
    """主程式"""
    print("="*60)
    print("🏛️ 財政部法規草案爬蟲 - URL修正版")
    print(f"🕐 執行時間: {datetime.now()}")
    print("🔗 確保每個草案都有可用連結")
    print("="*60)
    
    try:
        scraper = DraftLawScraperFixed()
        
        # 爬取
        print("\n📡 開始爬取法規草案...")
        drafts = scraper.fetch_draft_laws()
        
        if not drafts:
            print("⚠️ 未獲取任何草案資料")
            scraper.generate_report([], [])
            return
        
        print(f"\n✅ 成功爬取 {len(drafts)} 筆草案")
        
        # 顯示URL統計
        original_urls = sum(1 for d in drafts if d.get('url_type') == 'original')
        generated_urls = sum(1 for d in drafts if d.get('url_type') == 'generated')
        
        print(f"\n🔗 URL 統計:")
        print(f"   • 原始連結: {original_urls} 筆")
        print(f"   • 生成連結: {generated_urls} 筆")
        
        # 預覽
        print("\n📋 資料預覽:")
        for i, draft in enumerate(drafts[:3], 1):
            print(f"\n  {i}. {draft.get('title', 'N/A')[:50]}...")
            print(f"     URL類型: {draft.get('url_type', 'N/A')}")
            if draft.get('url'):
                print(f"     連結: {draft['url'][:60]}...")
        
        # 比對歷史
        print("\n📊 比對歷史記錄...")
        new_items, history = scraper.compare_and_update(drafts)
        
        if new_items:
            print(f"\n🆕 發現 {len(new_items)} 筆新草案!")
        else:
            print("\n✨ 沒有新草案")
        
        # 儲存
        print("\n💾 儲存資料...")
        scraper.save_results(drafts)
        
        # 報告
        print("\n📋 生成報告...")
        report = scraper.generate_report(new_items, drafts)
        
        print("\n✅ 執行完成！")
        print("🔗 所有草案都已確保有可用連結")
        
    except Exception as e:
        print(f"\n❌ 執行失敗: {e}")
        import traceback
        traceback.print_exc()
        exit(1)

if __name__ == "__main__":
    main()
