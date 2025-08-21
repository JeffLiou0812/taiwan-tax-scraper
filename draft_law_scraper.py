#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
財政部法規草案爬蟲 - 錯誤防護加強版
基於過去錯誤經驗優化的版本

目標網站: https://law-out.mof.gov.tw/DraftForum.aspx
版本: 3.0 Error-Protected
建立日期: 2025-08-20
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
from urllib.parse import urljoin, urlparse

class DraftLawScraperProtected:
    """錯誤防護加強版法規草案爬蟲"""
    
    def __init__(self, data_dir="data"):
        """初始化爬蟲"""
        self.base_url = "https://law-out.mof.gov.tw/DraftForum.aspx"
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        # 錯誤防護1: 完整的請求標頭（避免robots.txt阻擋）
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0'
        }
        
        self.tz_taipei = timezone(timedelta(hours=8))
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        
    def validate_url(self, url):
        """
        錯誤防護2: URL驗證和修復
        學習自過去的 law.dot.gov.twhome.jsp 錯誤
        """
        if not url:
            return None
            
        url = url.strip()
        
        # 修復常見URL問題
        if not url.startswith(('http://', 'https://')):
            # 判斷是否為相對路徑
            if url.startswith('/'):
                url = 'https://law-out.mof.gov.tw' + url
            else:
                url = 'https://' + url
        
        # 驗證URL格式
        try:
            result = urlparse(url)
            if all([result.scheme, result.netloc]):
                return url
        except:
            pass
            
        return None
    
    def convert_roc_date_safe(self, roc_date_str):
        """
        錯誤防護3: 穩健的日期轉換
        支援多種民國年格式
        """
        if not roc_date_str:
            return None, roc_date_str
            
        roc_date_str = str(roc_date_str).strip()
        
        # 多重模式匹配（學習自過去錯誤）
        patterns = [
            (r'(\d{2,3})年(\d{1,2})月(\d{1,2})日', '%Y-%m-%d'),
            (r'(\d{2,3})\.(\d{1,2})\.(\d{1,2})', '%Y-%m-%d'),
            (r'(\d{2,3})/(\d{1,2})/(\d{1,2})', '%Y-%m-%d'),
            (r'民國(\d{2,3})年(\d{1,2})月(\d{1,2})日', '%Y-%m-%d')
        ]
        
        for pattern, date_format in patterns:
            match = re.search(pattern, roc_date_str)
            if match:
                try:
                    roc_year = int(match.group(1))
                    month = int(match.group(2))
                    day = int(match.group(3))
                    
                    # 轉換為西元年
                    ad_year = roc_year + 1911
                    iso_date = f"{ad_year:04d}-{month:02d}-{day:02d}"
                    
                    return iso_date, roc_date_str  # 同時返回兩種格式
                except:
                    continue
        
        return None, roc_date_str
    
    def fetch_draft_laws(self):
        """
        爬取法規草案列表
        包含完整錯誤處理
        """
        all_drafts = []
        
        try:
            print("🔍 開始爬取法規草案...")
            
            # 錯誤防護4: 重試機制
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = self.session.get(
                        self.base_url,
                        timeout=30,
                        verify=True
                    )
                    
                    if response.status_code == 200:
                        break
                    else:
                        print(f"⚠️ 嘗試 {attempt + 1}/{max_retries}: 狀態碼 {response.status_code}")
                        time.sleep(2)
                        
                except requests.exceptions.RequestException as e:
                    print(f"⚠️ 網路錯誤 (嘗試 {attempt + 1}/{max_retries}): {str(e)}")
                    if attempt < max_retries - 1:
                        time.sleep(3)
                    else:
                        raise
            
            # 錯誤防護5: 解析HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 尋找資料表格（根據實際網站結構調整）
            table = soup.find('table', {'class': 'table'}) or soup.find('table')
            
            if not table:
                print("⚠️ 未找到資料表格，嘗試其他解析方式...")
                # 備用解析方式
                rows = soup.find_all('tr')
            else:
                rows = table.find_all('tr')[1:]  # 跳過標題列
            
            for row in rows:
                try:
                    cols = row.find_all('td')
                    
                    if len(cols) >= 3:  # 確保有足夠的欄位
                        # 提取資料
                        date_text = cols[0].get_text(strip=True)
                        title_element = cols[1].find('a')
                        end_date_text = cols[2].get_text(strip=True) if len(cols) > 2 else ""
                        
                        # 處理標題和連結
                        if title_element:
                            title = title_element.get_text(strip=True)
                            raw_url = title_element.get('href', '')
                            
                            # 錯誤防護6: URL處理
                            if raw_url:
                                # 完整URL處理
                                if not raw_url.startswith('http'):
                                    raw_url = urljoin(self.base_url, raw_url)
                                
                                url = self.validate_url(raw_url)
                            else:
                                url = None
                        else:
                            title = cols[1].get_text(strip=True)
                            url = None
                        
                        # 日期轉換
                        iso_date, roc_date = self.convert_roc_date_safe(date_text)
                        end_iso_date, end_roc_date = self.convert_roc_date_safe(end_date_text)
                        
                        # 建立草案資料
                        draft = {
                            'title': title,
                            'announcement_date': iso_date,
                            'announcement_date_roc': roc_date,
                            'end_date': end_iso_date,
                            'end_date_roc': end_roc_date,
                            'url': url,
                            'original_url': raw_url if title_element else None,
                            'status': self.check_status(end_iso_date),
                            'source': 'MOF_Taiwan_Draft',
                            'scrape_time': datetime.now(self.tz_taipei).isoformat()
                        }
                        
                        # 生成唯一ID
                        draft['id'] = self.generate_unique_id(draft)
                        
                        all_drafts.append(draft)
                        
                except Exception as e:
                    print(f"⚠️ 解析單筆資料錯誤: {str(e)}")
                    continue
            
            print(f"✅ 成功爬取 {len(all_drafts)} 筆法規草案")
            
        except Exception as e:
            print(f"❌ 爬取失敗: {str(e)}")
            import traceback
            traceback.print_exc()
        
        return all_drafts
    
    def check_status(self, end_date_str):
        """檢查草案狀態"""
        if not end_date_str:
            return "進行中"
        
        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
            today = datetime.now()
            
            if end_date < today:
                return "已結束"
            else:
                return "進行中"
        except:
            return "未知"
    
    def generate_unique_id(self, draft):
        """生成唯一識別碼"""
        # 使用標題和日期生成ID
        content = f"{draft.get('title', '')}{draft.get('announcement_date', '')}"
        return hashlib.md5(content.encode('utf-8')).hexdigest()[:12]
    
    def compare_and_update(self, new_drafts):
        """
        比對歷史記錄，找出新增的草案
        """
        history_file = self.data_dir / "draft_history.json"
        
        # 讀取歷史記錄
        if history_file.exists():
            try:
                with open(history_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)
            except:
                history = []
        else:
            history = []
        
        # 建立ID集合進行比對
        history_ids = {item['id'] for item in history if 'id' in item}
        
        # 找出新草案
        new_items = []
        for draft in new_drafts:
            if draft['id'] not in history_ids:
                new_items.append(draft)
        
        # 更新歷史記錄
        if new_items:
            history.extend(new_items)
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
        
        return new_items, history
    
    def save_results(self, drafts, filename_prefix="drafts"):
        """
        儲存結果為JSON和CSV格式
        """
        if not drafts:
            print("⚠️ 沒有資料可儲存")
            return None
        
        timestamp = datetime.now(self.tz_taipei).strftime('%Y%m%d_%H%M%S')
        
        # 儲存JSON
        json_file = self.data_dir / f'{filename_prefix}_{timestamp}.json'
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(drafts, f, ensure_ascii=False, indent=2)
        
        # 儲存CSV
        csv_file = self.data_dir / f'{filename_prefix}_{timestamp}.csv'
        df = pd.DataFrame(drafts)
        df.to_csv(csv_file, index=False, encoding='utf-8-sig')
        
        print(f"💾 資料已儲存:")
        print(f"   JSON: {json_file}")
        print(f"   CSV: {csv_file}")
        
        return json_file
    
    def generate_report(self, new_drafts, total_drafts):
        """生成執行報告"""
        report = {
            'execution_time': datetime.now(self.tz_taipei).isoformat(),
            'total_drafts': len(total_drafts),
            'new_drafts': len(new_drafts),
            'has_new': len(new_drafts) > 0,
            'status_summary': {},
            'error_fixes_applied': [
                'URL validation and correction',
                'Multiple date format support',
                'Retry mechanism for network errors',
                'Comprehensive error handling'
            ]
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
    """主程式 - 包含完整錯誤處理"""
    print("="*60)
    print("🏛️ 財政部法規草案爬蟲 - 錯誤防護加強版")
    print(f"🕐 執行時間: {datetime.now()}")
    print("🛡️ 已應用過去7天的所有錯誤修復")
    print("="*60)
    
    try:
        scraper = DraftLawScraperProtected()
        
        # 爬取資料
        print("\n📡 開始爬取法規草案...")
        drafts = scraper.fetch_draft_laws()
        
        if not drafts:
            print("⚠️ 未獲取任何草案資料")
            return
        
        # 比對歷史
        print("\n📊 比對歷史資料...")
        new_items, all_drafts = scraper.compare_and_update(drafts)
        
        if new_items:
            print(f"🆕 發現 {len(new_items)} 筆新草案!")
            for i, item in enumerate(new_items[:5], 1):  # 顯示前5筆
                print(f"   {i}. {item.get('title', '無標題')[:50]}...")
        else:
            print("✨ 沒有新的法規草案")
        
        # 儲存結果
        print("\n💾 儲存資料...")
        scraper.save_results(drafts)
        
        # 生成報告
        print("\n📋 生成報告...")
        report = scraper.generate_report(new_items, all_drafts)
        
        print(f"\n📊 執行統計:")
        print(f"   • 總草案數: {report['total_drafts']}")
        print(f"   • 新增草案: {report['new_drafts']}")
        print(f"   • 狀態分布: {report.get('status_summary', {})}")
        
        print("\n✅ 法規草案爬蟲執行完成！")
        print("🛡️ 所有錯誤防護機制均已生效")
        
    except Exception as e:
        print(f"\n❌ 執行失敗: {str(e)}")
        import traceback
        traceback.print_exc()
        exit(1)

if __name__ == "__main__":
    main()
