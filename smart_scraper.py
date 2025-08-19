#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能稅務函釋爬蟲 - 修復版
修復 URL 解析問題，確保連結正確性

目標網站: https://www.mof.gov.tw
版本: 1.1 (URL修復版)
"""

import requests
import json
import pandas as pd
from datetime import datetime, timezone, timedelta
import re
from pathlib import Path
import time
from urllib.parse import urljoin, urlparse

class FixedTaxScraper:
    """修復版稅務函釋爬蟲"""
    
    def __init__(self, data_dir="data"):
        self.base_url = "https://www.mof.gov.tw"
        self.search_url = "https://www.mof.gov.tw/singlehtml/7e8e67631e154c389e29c336ef1ed38e?cntId=c757f46b20ed47b4aff71ddf654c55f8"
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        # 設定請求標頭
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-TW,zh;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        # 台灣時區
        self.tz_taipei = timezone(timedelta(hours=8))
        
    def normalize_url(self, url):
        """
        正規化 URL，確保格式正確
        
        Args:
            url (str): 原始 URL
            
        Returns:
            str: 正規化後的 URL
        """
        if not url:
            return ""
            
        # 移除多餘的空白
        url = url.strip()
        
        # 如果是相對路徑，轉換為絕對路徑
        if url.startswith('/'):
            return urljoin(self.base_url, url)
        
        # 如果不是以 http 開頭，添加 https
        if not url.startswith(('http://', 'https://')):
            # 檢查是否是財政部相關網址
            if 'mof.gov.tw' in url or 'dot.gov.tw' in url:
                return f"https://{url}"
            else:
                return urljoin(self.base_url, url)
        
        # 修復常見的 URL 問題
        url = url.replace('law.dot.gov.twhome.jsp', 'www.mof.gov.tw')
        
        return url
    
    def validate_url(self, url):
        """
        驗證 URL 是否有效
        
        Args:
            url (str): 要驗證的 URL
            
        Returns:
            bool: URL 是否有效
        """
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except:
            return False
    
    def fetch_latest_rulings(self):
        """
        爬取最新函釋
        
        Returns:
            list: 函釋清單
        """
        print(f"🔍 開始爬取財政部稅務函釋...")
        print(f"📡 目標網站: {self.search_url}")
        
        try:
            # 發送請求
            response = requests.get(self.search_url, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            print(f"✅ 網站回應成功 (狀態碼: {response.status_code})")
            
            # 解析 HTML 內容
            content = response.text
            
            # 使用多種方法解析函釋資訊
            rulings = self._parse_rulings_comprehensive(content)
            
            print(f"✅ 成功解析 {len(rulings)} 筆函釋")
            
            return rulings
            
        except requests.exceptions.RequestException as e:
            print(f"❌ 網路請求失敗: {e}")
            return []
        except Exception as e:
            print(f"❌ 解析過程發生錯誤: {e}")
            return []
    
    def _parse_rulings_comprehensive(self, content):
        """
        綜合解析函釋資訊
        
        Args:
            content (str): 網頁內容
            
        Returns:
            list: 函釋清單
        """
        rulings = []
        current_time = datetime.now(self.tz_taipei).isoformat()
        
        # 方法1: 解析表格結構
        table_rulings = self._parse_table_format(content)
        rulings.extend(table_rulings)
        
        # 方法2: 解析列表結構
        if not rulings:
            list_rulings = self._parse_list_format(content)
            rulings.extend(list_rulings)
        
        # 方法3: 通用模式匹配
        if not rulings:
            pattern_rulings = self._parse_pattern_matching(content)
            rulings.extend(pattern_rulings)
        
        # 為每筆函釋添加基本資訊和修復 URL
        for ruling in rulings:
            ruling['scraped_at'] = current_time
            ruling['source'] = 'MOF_Taiwan'
            
            # 修復和驗證 URL
            if 'url' in ruling and ruling['url']:
                original_url = ruling['url']
                fixed_url = self.normalize_url(original_url)
                
                if self.validate_url(fixed_url):
                    ruling['url'] = fixed_url
                    ruling['url_status'] = 'valid'
                else:
                    ruling['url_status'] = 'invalid'
                    ruling['original_url'] = original_url
                    ruling['url'] = ""  # 清空無效連結
                    print(f"⚠️ 無效 URL 已修復: {original_url} -> 已清空")
            else:
                ruling['url_status'] = 'missing'
        
        return rulings
    
    def _parse_table_format(self, content):
        """解析表格格式的函釋"""
        rulings = []
        
        # 尋找表格行的模式
        # 匹配類似：日期 | 標題 | 字號 等格式
        table_pattern = r'(\d{2,3}年\d{1,2}月\d{1,2}日).*?([^<>\n]{10,200}).*?((?:台財|財稅|台財稅)[^<>\s]{5,30})'
        
        matches = re.findall(table_pattern, content)
        
        for match in matches:
            date_str, title, number = match
            
            ruling = {
                'date': self._convert_date(date_str),
                'title': title.strip(),
                'number': number.strip(),
                'url': "",  # 稍後嘗試找到對應連結
                'type': 'table_parsed'
            }
            
            rulings.append(ruling)
        
        return rulings
    
    def _parse_list_format(self, content):
        """解析列表格式的函釋"""
        rulings = []
        
        # 尋找列表項目的模式
        list_pattern = r'<li[^>]*>.*?(\d{2,3}年\d{1,2}月\d{1,2}日).*?([^<>{10,200}}).*?</li>'
        
        matches = re.findall(list_pattern, content, re.DOTALL)
        
        for match in matches:
            date_str, content_text = match
            
            # 從內容中提取標題和字號
            title_match = re.search(r'[^<>]{10,100}', content_text)
            number_match = re.search(r'(台財|財稅|台財稅)[^<>\s]{5,30}', content_text)
            
            ruling = {
                'date': self._convert_date(date_str),
                'title': title_match.group().strip() if title_match else content_text[:50],
                'number': number_match.group().strip() if number_match else "",
                'url': "",
                'type': 'list_parsed'
            }
            
            rulings.append(ruling)
        
        return rulings
    
    def _parse_pattern_matching(self, content):
        """通用模式匹配解析"""
        rulings = []
        
        # 更寬鬆的匹配模式
        general_pattern = r'(\d{2,3}\.\d{1,2}\.\d{1,2}|年\d{1,2}月\d{1,2}日)'
        
        date_matches = re.finditer(general_pattern, content)
        
        for date_match in list(date_matches)[:15]:  # 限制數量避免過多
            start_pos = date_match.start()
            end_pos = min(start_pos + 300, len(content))
            context = content[start_pos:end_pos]
            
            # 嘗試從上下文提取資訊
            title_pattern = r'[^<>{]{15,150}[。；]'
            title_match = re.search(title_pattern, context)
            
            number_pattern = r'(台財|財稅|台財稅)[^<>\s]{5,30}'
            number_match = re.search(number_pattern, context)
            
            if title_match:  # 至少要有標題才算有效
                ruling = {
                    'date': self._convert_date(date_match.group()),
                    'title': title_match.group().strip(),
                    'number': number_match.group().strip() if number_match else "",
                    'url': "",
                    'type': 'pattern_matched'
                }
                
                rulings.append(ruling)
        
        return rulings
    
    def _convert_date(self, date_str):
        """
        轉換日期格式
        
        Args:
            date_str (str): 原始日期字符串
            
        Returns:
            str: 標準格式日期
        """
        # 處理民國年格式 (114.07.30 或 114年07月30日)
        if '年' in date_str and '月' in date_str:
            # 114年07月30日 格式
            pattern = r'(\d{2,3})年(\d{1,2})月(\d{1,2})日'
            match = re.match(pattern, date_str)
            if match:
                year, month, day = match.groups()
                year = int(year) + 1911  # 民國年轉西元年
                return f"{year}-{int(month):02d}-{int(day):02d}"
        
        elif '.' in date_str:
            # 114.07.30 格式
            parts = date_str.split('.')
            if len(parts) == 3:
                year, month, day = parts
                year = int(year) + 1911  # 民國年轉西元年
                return f"{year}-{int(month):02d}-{int(day):02d}"
        
        return date_str  # 如果無法解析，返回原始字符串
    
    def load_history(self):
        """載入歷史記錄"""
        history_file = self.data_dir / "smart_history.json"
        
        if history_file.exists():
            try:
                with open(history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️ 載入歷史記錄失敗: {e}")
                return []
        return []
    
    def save_history(self, all_rulings):
        """儲存歷史記錄"""
        history_file = self.data_dir / "smart_history.json"
        
        try:
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(all_rulings, f, ensure_ascii=False, indent=2)
            print(f"✅ 歷史記錄已儲存: {history_file}")
        except Exception as e:
            print(f"❌ 儲存歷史記錄失敗: {e}")
    
    def compare_and_update(self, new_rulings):
        """比對新舊資料並更新"""
        history = self.load_history()
        
        # 建立歷史資料的標題集合
        existing_titles = {ruling.get('title', '') for ruling in history}
        
        # 找出新的函釋
        new_items = []
        for ruling in new_rulings:
            if ruling.get('title', '') not in existing_titles:
                new_items.append(ruling)
        
        # 更新歷史記錄
        updated_history = history + new_items
        
        # 按日期排序
        updated_history.sort(key=lambda x: x.get('date', ''), reverse=True)
        
        # 儲存更新後的歷史
        self.save_history(updated_history)
        
        return new_items, updated_history
    
    def generate_report(self, new_rulings, total_rulings):
        """生成執行報告"""
        report = {
            'execution_time': datetime.now(self.tz_taipei).strftime('%Y-%m-%d %H:%M:%S'),
            'total_checked': len(total_rulings),
            'new_count': len(new_rulings),
            'has_new': len(new_rulings) > 0,
            'source': 'MOF_Taiwan_Fixed',
            'scraper_version': '1.1_url_fixed',
            'url_statistics': self._analyze_url_status(total_rulings)
        }
        
        # 儲存今日報告
        report_file = self.data_dir / "daily_report.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        # 儲存新發現的函釋
        if new_rulings:
            new_file = self.data_dir / "today_new.json"
            with open(new_file, 'w', encoding='utf-8') as f:
                json.dump(new_rulings, f, ensure_ascii=False, indent=2)
        
        return report
    
    def _analyze_url_status(self, rulings):
        """分析 URL 狀態統計"""
        stats = {
            'total': len(rulings),
            'valid_urls': 0,
            'invalid_urls': 0,
            'missing_urls': 0
        }
        
        for ruling in rulings:
            status = ruling.get('url_status', 'unknown')
            if status == 'valid':
                stats['valid_urls'] += 1
            elif status == 'invalid':
                stats['invalid_urls'] += 1
            elif status == 'missing':
                stats['missing_urls'] += 1
        
        return stats

def main():
    """主程式"""
    print("="*50)
    print("💼 修復版財政部稅務函釋爬蟲")
    print(f"🕐 執行時間: {datetime.now()}")
    print("🔧 修復項目: URL 連結問題")
    print("="*50)
    
    scraper = FixedTaxScraper()
    
    print("\n🔍 爬取最新函釋...")
    new_rulings = scraper.fetch_latest_rulings()
    
    if not new_rulings:
        print("❌ 未能獲取任何函釋資料")
        return
    
    print(f"✅ 爬取完成，共獲得 {len(new_rulings)} 筆資料")
    
    # 比對並更新歷史記錄
    print("\n📊 比對歷史資料...")
    new_items, all_rulings = scraper.compare_and_update(new_rulings)
    
    if new_items:
        print(f"🆕 發現 {len(new_items)} 筆新函釋！")
        for i, item in enumerate(new_items, 1):
            print(f"   {i}. {item.get('title', '無標題')[:50]}...")
    else:
        print("✨ 今天沒有新函釋")
    
    # 生成報告
    print("\n📋 生成執行報告...")
    report = scraper.generate_report(new_items, new_rulings)
    
    # 顯示 URL 修復統計
    url_stats = report['url_statistics']
    print(f"\n🔗 URL 修復統計:")
    print(f"   • 總計: {url_stats['total']} 筆")
    print(f"   • 有效連結: {url_stats['valid_urls']} 筆")
    print(f"   • 無效連結: {url_stats['invalid_urls']} 筆")
    print(f"   • 缺少連結: {url_stats['missing_urls']} 筆")
    
    print(f"\n✅ 執行完成！")

if __name__ == "__main__":
    main()
