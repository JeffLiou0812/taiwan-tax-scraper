#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
財政部賦稅署法規查詢系統 - 新頒函釋爬蟲（完整修正版）
包含標題/主旨提取改進

版本: 7.0 Complete Fixed
更新日期: 2025-08-20
目標網站: https://law.dot.gov.tw/law-ch/home.jsp

修正內容：
✅ 正確提取函釋主旨作為標題
✅ 完整錯誤防護機制
✅ 保留原始日期格式（不轉換）
✅ URL修復機制
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
from urllib.parse import urljoin, urlparse, urlencode
import logging
from typing import Dict, List, Tuple, Optional
import traceback

class TaxRulingScraper:
    """財政部賦稅署函釋爬蟲 - 完整修正版"""
    
    def __init__(self, data_dir="data", debug=True):
        """初始化爬蟲"""
        # 使用Path物件處理路徑
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        # 設定日誌系統
        self.setup_logging(debug)
        
        # 網站設定
        self.base_url = "https://law.dot.gov.tw"
        self.search_url = "https://law.dot.gov.tw/law-ch/home.jsp"
        
        # 查詢參數
        self.search_params = {
            'id': '18',
            'contentid': '18',
            'parentpath': '0,7',
            'mcustomize': 'newlaw_list.jsp',
            'istype': 'L',
            'classtablename': 'LawClass',
            'sort': '1',
            'up_down': 'D'
        }
        
        # 台灣時區
        self.tz_taipei = timezone(timedelta(hours=8))
        
        # 完整的請求標頭
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8,zh-CN;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Cache-Control': 'max-age=0',
            'Upgrade-Insecure-Requests': '1',
            'Referer': 'https://law.dot.gov.tw/',
            'DNT': '1'
        }
        
        # 建立Session
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        
        # 錯誤統計
        self.error_stats = {
            'url_errors_fixed': 0,
            'parse_errors_recovered': 0,
            'retry_attempts': 0,
            'total_errors': 0
        }
    
    def setup_logging(self, debug: bool):
        """設定日誌系統"""
        log_level = logging.DEBUG if debug else logging.INFO
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        self.logger = logging.getLogger(__name__)
    
    def safe_request(self, url: str, params: Dict = None, max_retries: int = 3) -> Optional[requests.Response]:
        """安全的網路請求，包含重試機制"""
        for attempt in range(max_retries):
            try:
                self.logger.debug(f"請求嘗試 {attempt + 1}/{max_retries}: {url}")
                
                response = self.session.get(
                    url,
                    params=params,
                    timeout=30,
                    verify=True,
                    allow_redirects=True
                )
                
                if response.status_code == 200:
                    self.logger.debug("請求成功")
                    return response
                elif response.status_code == 404:
                    self.logger.error(f"頁面不存在 (404): {url}")
                    return None
                else:
                    self.logger.warning(f"HTTP {response.status_code}")
                    self.error_stats['retry_attempts'] += 1
                    
            except requests.RequestException as e:
                self.logger.error(f"請求錯誤 (嘗試 {attempt + 1}/{max_retries}): {e}")
                self.error_stats['total_errors'] += 1
            
            if attempt < max_retries - 1:
                wait_time = min(2 ** attempt, 10)
                self.logger.info(f"等待 {wait_time} 秒後重試...")
                time.sleep(wait_time)
        
        self.logger.error(f"所有重試都失敗: {url}")
        return None
    
    def fix_url_comprehensive(self, url: str) -> str:
        """全面的URL修復機制"""
        if not url:
            return ""
        
        original_url = url
        url = str(url).strip()
        
        # 檢測並修復已知的錯誤模式
        error_patterns = [
            ('twhome.jsp', '/home.jsp'),
            ('gov.twhome', 'gov.tw/home'),
            ('lawlaw', 'law'),
            ('//', '/')
        ]
        
        for error_pattern, correct_pattern in error_patterns:
            if error_pattern in url and error_pattern != '//':
                self.logger.warning(f"偵測到URL錯誤模式: {error_pattern}")
                url = url.replace(error_pattern, correct_pattern)
                self.error_stats['url_errors_fixed'] += 1
        
        # 處理雙斜線
        if '//' in url and not url.startswith('http'):
            url = re.sub(r'(?<!:)//', '/', url)
        
        # 確保URL完整性
        if not url.startswith(('http://', 'https://')):
            if url.startswith('/'):
                url = self.base_url + url
            else:
                url = urljoin(f"{self.base_url}/law-ch/", url)
        
        # 強制HTTPS
        if url.startswith('http://law.dot.gov.tw'):
            url = url.replace('http://', 'https://')
        
        # 最終驗證
        try:
            result = urlparse(url)
            if not all([result.scheme, result.netloc]):
                self.logger.error(f"URL驗證失敗: {url}")
                return original_url
        except:
            return original_url
        
        if url != original_url:
            self.logger.info(f"URL已修復: {original_url} -> {url}")
        
        return url
    
    def extract_date(self, text: str) -> str:
        """提取日期但不轉換（保留原始民國年格式）"""
        if not text:
            return ""
        
        # 搜尋各種日期格式
        date_patterns = [
            r'\d{2,3}年\d{1,2}月\d{1,2}日',
            r'\d{2,3}\.\d{1,2}\.\d{1,2}',
            r'\d{2,3}/\d{1,2}/\d{1,2}',
            r'民國\d{2,3}年\d{1,2}月\d{1,2}日',
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0)
        
        return ""
    
    def parse_rulings_smart(self, html_content: str) -> List[Dict]:
        """智能解析，使用多重策略"""
        rulings = []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 策略1：表格解析
            self.logger.debug("嘗試表格解析策略...")
            tables = soup.find_all('table')
            
            for table in tables:
                if 'navigation' in str(table.get('class', [])).lower():
                    continue
                
                rows = table.find_all('tr')
                for row in rows[1:]:  # 跳過標題列
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:
                        ruling = self.extract_ruling_from_cells(cells)
                        if ruling:
                            rulings.append(ruling)
            
            # 策略2：列表解析
            if not rulings:
                self.logger.debug("表格解析無結果，嘗試列表解析...")
                containers = soup.find_all(['div', 'ul', 'ol'], class_=re.compile(r'law|list|item|content'))
                
                for container in containers:
                    items = container.find_all(['li', 'div', 'p'])
                    for item in items:
                        ruling = self.extract_ruling_from_element(item)
                        if ruling:
                            rulings.append(ruling)
            
            # 策略3：全文搜尋
            if not rulings:
                self.logger.debug("列表解析無結果，使用全文搜尋...")
                all_text = soup.get_text()
                lines = all_text.split('\n')
                
                for i, line in enumerate(lines):
                    if self.extract_date(line):
                        ruling = {
                            'date': self.extract_date(line),
                            'title': lines[i+1] if i+1 < len(lines) else line,
                            'source': 'DOT_Taiwan',
                            'scrape_time': datetime.now(self.tz_taipei).isoformat()
                        }
                        ruling['id'] = self.generate_id(ruling)
                        rulings.append(ruling)
            
            self.logger.info(f"成功解析 {len(rulings)} 筆函釋")
            
        except Exception as e:
            self.logger.error(f"解析錯誤: {e}")
            self.error_stats['total_errors'] += 1
            self.error_stats['parse_errors_recovered'] += 1
        
        return rulings
    
    def extract_ruling_from_cells(self, cells) -> Optional[Dict]:
        """
        從表格儲存格提取函釋資訊
        改進版：確保正確提取主旨作為標題
        """
        try:
            ruling = {
                'source': 'DOT_Taiwan',
                'scrape_time': datetime.now(self.tz_taipei).isoformat()
            }
            
            has_content = False
            doc_number = ""
            title_content = ""
            date_text = ""
            
            # 第一輪：收集所有資訊
            for i, cell in enumerate(cells):
                cell_text = cell.get_text(strip=True)
                
                # 提取日期
                if not date_text:
                    date = self.extract_date(cell_text)
                    if date:
                        date_text = date
                        ruling['date'] = date
                        has_content = True
                
                # 提取字號
                if re.search(r'[台財稅].*?第?\d+號', cell_text):
                    doc_number = cell_text
                    ruling['doc_number'] = doc_number
                    has_content = True
                
                # 提取連結
                links = cell.find_all('a')
                for link in links:
                    link_text = link.get_text(strip=True)
                    href = link.get('href', '')
                    
                    # 判斷連結文字是否為主旨
                    if link_text and not re.match(r'^[台財稅].*?第?\d+號', link_text):
                        # 這個連結文字不是字號，應該是主旨
                        if len(link_text) > len(title_content):
                            title_content = link_text
                    
                    if href:
                        ruling['url'] = self.fix_url_comprehensive(href)
                        ruling['original_url'] = href
                        has_content = True
                
                # 如果這個儲存格有較長的文字，且不是日期或字號，可能是主旨
                if len(cell_text) > 20:
                    # 排除純日期、字號
                    if not re.match(r'^[\d年月日\.\/ ]+$', cell_text) and \
                       not re.search(r'^[台財稅].*?第?\d+號$', cell_text):
                        # 如果還沒有標題，或這個文字更長更詳細
                        if not title_content or len(cell_text) > len(title_content):
                            title_content = cell_text[:500]  # 限制長度
            
            # 第二輪：組合標題
            if title_content:
                ruling['title'] = title_content
            elif doc_number:
                # 如果真的沒有找到主旨，至少用字號
                ruling['title'] = doc_number
            else:
                # 最後的備案
                ruling['title'] = date_text if date_text else "無標題"
            
            # 確保有基本資訊才返回
            if has_content and (ruling.get('date') or ruling.get('doc_number') or len(ruling.get('title', '')) > 10):
                ruling['id'] = self.generate_id(ruling)
                self.logger.debug(f"提取成功 - 標題: {ruling.get('title', '')[:50]}...")
                return ruling
                
        except Exception as e:
            self.logger.debug(f"儲存格提取錯誤: {e}")
            
        return None
    
    def extract_ruling_from_element(self, element) -> Optional[Dict]:
        """從HTML元素提取函釋資訊"""
        try:
            text = element.get_text(strip=True)
            
            if len(text) < 10:
                return None
            
            ruling = {
                'source': 'DOT_Taiwan',
                'scrape_time': datetime.now(self.tz_taipei).isoformat()
            }
            
            # 提取日期
            date = self.extract_date(text)
            if date:
                ruling['date'] = date
            
            # 提取字號
            doc_match = re.search(r'([台財稅].*?第?\d+號)', text)
            if doc_match:
                ruling['doc_number'] = doc_match.group(1)
            
            # 提取連結和主旨
            links = element.find_all('a')
            title_content = ""
            
            for link in links:
                link_text = link.get_text(strip=True)
                href = link.get('href', '')
                
                # 優先使用非字號的連結文字作為標題
                if link_text and not re.match(r'^[台財稅].*?第?\d+號', link_text):
                    if len(link_text) > len(title_content):
                        title_content = link_text
                
                if href:
                    ruling['url'] = self.fix_url_comprehensive(href)
            
            # 設定標題
            if title_content:
                ruling['title'] = title_content
            elif doc_match:
                # 尋找字號之後的文字作為主旨
                after_doc = text[doc_match.end():].strip()
                if after_doc and len(after_doc) > 10:
                    ruling['title'] = after_doc[:300]
                else:
                    ruling['title'] = text[:200]
            else:
                ruling['title'] = text[:200]
            
            # 只有在有實質內容時才返回
            if ruling.get('date') or ruling.get('title'):
                ruling['id'] = self.generate_id(ruling)
                return ruling
                
        except Exception as e:
            self.logger.debug(f"元素提取錯誤: {e}")
            
        return None
    
    def generate_id(self, ruling: Dict) -> str:
        """生成唯一識別碼"""
        key_parts = [
            ruling.get('date', ''),
            ruling.get('doc_number', ''),
            ruling.get('title', '')[:50]
        ]
        key_string = '|'.join(filter(None, key_parts))
        return hashlib.md5(key_string.encode('utf-8')).hexdigest()[:12]
    
    def fetch_new_rulings(self, max_pages: int = 3) -> List[Dict]:
        """主要爬取函數"""
        all_rulings = []
        
        self.logger.info("="*60)
        self.logger.info("開始爬取財政部賦稅署新頒函釋")
        self.logger.info(f"目標: {self.search_url}")
        self.logger.info("="*60)
        
        for page in range(1, max_pages + 1):
            try:
                params = self.search_params.copy()
                if page > 1:
                    params['page'] = str(page)
                
                self.logger.info(f"\n正在爬取第 {page} 頁...")
                
                response = self.safe_request(self.search_url, params)
                
                if not response:
                    self.logger.warning(f"第 {page} 頁無法取得")
                    if page == 1:
                        self.logger.error("無法取得第一頁資料，停止爬取")
                        break
                    continue
                
                page_rulings = self.parse_rulings_smart(response.text)
                
                if not page_rulings:
                    self.logger.info(f"第 {page} 頁無資料，停止爬取")
                    break
                
                all_rulings.extend(page_rulings)
                self.logger.info(f"第 {page} 頁成功: {len(page_rulings)} 筆")
                
                # 顯示提取的標題（用於驗證）
                for ruling in page_rulings[:2]:  # 顯示前2筆
                    self.logger.debug(f"  標題: {ruling.get('title', 'N/A')[:50]}...")
                
                if page < max_pages:
                    time.sleep(1)
                    
            except Exception as e:
                self.logger.error(f"爬取第 {page} 頁發生錯誤: {e}")
                self.error_stats['total_errors'] += 1
                continue
        
        self.logger.info(f"\n總共爬取: {len(all_rulings)} 筆函釋")
        return all_rulings
    
    def compare_and_update(self, new_rulings: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """比對歷史記錄，找出新增的函釋"""
        history_file = self.data_dir / "smart_history.json"
        
        history = []
        if history_file.exists():
            try:
                with open(history_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if content:
                        history = json.loads(content)
                    self.logger.info(f"載入 {len(history)} 筆歷史記錄")
            except json.JSONDecodeError as e:
                self.logger.error(f"JSON解析錯誤: {e}")
                backup_file = history_file.with_suffix('.json.backup')
                history_file.rename(backup_file)
                self.logger.info(f"已備份損壞的歷史檔案到 {backup_file}")
            except Exception as e:
                self.logger.error(f"讀取歷史記錄失敗: {e}")
        
        # 比對新資料
        history_ids = {item.get('id') for item in history if item.get('id')}
        new_items = []
        
        for ruling in new_rulings:
            if ruling.get('id') and ruling['id'] not in history_ids:
                new_items.append(ruling)
        
        self.logger.info(f"發現 {len(new_items)} 筆新函釋")
        
        # 更新歷史記錄
        if new_items:
            history.extend(new_items)
            
            if len(history) > 1000:
                history = history[-1000:]
            
            try:
                temp_file = history_file.with_suffix('.json.tmp')
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(history, f, ensure_ascii=False, indent=2)
                
                with open(temp_file, 'r', encoding='utf-8') as f:
                    json.load(f)
                
                temp_file.replace(history_file)
                self.logger.info("歷史記錄已安全更新")
                
            except Exception as e:
                self.logger.error(f"更新歷史記錄失敗: {e}")
                if temp_file.exists():
                    temp_file.unlink()
        
        return new_items, history
    
    def generate_report(self, new_items: List[Dict], total_rulings: List[Dict]) -> Dict:
        """生成執行報告"""
        report = {
            'execution_time': datetime.now(self.tz_taipei).isoformat(),
            'execution_date': datetime.now(self.tz_taipei).strftime('%Y-%m-%d'),
            'total_checked': len(total_rulings),
            'new_count': len(new_items),
            'has_new': len(new_items) > 0,
            'source': 'law.dot.gov.tw',
            'scraper_version': '7.0_Complete_Fixed',
            'error_statistics': self.error_stats,
            'status': 'success' if total_rulings else 'no_data'
        }
        
        # 儲存報告
        report_file = self.data_dir / "daily_report.json"
        try:
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            self.logger.info("報告已生成")
        except Exception as e:
            self.logger.error(f"報告生成失敗: {e}")
            basic_report = {'has_new': False, 'status': 'error'}
            with open(report_file, 'w') as f:
                json.dump(basic_report, f)
        
        # 儲存新函釋
        if new_items:
            new_file = self.data_dir / "today_new.json"
            try:
                with open(new_file, 'w', encoding='utf-8') as f:
                    json.dump(new_items, f, ensure_ascii=False, indent=2)
                self.logger.info(f"新函釋已儲存: {len(new_items)} 筆")
            except Exception as e:
                self.logger.error(f"儲存新函釋失敗: {e}")
        
        return report
    
    def save_results(self, rulings: List[Dict]) -> None:
        """儲存結果為多種格式"""
        if not rulings:
            return
        
        timestamp = datetime.now(self.tz_taipei).strftime('%Y%m%d_%H%M%S')
        
        # JSON格式
        json_file = self.data_dir / f'smart_results_{timestamp}.json'
        try:
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(rulings, f, ensure_ascii=False, indent=2)
            self.logger.info(f"JSON已儲存: {json_file.name}")
        except Exception as e:
            self.logger.error(f"JSON儲存失敗: {e}")
        
        # CSV格式
        csv_file = self.data_dir / f'smart_results_{timestamp}.csv'
        try:
            df = pd.DataFrame(rulings)
            df.to_csv(csv_file, index=False, encoding='utf-8-sig')
            self.logger.info(f"CSV已儲存: {csv_file.name}")
        except Exception as e:
            self.logger.error(f"CSV儲存失敗: {e}")

def main():
    """主程式"""
    print("="*70)
    print("🏛️ 財政部賦稅署新頒函釋爬蟲 - 完整修正版")
    print(f"📍 目標網站: law.dot.gov.tw")
    print(f"🕐 執行時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📌 版本: 7.0 - 包含標題提取改進")
    print("="*70)
    
    try:
        # 初始化
        print("\n⚙️ 初始化系統...")
        scraper = TaxRulingScraper(debug=True)
        
        # 爬取
        print("\n📡 開始爬取...")
        rulings = scraper.fetch_new_rulings(max_pages=3)
        
        if not rulings:
            print("\n⚠️ 未爬取到資料")
            scraper.generate_report([], [])
            return
        
        print(f"\n✅ 成功爬取 {len(rulings)} 筆函釋")
        
        # 資料預覽（顯示標題驗證）
        print("\n📋 資料預覽（驗證標題提取）：")
        for i, ruling in enumerate(rulings[:5], 1):
            print(f"\n  {i}. 標題: {ruling.get('title', 'N/A')[:80]}")
            print(f"     日期: {ruling.get('date', 'N/A')}")
            print(f"     字號: {ruling.get('doc_number', 'N/A')}")
        
        # 比對歷史
        print("\n🔍 比對歷史記錄...")
        new_items, history = scraper.compare_and_update(rulings)
        
        if new_items:
            print(f"\n🎉 發現 {len(new_items)} 筆新函釋")
            for i, item in enumerate(new_items[:3], 1):
                print(f"\n  {i}. 標題: {item.get('title', 'N/A')[:80]}")
                print(f"     日期: {item.get('date', 'N/A')}")
        else:
            print("\n✨ 無新函釋")
        
        # 儲存
        print("\n💾 儲存資料...")
        scraper.save_results(rulings)
        
        # 報告
        print("\n📊 生成報告...")
        report = scraper.generate_report(new_items, rulings)
        
        # 統計
        print("\n📈 執行統計：")
        print(f"  • 總處理數: {len(rulings)}")
        print(f"  • 新函釋數: {len(new_items)}")
        print(f"  • URL修復: {report['error_statistics']['url_errors_fixed']}")
        print(f"  • 錯誤恢復: {report['error_statistics']['parse_errors_recovered']}")
        
        print("\n✅ 執行完成！")
        
    except KeyboardInterrupt:
        print("\n⚠️ 使用者中斷執行")
    except Exception as e:
        print(f"\n❌ 嚴重錯誤: {e}")
        traceback.print_exc()
        
        # 確保有報告
        try:
            report = {
                'execution_time': datetime.now().isoformat(),
                'has_new': False,
                'status': 'error',
                'error': str(e)
            }
            report_file = Path("data") / "daily_report.json"
            report_file.parent.mkdir(exist_ok=True)
            with open(report_file, 'w') as f:
                json.dump(report, f)
        except:
            pass
        
        exit(1)

if __name__ == "__main__":
    main()
