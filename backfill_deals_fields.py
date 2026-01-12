"""一次性回填脚本：填充 deals 表的 canonical_name, one_liner, evidence_urls 字段

使用方法：
    python backfill_deals_fields.py

说明：
    - 只更新 canonical_name/one_liner/evidence_urls 为空的记录
    - canonical_name = title（或清洗后的 title）
    - one_liner = left(description, 120)
    - evidence_urls = array[url]
"""

# 首先加载环境变量（在任何其他导入或读取环境变量之前）
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(dotenv_path=Path(__file__).parent / ".env", override=False)

import os
import re
import hashlib
from datetime import datetime
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
from db.supabase_db import get_supabase_client


def clean_canonical_name(title: str) -> str:
    """清洗标题，提取规范名称（去掉网站后缀/分隔符后半段）"""
    if not title:
        return ""
    
    # 常见分隔符模式：去除 " - Company", " | TechCrunch", " - The Verge" 等
    patterns = [
        r'\s*[-–—]\s*[^|]+$',  # 匹配 " - XXX" 到末尾
        r'\s*\|\s*[^|]+$',      # 匹配 " | XXX" 到末尾
        r'\s*::\s*[^:]+$',      # 匹配 " :: XXX" 到末尾
    ]
    
    cleaned = title
    for pattern in patterns:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
    
    # 去除首尾空格
    cleaned = cleaned.strip()
    
    # 如果清洗后为空，返回原始标题
    return cleaned if cleaned else title


def normalize_url(u: str) -> str:
    """规范化 URL：去掉追踪参数，统一格式"""
    if not u:
        return ""
    
    u = u.strip()
    if not u:
        return ""
    
    # 无 scheme 时补 https://
    if not u.startswith(('http://', 'https://')):
        u = 'https://' + u
    
    try:
        parsed = urlparse(u)
        
        # scheme 强制为 https
        scheme = 'https'
        
        # netloc 小写，去掉前缀 www.
        netloc = parsed.netloc.lower()
        if netloc.startswith('www.'):
            netloc = netloc[4:]
        
        # path 去掉末尾 /（根路径除外）
        path = parsed.path
        if path != '/' and path.endswith('/'):
            path = path[:-1]
        
        # query 参数过滤
        query_dict = parse_qs(parsed.query, keep_blank_values=False)
        
        # 过滤追踪参数
        tracking_params = [
            'ref', 'ref_src', 'fbclid', 'gclid', 'igshid', 
            'mc_cid', 'mc_eid', 'spm', 'source', 'mkt_tok'
        ]
        filtered_query = {}
        for key, values in query_dict.items():
            if key.startswith('utm_'):
                continue
            if key.lower() in [p.lower() for p in tracking_params]:
                continue
            filtered_query[key] = values[0] if values else ''
        
        # 按 key 排序后重组
        if filtered_query:
            sorted_params = sorted(filtered_query.items())
            query = urlencode(sorted_params)
        else:
            query = ''
        
        # 丢弃 fragment
        fragment = ''
        
        normalized = urlunparse((scheme, netloc, path, parsed.params, query, fragment))
        return normalized
        
    except Exception as e:
        print(f"⚠️ URL 规范化失败 ({u[:50]}...): {e}")
        return u.strip()


def get_hostname(url: str) -> str:
    """从 URL 提取主机名"""
    try:
        parsed = urlparse(url)
        return parsed.netloc or ""
    except:
        return ""


def compute_dedupe_key(url: str, hostname: str, canonical_name: str, title: str) -> str:
    """计算 dedupe_key（以规范化 URL 为主）"""
    normalized_url = normalize_url(url)
    if normalized_url:
        url_hash = hashlib.sha1(normalized_url.encode()).hexdigest()
        return f"url:{url_hash}"
    
    key_str = f"{hostname}|{canonical_name or title}".lower().strip()
    key_hash = hashlib.sha1(key_str.encode()).hexdigest()
    return f"ht:{key_hash}"


def generate_one_liner(description: str) -> str:
    """从 description 生成 one_liner（去换行，截断到120字）"""
    if not description:
        return ""
    
    # 去除换行和多余空格
    cleaned = " ".join(description.split())
    
    # 截断到120字
    if len(cleaned) > 120:
        # 尽量在标点符号处截断
        truncated = cleaned[:120]
        for punct in ['.', '。', '!', '！', '?', '？', ';', '；']:
            last_punct = truncated.rfind(punct)
            if last_punct > 80:  # 如果标点位置在80字之后
                return truncated[:last_punct + 1]
        return truncated[:117] + "..."
    else:
        return cleaned


def main():
    """主函数：回填 deals 表的三个字段"""
    print("=" * 60)
    print("开始回填 deals 表的 canonical_name, one_liner, evidence_urls 字段")
    print("=" * 60)
    
    # 获取 Supabase 客户端（使用 service role key 以便写入）
    client = get_supabase_client(use_service_role=True)
    if not client:
        print("❌ 无法创建 Supabase 客户端（请检查环境变量）")
        return 1
    
    try:
        # 读取所有 deals（只读取需要的字段）
        print("\n📖 读取 deals 数据...")
        response = client.table("deals")\
            .select("id,title,description,url,canonical_name,one_liner,evidence_urls,hostname,dedupe_key")\
            .execute()
        
        all_deals = response.data if hasattr(response, 'data') else []
        print(f"    ✅ 共读取 {len(all_deals)} 条记录")
        
        # 筛选需要更新的记录（url/evidence_urls/dedupe_key 需要规范化或为空）
        deals_to_update = []
        for deal in all_deals:
            canonical_name = deal.get("canonical_name", "").strip() if deal.get("canonical_name") else ""
            one_liner = deal.get("one_liner", "").strip() if deal.get("one_liner") else ""
            evidence_urls = deal.get("evidence_urls", [])
            evidence_urls = evidence_urls if isinstance(evidence_urls, list) and len(evidence_urls) > 0 else []
            url = deal.get("url", "")
            dedupe_key = deal.get("dedupe_key", "").strip() if deal.get("dedupe_key") else ""
            
            # 检查是否需要更新（三个字段为空，或 url 包含追踪参数，或 dedupe_key 为空）
            url_needs_normalize = url and any(param in url for param in ['utm_', 'ref=', 'fbclid=', 'gclid='])
            evidence_needs_normalize = evidence_urls and any(any(param in str(u) for param in ['utm_', 'ref=', 'fbclid=']) for u in evidence_urls)
            
            if not canonical_name or not one_liner or not evidence_urls or url_needs_normalize or evidence_needs_normalize or not dedupe_key:
                deals_to_update.append(deal)
        
        print(f"    📝 需要更新的记录数: {len(deals_to_update)}")
        
        if not deals_to_update:
            print("\n✅ 所有记录都已规范化，无需更新")
            return 0
        
        # 批量更新
        updated_count = 0
        failed_count = 0
        url_updated_count = 0
        evidence_updated_count = 0
        dedupe_key_updated_count = 0
        
        print(f"\n🔄 开始批量更新...")
        for idx, deal in enumerate(deals_to_update, 1):
            deal_id = deal.get("id")
            title = deal.get("title", "")
            description = deal.get("description", "")
            url = deal.get("url", "")
            
            if not deal_id:
                print(f"    ⚠️ 跳过无 ID 的记录: {title[:50]}")
                failed_count += 1
                continue
            
            # 规范化 URL
            normalized_url = normalize_url(url) if url else ""
            
            # 规范化 evidence_urls
            existing_evidence_urls = deal.get("evidence_urls", [])
            if isinstance(existing_evidence_urls, list) and len(existing_evidence_urls) > 0:
                normalized_evidence_urls = []
                seen = set()
                for u in existing_evidence_urls:
                    normalized = normalize_url(str(u))
                    if normalized and normalized not in seen:
                        normalized_evidence_urls.append(normalized)
                        seen.add(normalized)
            else:
                normalized_evidence_urls = [normalized_url] if normalized_url else []
            
            # 生成三个字段（如果为空）
            # canonical_name: 优先用清洗后的 title
            if not deal.get("canonical_name") or not deal.get("canonical_name", "").strip():
                canonical_name = clean_canonical_name(title) if title else ""
            else:
                canonical_name = deal.get("canonical_name")
            
            # one_liner: 从 description 截断
            if not deal.get("one_liner") or not deal.get("one_liner", "").strip():
                one_liner = generate_one_liner(description) if description else ""
            else:
                one_liner = deal.get("one_liner")
            
            # 计算 dedupe_key
            hostname = deal.get("hostname", "") or get_hostname(url)
            new_dedupe_key = compute_dedupe_key(url, hostname, canonical_name, title)
            
            # 构建更新数据（总是更新 url, evidence_urls, dedupe_key 以确保规范化）
            update_data = {}
            
            # 总是更新 url（规范化）
            if normalized_url:
                update_data["url"] = normalized_url
                if normalized_url != url:
                    url_updated_count += 1
            
            # 总是更新 evidence_urls（规范化）
            update_data["evidence_urls"] = normalized_evidence_urls
            if normalized_evidence_urls != existing_evidence_urls:
                evidence_updated_count += 1
            
            # 总是更新 dedupe_key
            update_data["dedupe_key"] = new_dedupe_key
            if new_dedupe_key != deal.get("dedupe_key", ""):
                dedupe_key_updated_count += 1
            
            # 更新三个字段（如果为空）
            if not deal.get("canonical_name") or not deal.get("canonical_name", "").strip():
                update_data["canonical_name"] = canonical_name
            if not deal.get("one_liner") or not deal.get("one_liner", "").strip():
                update_data["one_liner"] = one_liner
            
            # 添加 updated_at
            update_data["updated_at"] = datetime.utcnow().isoformat()
            
            try:
                # 更新记录
                client.table("deals")\
                    .update(update_data)\
                    .eq("id", deal_id)\
                    .execute()
                
                updated_count += 1
                if idx % 10 == 0:
                    print(f"    ✅ 已更新 {idx}/{len(deals_to_update)} 条记录...")
            except Exception as e:
                print(f"    ❌ 更新失败 (id: {deal_id}, title: {title[:50]}): {e}")
                failed_count += 1
        
        print(f"\n📊 回填完成统计:")
        print(f"  - 总记录数: {len(all_deals)}")
        print(f"  - 需要更新: {len(deals_to_update)}")
        print(f"  - 成功更新: {updated_count}")
        print(f"  - 更新失败: {failed_count}")
        print(f"  - URL 规范化: {url_updated_count} 条")
        print(f"  - evidence_urls 规范化: {evidence_updated_count} 条")
        print(f"  - dedupe_key 生成/更新: {dedupe_key_updated_count} 条")
        
        if failed_count > 0:
            print(f"\n⚠️ 有 {failed_count} 条记录更新失败，请检查错误日志")
            return 1
        else:
            print(f"\n✅ 所有记录回填成功！")
            return 0
            
    except Exception as e:
        print(f"\n❌ 回填过程出错: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
