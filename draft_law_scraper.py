#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
改進版財政部法規草案爬蟲
- 更智能的重複檢測機制
- 過期草案狀態追蹤
- URL-based 去重邏輯
- 完整的變化追蹤 (新增/更新/過期)

目標網站: https://law-out.mof.gov.tw/DraftForum.aspx
作者: 自動化稅務法規追蹤系統
版本: 2.0 Enhanced
日期: 2025-08-19
"""

import requests
import json
import pandas as pd
from datetime import datetime, timezone, timedelta
import re
from pathlib import Path
import hashlib
import time

class ImprovedDraftLawScraper:
    """改進版法規草案爬蟲類別"""
    
    def __init__(self, data_dir="data"):
        """
        初始化爬蟲
        
        Args:
            data_dir (str): 資料儲存目錄
        """
        self.base_url = "https://law-out.mof.gov.tw/DraftForum.aspx"
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        # 設定請求標頭 - 模擬正常瀏覽器
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
        
    def generate_unique_id(self, draft):
        """
        生成唯一識別碼
        
        Args:
            draft (dict): 法規草案資料
            
        Returns:
            str: 12位唯一識別碼
        """
        # 使用 URL 作為主要識別碼，如果沒有 URL 則使用標題+日期
        if draft.get('url'):
            return hashlib.md5(draft['url'].encode('utf-8')).hexdigest()[:12]
        else:
            content = f"{draft.get('title', '')}{draft.get('date', '')}"
            return hashlib.md5(content.encode('utf-8')).hexdigest()[:12]
    
    def convert_roc_date(self, roc_date):
        """
        轉換民國年為西元年
        
        Args:
            roc_date (str): 民國年日期 (格式: 114.08.19)
            
        Returns:
            str: 西元年日期 (格式: 2025-08-19)
        """
        try:
            parts = roc_date.split('.')
            if len(parts) == 3:
                year = int(parts[0]) + 1911  # 民國年轉西元年
                month = int(parts[1])
                day = int(parts[2])
                return f"{year}-{month:02d}-{day:02d}"
        except (ValueError, IndexError):
            print(f"⚠️ 日期格式錯誤: {roc_date}")
        
        return roc_date
    
    def fetch_draft_laws(self):
        """
        爬取法規草案
        
        Returns:
            list: 法規草案清單
        """
        print(f"🔍 開始爬取法規草案...")
        print(f"📡 目標網站: {self.base_url}")
        
        try:
            # 發送請求
            print("📡 發送網路請求...")
            response = requests.get(self.base_url, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            print(f"✅ 網站回應成功 (狀態碼: {response.status_code})")
            print(f"📄 回應內容大小: {len(response.text)} 字元")
            
            content = response.text
            
            # 使用正則表達式解析表格結構
            # 模式：序號 | 日期 | 標題連結 | 預告終止日
            print("🔍 解析網頁內容...")
            pattern = r'(\d+)\.\s*\|\s*(\d{3}\.\d{2}\.\d{2})\s*\|\s*\[([^\]]+)\]\(([^)]+)\)\s*（預告終止日(\d{3}\.\d{2}\.\d{2})）'
            
            matches = re.findall(pattern, content)
            
            if not matches:
                print("⚠️ 主要解析方法未找到資料，嘗試備用解析...")
                return self._alternative_parsing(content)
            
            print(f"✅ 正則表達式找到 {len(matches)} 筆匹配")
            
            # 轉換為結構化資料
            draft_laws = []
            current_time = datetime.now(self.tz_taipei).isoformat()
            
            for i, match in enumerate(matches, 1):
                seq_num, date_str, title, url, end_date = match
                
                print(f"📝 處理第 {i} 筆: {title[:30]}...")
                
                draft_law = {
                    'sequence': int(seq_num),
                    'date': self.convert_roc_date(date_str),
                    'roc_date': date_str,
                    'title': title.strip(),
                    'url': url.strip(),
                    'end_date': self.convert_roc_date(end_date),
                    'roc_end_date': end_date,
                    'scraped_at': current_time,
                    'source': 'MOF_DraftForum',
                    'status': 'active',  # 新增狀態欄位
                    'scraper_version': '2.0_enhanced'
                }
                
                # 生成唯一ID
                draft_law['unique_id'] = self.generate_unique_id(draft_law)
                
                draft_laws.append(draft_law)
            
            print(f"✅ 成功解析 {len(draft_laws)} 筆法規草案")
            return draft_laws
            
        except requests.exceptions.RequestException as e:
            print(f"❌ 網路請求失敗: {e}")
            print("🔄 可能的原因:")
            print("   • 網路連線問題")
            print("   • 目標網站暫時無法存取")
            print("   • 請求被阻擋")
            return []
        except Exception as e:
            print(f"❌ 解析過程發生錯誤: {e}")
            print("🔄 可能的原因:")
            print("   • 網站結構改變")
            print("   • 正則表達式需要調整")
            return []
    
    def _alternative_parsing(self, content):
        """
        備用解析方法
        
        Args:
            content (str): 網頁內容
            
        Returns:
            list: 法規草案清單
        """
        print("🔄 使用備用解析方法...")
        
        draft_laws = []
        lines = content.split('\n')
        current_time = datetime.now(self.tz_taipei).isoformat()
        
        sequence = 1
        for line in lines:
            line = line.strip()
            
            # 尋找包含日期和連結的行
            if '114.' in line and 'join.gov.tw' in line:
                print(f"📝 備用方法找到: {line[:50]}...")
                
                # 嘗試提取基本資訊
                draft_law = {
                    'sequence': sequence,
                    'title': line.strip(),
                    'scraped_at': current_time,
                    'source': 'MOF_DraftForum_Alternative',
                    'status': 'active',
                    'scraper_version': '2.0_alternative'
                }
                
                # 嘗試提取URL
                url_match = re.search(r'https://[^\s)]+', line)
                if url_match:
                    draft_law['url'] = url_match.group()
                
                # 生成唯一ID
                draft_law['unique_id'] = self.generate_unique_id(draft_law)
                
                draft_laws.append(draft_law)
                sequence += 1
                
                # 限制備用方法的結果數量
                if len(draft_laws) >= 10:
                    break
        
        print(f"✅ 備用方法找到 {len(draft_laws)} 筆資料")
        return draft_laws
    
    def load_history(self):
        """
        載入歷史記錄
        
        Returns:
            list: 歷史記錄清單
        """
        history_file = self.data_dir / "draft_law_history.json"
        
        if history_file.exists():
            try:
                with open(history_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)
                print(f"📚 載入歷史記錄: {len(history)} 筆")
                return history
            except Exception as e:
                print(f"⚠️ 載入歷史記錄失敗: {e}")
                return []
        else:
            print("📝 首次執行，無歷史記錄")
            return []
    
    def compare_and_update_smart(self, current_drafts):
        """
        智能比對和更新邏輯
        
        Args:
            current_drafts (list): 當前爬取的草案清單
            
        Returns:
            tuple: (new_items, updated_items, all_history, stats)
        """
        print("\n🧠 執行智能比對分析...")
        
        history = self.load_history()
        
        # 建立歷史資料的 unique_id 對應表
        history_dict = {item.get('unique_id'): item for item in history if item.get('unique_id')}
        current_dict = {item.get('unique_id'): item for item in current_drafts if item.get('unique_id')}
        
        print(f"📊 比對統計:")
        print(f"   • 當前網站草案: {len(current_drafts)} 筆")
        print(f"   • 歷史記錄草案: {len(history)} 筆")
        print(f"   • 歷史有效ID: {len(history_dict)} 個")
        
        # 1. 找出真正的新項目 (unique_id 不存在於歷史中)
        new_items = []
        for uid, draft in current_dict.items():
            if uid not in history_dict:
                new_items.append(draft)
                print(f"🆕 發現新草案: {draft.get('title', '')[:50]}...")
        
        # 2. 更新現有項目狀態 (如果有變化)
        updated_items = []
        for uid, current_draft in current_dict.items():
            if uid in history_dict:
                historical_draft = history_dict[uid]
                
                # 檢查是否有重要變化
                has_changes = False
                changes = []
                
                if current_draft.get('title') != historical_draft.get('title'):
                    has_changes = True
                    changes.append("標題")
                
                if current_draft.get('end_date') != historical_draft.get('end_date'):
                    has_changes = True
                    changes.append("終止日期")
                
                if current_draft.get('date') != historical_draft.get('date'):
                    has_changes = True
                    changes.append("公告日期")
                
                if has_changes:
                    # 更新 scraped_at 和變更記錄
                    current_draft['last_updated'] = datetime.now(self.tz_taipei).isoformat()
                    current_draft['changes'] = changes
                    updated_items.append(current_draft)
                    print(f"🔄 草案已更新: {current_draft.get('title', '')[:50]}... (變更: {', '.join(changes)})")
        
        # 3. 標記不再出現的項目為過期
        expired_count = 0
        current_uids = set(current_dict.keys())
        for uid, historical_draft in history_dict.items():
            if uid not in current_uids and historical_draft.get('status') == 'active':
                # 標記為過期但保留在歷史中
                historical_draft['status'] = 'expired'
                historical_draft['expired_at'] = datetime.now(self.tz_taipei).isoformat()
                expired_count += 1
                print(f"⏰ 草案已過期: {historical_draft.get('title', '')[:50]}...")
        
        # 4. 建立更新後的完整歷史記錄
        updated_history = []
        
        # 加入所有現有的活躍項目 (新的和更新的)
        for draft in current_drafts:
            # 如果是更新的項目，使用更新後的版本
            uid = draft.get('unique_id')
            updated_version = next((item for item in updated_items if item.get('unique_id') == uid), draft)
            updated_history.append(updated_version)
        
        # 加入歷史中的過期項目
        for uid, historical_draft in history_dict.items():
            if uid not in current_dict and historical_draft.get('status') == 'expired':
                updated_history.append(historical_draft)
        
        # 按日期排序 (最新的在前)
        updated_history.sort(key=lambda x: x.get('date', ''), reverse=True)
        
        # 儲存更新後的歷史
        self.save_history(updated_history)
        
        # 統計資訊
        stats = {
            'new_count': len(new_items),
            'updated_count': len(updated_items),
            'expired_count': expired_count,
            'active_count': len(current_drafts),
            'total_historical': len(updated_history)
        }
        
        print(f"\n📈 智能比對結果:")
        print(f"   🆕 新增: {stats['new_count']} 筆")
        print(f"   🔄 更新: {stats['updated_count']} 筆")
        print(f"   ⏰ 過期: {stats['expired_count']} 筆")
        print(f"   ✅ 當前活躍: {stats['active_count']} 筆")
        print(f"   📚 歷史總計: {stats['total_historical']} 筆")
        
        return new_items, updated_items, updated_history, stats
    
    def save_history(self, all_drafts):
        """
        儲存歷史記錄
        
        Args:
            all_drafts (list): 完整的草案清單
        """
        history_file = self.data_dir / "draft_law_history.json"
        
        try:
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(all_drafts, f, ensure_ascii=False, indent=2)
            print(f"✅ 歷史記錄已儲存: {history_file} ({len(all_drafts)} 筆)")
        except Exception as e:
            print(f"❌ 儲存歷史記錄失敗: {e}")
    
    def generate_comprehensive_report(self, new_items, updated_items, current_drafts, stats):
        """
        生成詳細報告
        
        Args:
            new_items (list): 新增項目
            updated_items (list): 更新項目
            current_drafts (list): 當前草案
            stats (dict): 統計資料
            
        Returns:
            dict: 詳細報告
        """
        print("\n📋 生成詳細報告...")
        
        report = {
            'execution_time': datetime.now(self.tz_taipei).strftime('%Y-%m-%d %H:%M:%S'),
            'source': 'MOF_DraftForum',
            'scraper_version': '2.0_enhanced',
            'target_url': self.base_url,
            'statistics': stats,
            'summary': {
                'has_new': len(new_items) > 0,
                'has_updates': len(updated_items) > 0,
                'total_changes': len(new_items) + len(updated_items),
                'execution_status': 'success'
            },
            'metadata': {
                'timezone': 'Asia/Taipei',
                'data_dir': str(self.data_dir),
                'files_generated': []
            }
        }
        
        # 儲存主報告
        report_file = self.data_dir / "draft_report.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        report['metadata']['files_generated'].append('draft_report.json')
        print(f"✅ 主報告已儲存: {report_file}")
        
        # 儲存新發現的草案
        if new_items:
            new_file = self.data_dir / "today_new_drafts.json"
            with open(new_file, 'w', encoding='utf-8') as f:
                json.dump(new_items, f, ensure_ascii=False, indent=2)
            report['metadata']['files_generated'].append('today_new_drafts.json')
            print(f"✅ 新增草案清單已儲存: {new_file} ({len(new_items)} 筆)")
        
        # 儲存更新的草案
        if updated_items:
            updated_file = self.data_dir / "today_updated_drafts.json"
            with open(updated_file, 'w', encoding='utf-8') as f:
                json.dump(updated_items, f, ensure_ascii=False, indent=2)
            report['metadata']['files_generated'].append('today_updated_drafts.json')
            print(f"✅ 更新草案清單已儲存: {updated_file} ({len(updated_items)} 筆)")
        
        # 儲存當前活躍草案
        if current_drafts:
            current_file = self.data_dir / "current_active_drafts.json"
            with open(current_file, 'w', encoding='utf-8') as f:
                json.dump(current_drafts, f, ensure_ascii=False, indent=2)
            report['metadata']['files_generated'].append('current_active_drafts.json')
            print(f"✅ 當前活躍草案已儲存: {current_file} ({len(current_drafts)} 筆)")
        
        return report
    
    def export_to_csv(self, drafts):
        """
        匯出為CSV格式
        
        Args:
            drafts (list): 草案清單
            
        Returns:
            Path: CSV檔案路徑
        """
        if not drafts:
            print("⚠️ 無資料可匯出為CSV")
            return None
            
        print(f"💾 匯出 {len(drafts)} 筆資料為CSV...")
        
        try:
            df = pd.DataFrame(drafts)
            
            # 重新排列欄位順序，確保重要資訊在前
            preferred_columns = [
                'unique_id', 'sequence', 'status', 'date', 'title', 
                'url', 'end_date', 'roc_date', 'roc_end_date',
                'scraped_at', 'source', 'scraper_version'
            ]
            
            # 只保留存在的欄位
            available_columns = [col for col in preferred_columns if col in df.columns]
            
            # 加入其他欄位
            other_columns = [col for col in df.columns if col not in available_columns]
            final_columns = available_columns + other_columns
            
            df = df[final_columns]
            
            # 生成檔案名稱
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            csv_file = self.data_dir / f'draft_laws_{timestamp}.csv'
            
            # 儲存CSV (使用UTF-8 BOM確保中文正確顯示)
            df.to_csv(csv_file, index=False, encoding='utf-8-sig')
            
            print(f"✅ CSV檔案已儲存: {csv_file}")
            print(f"📊 CSV包含欄位: {len(final_columns)} 個")
            print(f"📋 CSV包含記錄: {len(df)} 筆")
            
            return csv_file
            
        except Exception as e:
            print(f"❌ CSV匯出失敗: {e}")
            return None
    
    def print_summary(self, new_items, updated_items, stats):
        """
        列印執行摘要
        
        Args:
            new_items (list): 新增項目
            updated_items (list): 更新項目
            stats (dict): 統計資料
        """
        print("\n" + "="*60)
        print("📊 執行摘要")
        print("="*60)
        
        print(f"🕐 執行時間: {datetime.now(self.tz_taipei).strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🌏 時區: Asia/Taipei (UTC+8)")
        print(f"📡 來源: {self.base_url}")
        print()
        
        print("📈 統計資料:")
        print(f"   🆕 新增草案: {stats['new_count']} 筆")
        print(f"   🔄 更新草案: {stats['updated_count']} 筆")
        print(f"   ⏰ 過期草案: {stats['expired_count']} 筆")
        print(f"   ✅ 當前活躍: {stats['active_count']} 筆")
        print(f"   📚 歷史總計: {stats['total_historical']} 筆")
        print()
        
        # 顯示新增草案詳情
        if new_items:
            print("🆕 新增草案詳情:")
            for i, item in enumerate(new_items[:3], 1):  # 只顯示前3筆
                print(f"   {i}. {item.get('title', '無標題')[:60]}...")
                if item.get('end_date'):
                    print(f"      預告終止: {item.get('end_date')}")
            if len(new_items) > 3:
                print(f"   ...還有 {len(new_items) - 3} 筆新增草案")
            print()
        
        # 顯示更新草案詳情
        if updated_items:
            print("🔄 更新草案詳情:")
            for i, item in enumerate(updated_items[:3], 1):  # 只顯示前3筆
                print(f"   {i}. {item.get('title', '無標題')[:60]}...")
                if item.get('changes'):
                    print(f"      變更項目: {', '.join(item.get('changes'))}")
            if len(updated_items) > 3:
                print(f"   ...還有 {len(updated_items) - 3} 筆更新草案")
            print()
        
        total_changes = len(new_items) + len(updated_items)
        if total_changes > 0:
            print(f"🎉 發現 {total_changes} 項重要變化!")
        else:
            print("✨ 沒有發現新的變化，系統運作正常")
        
        print("="*60)

def main():
    """
    主程式入口
    """
    print("=" * 60)
    print("📜 改進版財政部法規草案爬蟲系統")
    print("🔗 目標網站: https://law-out.mof.gov.tw/DraftForum.aspx")
    print(f"🕐 執行時間: {datetime.now()}")
    print(f"🚀 版本: 2.0 Enhanced")
    print("=" * 60)
    
    try:
        # 建立爬蟲實例
        scraper = ImprovedDraftLawScraper()
        
        # 執行爬取
        print("\n🔍 階段一: 爬取法規草案")
        print("-" * 40)
        current_drafts = scraper.fetch_draft_laws()
        
        if not current_drafts:
            print("❌ 未能獲取任何法規草案資料")
            print("\n🔧 可能的解決方案:")
            print("   1. 檢查網路連線")
            print("   2. 確認目標網站可正常訪問")
            print("   3. 稍後重試")
            return False
        
        print(f"✅ 爬取階段完成，共獲得 {len(current_drafts)} 筆當前活躍草案")
        
        # 智能比對和更新
        print("\n🧠 階段二: 智能比對分析")
        print("-" * 40)
        new_items, updated_items, all_history, stats = scraper.compare_and_update_smart(current_drafts)
        
        # 生成報告
        print("\n📋 階段三: 生成詳細報告")
        print("-" * 40)
        report = scraper.generate_comprehensive_report(new_items, updated_items, current_drafts, stats)
        
        # 匯出資料
        print("\n💾 階段四: 匯出資料檔案")
        print("-" * 40)
        csv_file = scraper.export_to_csv(all_history)
        
        # 顯示最終摘要
        scraper.print_summary(new_items, updated_items, stats)
        
        # 檔案清單
        print("\n📁 生成的檔案:")
        for filename in report['metadata']['files_generated']:
            file_path = scraper.data_dir / filename
            if file_path.exists():
                size = file_path.stat().st_size
                print(f"   ✅ {filename} ({size} bytes)")
        
        if csv_file:
            print(f"   ✅ {csv_file.name} ({csv_file.stat().st_size} bytes)")
        
        print(f"\n🎯 執行成功完成！")
        print(f"📊 數據目錄: {scraper.data_dir}")
        
        return True
        
    except KeyboardInterrupt:
        print("\n⚠️ 用戶中斷執行")
        return False
    except Exception as e:
        print(f"\n❌ 執行過程發生未預期錯誤: {e}")
        print("\n🔧 建議:")
        print("   1. 檢查錯誤訊息")
        print("   2. 確認網路連線正常")
        print("   3. 如問題持續，請回報錯誤訊息")
        return False

if __name__ == "__main__":
    success = main()
    
    # 設定退出碼
    exit(0 if success else 1)
