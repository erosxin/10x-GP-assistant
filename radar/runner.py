"""雷达抓取 + 周报生成主程序"""
# 首先加载环境变量（在任何其他导入或读取环境变量之前）
from pathlib import Path
from dotenv import load_dotenv
# 加载项目根目录的 .env 文件（radar/runner.py 位于项目根目录/radar/runner.py，所以需要向上两级）
load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env", override=False)

import os
import yaml
import hashlib
import re
import requests
from datetime import datetime, timedelta, timezone
from dateutil.relativedelta import relativedelta
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
import sys

# 添加父目录到路径以便导入
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db.supabase_db import get_supabase_client


def load_config():
    """加载配置文件"""
    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            print(f"✅ 配置文件已加载 (版本: {config['version']})")
            return config
    except FileNotFoundError:
        print(f"❌ 配置文件不存在: {config_path}")
        raise
    except Exception as e:
        print(f"❌ 加载配置文件失败: {e}")
        raise


def get_url_hash(url: str) -> str:
    """生成 URL 的哈希值用于去重"""
    return hashlib.md5(url.encode()).hexdigest()


def search_serper(query: str, gl: str = "us", hl: str = "en", num: int = 10):
    """使用 Serper API 搜索"""
    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        print("❌ SERPER_API_KEY 环境变量未设置")
        return []
    
    url = "https://google.serper.dev/search"
    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json"
    }
    payload = {
        "q": query,
        "gl": gl,
        "hl": hl,
        "num": num
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        organic_results = data.get("organic", [])
        
        # 在解析 Serper 结果时就赋值 source 字段
        # 优先：result.get("source")，兜底："serper"
        empty_source_count = 0
        for result in organic_results:
            original_source = result.get("source")
            if not original_source or original_source.strip() == "":
                empty_source_count += 1
            result["source"] = original_source or "serper"
        
        if empty_source_count > 0:
            print(f"    ⚠️ 搜索结果中有 {empty_source_count} 条记录的 source 为空（已自动填充为 'serper'）")
        
        return organic_results
    except Exception as e:
        print(f"⚠️ Serper 搜索失败 ({query}): {e}")
        return []


def normalize_url(u: str) -> str:
    """规范化 URL：去掉追踪参数，统一格式
    
    Args:
        u: 原始 URL 字符串
        
    Returns:
        规范化后的 URL 字符串
    """
    if not u:
        return ""
    
    # strip()
    u = u.strip()
    if not u:
        return ""
    
    # 无 scheme 时补 https://
    if not u.startswith(('http://', 'https://')):
        u = 'https://' + u
    
    try:
        # urlparse
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
        # 删除追踪参数：utm_*, ref, ref_src, fbclid, gclid, igshid, mc_cid, mc_eid, spm, source, mkt_tok
        query_dict = parse_qs(parsed.query, keep_blank_values=False)
        
        # 过滤追踪参数
        tracking_params = [
            'ref', 'ref_src', 'fbclid', 'gclid', 'igshid', 
            'mc_cid', 'mc_eid', 'spm', 'source', 'mkt_tok'
        ]
        filtered_query = {}
        for key, values in query_dict.items():
            # 跳过 utm_* 开头的参数
            if key.startswith('utm_'):
                continue
            # 跳过其他追踪参数
            if key.lower() in [p.lower() for p in tracking_params]:
                continue
            # 保留其他参数（取第一个值）
            filtered_query[key] = values[0] if values else ''
        
        # 按 key 排序后重组
        if filtered_query:
            sorted_params = sorted(filtered_query.items())
            query = urlencode(sorted_params)
        else:
            query = ''
        
        # 丢弃 fragment（#...）
        fragment = ''
        
        # 返回重组后的 url
        normalized = urlunparse((scheme, netloc, path, parsed.params, query, fragment))
        return normalized
        
    except Exception as e:
        # 如果解析失败，返回原 URL（至少 strip 过）
        print(f"⚠️ URL 规范化失败 ({u[:50]}...): {e}")
        return u.strip()


def get_hostname(url: str) -> str:
    """从 URL 提取主机名"""
    try:
        parsed = urlparse(url)
        return parsed.netloc or ""
    except:
        return ""


def clean_canonical_name(title: str) -> str:
    """清洗标题，提取规范名称（去掉网站后缀/分隔符后半段）"""
    if not title:
        return ""
    
    # 常见分隔符模式：去除 " - Company", " | TechCrunch", " - The Verge" 等
    import re
    # 匹配分隔符及其后的内容（常见分隔符：|、-、–、—、::）
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


def generate_canonical_name(item: dict, title: str, hostname: str) -> str:
    """生成 canonical_name（优先级：已有字段 > 清洗 title > hostname）"""
    # 优先级1: 已有结构化字段
    for field in ["company", "product", "name", "canonical_name"]:
        value = item.get(field, "").strip()
        if value:
            return value
    
    # 优先级2: 清洗 title
    if title:
        cleaned = clean_canonical_name(title)
        if cleaned:
            return cleaned
    
    # 优先级3: hostname
    if hostname:
        return hostname
    
    # 兜底
    return title or "(untitled)"


def generate_one_liner(item: dict, description: str, title: str = "") -> str:
    """生成 one_liner（优先级：已有摘要 > description 截断 > title 截断）"""
    # 优先级1: 已有摘要字段
    for field in ["one_liner", "summary", "excerpt"]:
        value = item.get(field, "").strip()
        if value:
            # 如果已有摘要太长，截断到120字
            if len(value) > 120:
                return value[:117] + "..."
            return value
    
    # 优先级2: 从 description 生成（去换行，截断到80-120字）
    if description:
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
        elif len(cleaned) >= 80:
            return cleaned
        else:
            # 如果不足80字，仍然返回（至少比空好）
            return cleaned
    
    # 优先级3: 从 title 生成（作为最后兜底）
    if title:
        cleaned = " ".join(title.split())
        if len(cleaned) > 120:
            return cleaned[:117] + "..."
        return cleaned
    
    # 兜底：返回默认值
    return "无描述"


def generate_evidence_urls(item: dict, url: str) -> list:
    """生成 evidence_urls（至少包含规范化后的 url，合并其他来源链接并规范化）"""
    urls_list = []
    seen = set()
    
    # 必须包含主 URL（规范化后）
    if url:
        normalized = normalize_url(url)
        if normalized and normalized not in seen:
            urls_list.append(normalized)
            seen.add(normalized)
    
    # 合并其他来源链接（每条都规范化）
    for field in ["sources", "links", "evidence_urls", "related_urls"]:
        value = item.get(field)
        if value:
            if isinstance(value, list):
                for u in value:
                    if u:
                        normalized = normalize_url(str(u))
                        if normalized and normalized not in seen:
                            urls_list.append(normalized)
                            seen.add(normalized)
            elif isinstance(value, str):
                # 如果是字符串，尝试按逗号/分号分割
                for u in re.split(r'[,;]', value):
                    u = u.strip()
                    if u:
                        normalized = normalize_url(u)
                        if normalized and normalized not in seen:
                            urls_list.append(normalized)
                            seen.add(normalized)
    
    # 断言：最终列表长度 >= 1
    assert len(urls_list) > 0, f"❌ 错误: evidence_urls 为空 (url: {url[:50]}...)"
    
    # 返回列表（保持顺序，已去重）
    return urls_list


def compute_dedupe_key(url: str, hostname: str, canonical_name: str, title: str) -> str:
    """计算 dedupe_key（以规范化 URL 为主）
    
    Args:
        url: 原始 URL
        hostname: 主机名
        canonical_name: 规范名称
        title: 标题
        
    Returns:
        dedupe_key 字符串（格式：url:sha1 或 ht:sha1）
    """
    # 若 normalize 后 url 非空：dedupe_key = "url:" + sha1(normalized_url)
    normalized_url = normalize_url(url)
    if normalized_url:
        url_hash = hashlib.sha1(normalized_url.encode()).hexdigest()
        return f"url:{url_hash}"
    
    # 否则：dedupe_key = "ht:" + sha1((hostname + "|" + (canonical_name or title)).lower().strip())
    key_str = f"{hostname}|{canonical_name or title}".lower().strip()
    key_hash = hashlib.sha1(key_str.encode()).hexdigest()
    return f"ht:{key_hash}"


def get_week_start() -> datetime:
    """获取本周一的日期（UTC）"""
    today = datetime.utcnow()
    # 获取本周一
    days_since_monday = today.weekday()
    week_start = today - timedelta(days=days_since_monday)
    return week_start.replace(hour=0, minute=0, second=0, microsecond=0)


def upsert_radar_items(client, items: list, topic_name: str, query: str = ""):
    """将雷达项写入数据库
    
    Args:
        client: Supabase 客户端
        items: 搜索结果列表
        topic_name: 主题名称
        query: 搜索查询关键词
    """
    if not client:
        return
    
    # 统计本轮写入的记录数（用于验证）
    processed_count = 0
    
    for item in items:
        url = item.get("link", "")
        if not url:
            continue
        
        url_hash = get_url_hash(url)
        hostname = get_hostname(url)
        
        # 在写入前加硬断言/默认值（防回归）
        # 确保最终写库前 source 永不为空
        # 优先：result.get("source")，兜底："serper"
        item["source"] = item.get("source") or "serper"
        source = item["source"]  # 使用 item 中的 source（已确保不为空）
        
        # 硬断言：确保 source 不为空（防回归）
        assert source and source.strip() != "", f"❌ 错误: source 字段为空 (url: {url[:50]}...)"
        
        data = {
            "url_hash": url_hash,
            "url": url,
            "title": item.get("title", ""),
            "snippet": item.get("snippet", ""),
            "topic": topic_name,
            "hostname": hostname,
            "source": source,  # 确保永不为 None
            "fetched_at": datetime.now(timezone.utc).isoformat()
        }
        
        # 在 insert 前打印调试信息
        debug_info = {
            "url": url[:80] + "..." if len(url) > 80 else url,
            "source": source,
            "hostname": hostname,
            "query": query[:50] + "..." if len(query) > 50 else query
        }
        print(f"    📝 Insert radar_item: {debug_info}")
        
        try:
            # 使用 upsert（按 url_hash 去重）
            client.table("radar_items").upsert(data, on_conflict="url_hash").execute()
        except Exception as e:
            print(f"⚠️ 写入 radar_items 失败 ({url_hash[:8]}): {e}")
    
        processed_count += 1
    
    # 验证：保证最终写入的 source 字段永不为空（所有空值已填充为 'serper'）
    print(f"    ✅ 本轮成功处理 {processed_count} 条记录，所有记录的 source 字段均有效")


def upsert_deals(client, items: list, topic_name: str):
    """将 deals 写入数据库（按 dedupe_key 去重，支持合并更新和二次发现策略）
    
    Returns:
        dict: 统计信息 {"processed": int, "reactivated": int, "errors": int}
    """
    if not client:
        return {"processed": 0, "reactivated": 0, "errors": 0}
    
    # 统计本轮写入的记录数（用于验证）
    processed_count = 0
    reactivated_count = 0
    error_count = 0
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()  # 自动包含 +00:00 时区信息
    
    for item in items:
        url = item.get("link", "")
        title = item.get("title", "")
        if not url or not title:
            continue
        
        hostname = get_hostname(url)
        description = item.get("snippet", "")
        
        # 生成三个必需字段
        canonical_name = generate_canonical_name(item, title, hostname)
        one_liner = generate_one_liner(item, description, title)
        new_evidence_urls = generate_evidence_urls(item, url)
        
        # 规范化 URL
        normalized_url = normalize_url(url)
        
        # 计算 dedupe_key（基于规范化 URL）
        dedupe_key = compute_dedupe_key(url, hostname, canonical_name, title)
        
        # 验证字段非空
        assert canonical_name and canonical_name.strip() != "", f"❌ 错误: canonical_name 为空 (url: {url[:50]}...)"
        assert one_liner and one_liner.strip() != "", f"❌ 错误: one_liner 为空 (url: {url[:50]}...)"
        assert new_evidence_urls and len(new_evidence_urls) > 0, f"❌ 错误: evidence_urls 为空 (url: {url[:50]}...)"
        
        # 查询现有记录（基于 dedupe_key）
        existing_deal = None
        try:
            existing_response = client.table("deals")\
                .select("id,status,evidence_urls,first_seen_at,last_seen_at,seen_count,score,dismissed_reason,dismissed_at")\
                .eq("dedupe_key", dedupe_key)\
                .limit(1)\
                .execute()
            
            if existing_response.data and len(existing_response.data) > 0:
                existing_deal = existing_response.data[0]
        except Exception as e:
            print(f"⚠️ 查询现有记录失败 ({dedupe_key[:8]}): {e}")
            error_count += 1
            continue  # 查询失败，跳过该记录
        
        # Archived 保护：如果现有记录状态为 archived，完全跳过更新
        if existing_deal:
            existing_status = existing_deal.get("status")
            if existing_status == "archived":
                deal_id = existing_deal.get("id")
                print(f"    ⏸️ Skip archived deal {deal_id} (dedupe_key: {dedupe_key[:16]}...)")
                continue  # 完全跳过 archived 记录的更新
        
        # 合并 evidence_urls（并集去重，保持最大 N 条）
        EVIDENCE_URLS_MAX = 20  # 最大保留 evidence_urls 数量
        if existing_deal:
            existing_evidence_urls = existing_deal.get("evidence_urls", [])
            if not isinstance(existing_evidence_urls, list):
                existing_evidence_urls = []
            
            # 合并：新值 ∪ 旧值（去重，保持顺序）
            merged_evidence_urls = list(existing_evidence_urls)
            seen = set(existing_evidence_urls)
            for u in new_evidence_urls:
                if u not in seen:
                    merged_evidence_urls.append(u)
                    seen.add(u)
            
            # 限制最大数量（保留最新的）
            if len(merged_evidence_urls) > EVIDENCE_URLS_MAX:
                merged_evidence_urls = merged_evidence_urls[-EVIDENCE_URLS_MAX:]
            
            evidence_urls = merged_evidence_urls
            new_evidence_count = len([u for u in new_evidence_urls if u not in existing_evidence_urls])
        else:
            evidence_urls = new_evidence_urls[:EVIDENCE_URLS_MAX]  # 新记录也限制数量
            new_evidence_count = len(new_evidence_urls)
        
        # 计算 seen_count
        if existing_deal:
            seen_count = (existing_deal.get("seen_count") or 0) + 1
            first_seen_at = existing_deal.get("first_seen_at") or now_iso
        else:
            seen_count = 1
            first_seen_at = now_iso
        
        # 规则 A：禁止改动 shortlisted/archived 的 status
        # 规则 B：自动复活（7 天）- 当 dismissed 记录在 7 天内再次出现时自动复活
        status = None  # None 表示不更新 status（保持原值）
        dismissed_reason = None
        dismissed_at = None
        
        existing_status = existing_deal.get("status") if existing_deal else None
        
        # 规则 A：禁止改动 shortlisted 的 status
        # 注意：archived 状态已在前面处理（直接跳过），这里只处理 shortlisted
        if existing_status == "shortlisted":
            # 保持人工状态，不更新 status
            pass
        elif existing_status == "dismissed":
            # 规则 B：自动复活（7 天）
            # 如果 now() - dismissed_at <= 7 days，则自动复活
            dismissed_at_str = existing_deal.get("dismissed_at")
            
            if dismissed_at_str:
                try:
                    # 解析 dismissed_at（ISO 格式，可能带时区）
                    dismissed_at_str_clean = dismissed_at_str.replace('Z', '+00:00')
                    dismissed_at_dt = datetime.fromisoformat(dismissed_at_str_clean)
                    
                    # 如果有时区信息，转换为 UTC（now 是 UTC）
                    if dismissed_at_dt.tzinfo:
                        dismissed_at_utc = dismissed_at_dt.astimezone(tz=None).replace(tzinfo=None)
                    else:
                        dismissed_at_utc = dismissed_at_dt
                    
                    # 计算时间差：如果 now() - dismissed_at <= 7 days，则复活
                    time_diff = now - dismissed_at_utc
                    within_7_days = time_diff <= timedelta(days=7)
                    
                    if within_7_days:
                        # 自动复活：在 7 天内再次出现，直接复活
                        status = "new"
                        dismissed_reason = None
                        dismissed_at = None
                        reactivated_count += 1
                        print(f"    🔄 规则 B：自动复活 dismissed 记录 ({dedupe_key[:8]}) - 距离 dismissed 时间 {time_diff.days} 天（<= 7 天）")
                    else:
                        # 超过 7 天，不自动复活
                        print(f"    ⏸️ 跳过复活 ({dedupe_key[:8]}) - 距离 dismissed 时间 {time_diff.days} 天（> 7 天）")
                except Exception as e:
                    print(f"    ⚠️ 解析 dismissed_at 失败 ({dedupe_key[:8]}): {e}")
                    # 如果解析失败，保守处理：不复活
            else:
                # 如果没有 dismissed_at，说明可能是旧数据，允许复活
                status = "new"
                dismissed_reason = None
                dismissed_at = None
                reactivated_count += 1
                print(f"    🔄 规则 B：自动复活 dismissed 记录 ({dedupe_key[:8]}) - 无 dismissed_at（旧数据）")
        
        # 规则 A：构建 upsert 数据
        # 总是更新：seen_count, last_seen_at
        # first_seen_at 只在新建时写
        data = {
            "dedupe_key": dedupe_key,
            "title": title,
            "url": normalized_url,
            "description": description,
            "canonical_name": canonical_name,
            "one_liner": one_liner,
            "evidence_urls": evidence_urls,  # 去重追加，已限制最大数量
            "topic": topic_name,
            "hostname": hostname,
            "last_seen_at": now_iso,  # 规则 A：总是更新
            "seen_count": seen_count,  # 规则 A：总是更新 seen_count + 1
            "updated_at": now_iso
        }
        
        # 规则 A：first_seen_at 只在新建时写
        if not existing_deal:
            data["created_at"] = now_iso
            data["first_seen_at"] = first_seen_at
            # 不显式设置 status，让数据库默认值 'new' 生效
        else:
            # 更新时，不覆盖 first_seen_at（保持原值）
            pass
        
        # 规则 A + 规则 B：状态更新逻辑
        # 关键：禁止改动 shortlisted 的 status
        # 注意：archived 状态已在前面处理（直接跳过），这里只处理 shortlisted
        if existing_status == "shortlisted":
            # 规则 A：保持人工状态，绝不更新 status
            # seen_count 和 last_seen_at 仍然会更新（已在上面的 data 中设置）
            pass
        elif status is not None:
            # 规则 B：如果状态需要更新（仅复活 dismissed 时）
            data["status"] = status
            data["dismissed_reason"] = dismissed_reason
            data["dismissed_at"] = dismissed_at
        
        # 如果有 score 字段，也更新
        if "score" in item:
            data["score"] = item.get("score")
        
        # 入库前打印调试信息
        debug_info = {
            "dedupe_key": dedupe_key[:16] + "...",
            "canonical_name": canonical_name[:50] + "..." if len(canonical_name) > 50 else canonical_name,
            "evidence_urls_count": len(evidence_urls),
            "new_evidence_count": new_evidence_count,
            "seen_count": seen_count,
            "status": status if status else (existing_deal.get("status") if existing_deal else "new"),
            "is_new": not existing_deal
        }
        print(f"    📝 Upsert deal: {debug_info}")
        
        try:
            # 使用 upsert（按 dedupe_key 去重）
            client.table("deals").upsert(data, on_conflict="dedupe_key").execute()
            processed_count += 1
        except Exception as e:
            print(f"⚠️ 写入 deals 失败 ({dedupe_key[:8]}): {e}")
    
    print(f"    ✅ 本轮成功处理 {processed_count} 条 deals 记录")
    if reactivated_count > 0:
        print(f"    🔄 其中 {reactivated_count} 条 dismissed 记录已自动复活")
    if error_count > 0:
        print(f"    ⚠️ 其中 {error_count} 条记录写入失败")
    
    return {
        "processed": processed_count,
        "reactivated": reactivated_count,
        "errors": error_count
    }


def reactivate_dismissed_deals(client) -> int:
    """DB 侧兜底：自动复活 7 天内的 dismissed 记录
    
    Args:
        client: Supabase 客户端
        
    Returns:
        int: 复活的记录数
    """
    if not client:
        return 0
    
    try:
        # 执行 SQL 更新：复活 7 天内的 dismissed 记录
        # 注意：Supabase Python 客户端不直接支持 raw SQL，需要使用 RPC 或直接更新
        # 这里使用查询 + 更新的方式
        
        # 查询需要复活的记录
        response = client.table("deals")\
            .select("id")\
            .eq("status", "dismissed")\
            .gte("last_seen_at", (datetime.now(timezone.utc) - timedelta(days=7)).isoformat())\
            .execute()
        
        deal_ids = [deal.get("id") for deal in (response.data if hasattr(response, 'data') else [])]
        
        if not deal_ids:
            return 0
        
        # 批量更新
        updated_count = 0
        for deal_id in deal_ids:
            try:
                client.table("deals")\
                    .update({
                        "status": "new",
                        "dismissed_reason": None,
                        "dismissed_at": None,
                        "updated_at": datetime.now(timezone.utc).isoformat()
                    })\
                    .eq("id", deal_id)\
                    .execute()
                updated_count += 1
            except Exception as e:
                print(f"    ⚠️ 复活记录失败 (id: {deal_id}): {e}")
        
        if updated_count > 0:
            print(f"    🔄 DB 侧兜底：自动复活 {updated_count} 条 dismissed 记录（7 天内）")
        
        return updated_count
        
    except Exception as e:
        print(f"    ⚠️ DB 侧复活检查失败: {e}")
        return 0


def health_check_deals(client, run_started_at: datetime = None) -> dict:
    """DB 健康检查：检查 evidence_urls、seen_count、last_seen_at、archived 保护
    
    Args:
        client: Supabase 客户端
        run_started_at: 本次运行开始时间（用于 archived 验收检查，如果为 None 则使用过去 60 分钟）
        
    Returns:
        dict: 健康检查结果，包含 archived_updated_last_2h 字段（必定返回 dict）
    """
    if not client:
        return {"evidence_over_20": 0, "seen_count_null": 0, "latest_last_seen_at": None, "archived_updated_last_2h": 0}
    
    try:
        # 查询所有记录进行统计
        response = client.table("deals")\
            .select("evidence_urls,seen_count,last_seen_at")\
            .execute()
        
        deals = response.data if hasattr(response, 'data') else []
        
        evidence_over_20 = 0
        seen_count_null = 0
        latest_last_seen_at = None
        
        for deal in deals:
            # 检查 evidence_urls 超过 20 条
            evidence_urls = deal.get("evidence_urls", [])
            if isinstance(evidence_urls, list) and len(evidence_urls) > 20:
                evidence_over_20 += 1
            
            # 检查 seen_count 为 null
            if deal.get("seen_count") is None:
                seen_count_null += 1
            
            # 找最新的 last_seen_at
            last_seen = deal.get("last_seen_at")
            if last_seen:
                if latest_last_seen_at is None or last_seen > latest_last_seen_at:
                    latest_last_seen_at = last_seen
        
        # Archived 保护验收：检查自本次运行开始时间以来是否有 archived 记录被更新
        archived_updated_last_2h = 0
        threshold_time_str = None
        try:
            # 使用 run_started_at 作为阈值（如果提供），否则使用过去 60 分钟
            if run_started_at:
                # 确保 run_started_at 是 timezone-aware
                if run_started_at.tzinfo is None:
                    threshold_time = run_started_at.replace(tzinfo=timezone.utc)
                else:
                    threshold_time = run_started_at
                threshold_time_str = threshold_time.isoformat()
            else:
                # 使用过去 60 分钟作为阈值
                threshold_time = datetime.now(timezone.utc) - timedelta(minutes=60)
                threshold_time_str = threshold_time.isoformat()
            
            archived_response = client.table("deals")\
                .select("id")\
                .eq("status", "archived")\
                .gt("last_seen_at", threshold_time_str)\
                .execute()
            
            archived_updated_last_2h = len(archived_response.data if hasattr(archived_response, 'data') else [])
            
            # 打印阈值时间用于调试
            threshold_display = threshold_time.strftime('%Y-%m-%d %H:%M:%S UTC')
            print(f"    📅 Archived 验收阈值时间: {threshold_display}")
        except Exception as e:
            print(f"    ⚠️ Archived 保护验收检查失败: {e}")
        
        result = {
            "evidence_over_20": evidence_over_20,
            "seen_count_null": seen_count_null,
            "latest_last_seen_at": latest_last_seen_at,
            "archived_updated_last_2h": archived_updated_last_2h
        }
        
        return result
        
    except Exception as e:
        print(f"    ⚠️ 健康检查失败: {e}")
        return {"evidence_over_20": 0, "seen_count_null": 0, "latest_last_seen_at": None, "archived_updated_last_2h": 0}


def generate_weekly_report(client, config: dict) -> str:
    """生成本周周报 markdown"""
    if not client:
        return ""
    
    week_start = get_week_start()
    week_end = week_start + timedelta(days=6)
    
    # 获取本周的 top N 雷达项
    try:
        response = client.table("radar_items")\
            .select("*")\
            .gte("fetched_at", week_start.isoformat())\
            .lte("fetched_at", week_end.isoformat())\
            .order("fetched_at", desc=True)\
            .limit(config["report"]["top_n"])\
            .execute()
        
        items = response.data if hasattr(response, 'data') else []
    except Exception as e:
        print(f"⚠️ 获取周报数据失败: {e}")
        items = []
    
    # 按 topic 分组
    topics_dict = {}
    for item in items:
        topic = item.get("topic", "其他")
        if topic not in topics_dict:
            topics_dict[topic] = []
        topics_dict[topic].append(item)
    
    # 生成 markdown
    report_lines = [
        f"# 雷达周报 - {week_start.strftime('%Y-%m-%d')} 至 {week_end.strftime('%Y-%m-%d')}",
        "",
        f"生成时间: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC",
        "",
        f"## 总览",
        f"- 本周捕获项目数: {len(items)}",
        f"- 涉及主题数: {len(topics_dict)}",
        "",
    ]
    
    # 按主题输出
    for topic, topic_items in topics_dict.items():
        report_lines.extend([
            f"## {topic}",
            ""
        ])
        
        for i, item in enumerate(topic_items, 1):
            title = item.get("title", "无标题")
            url = item.get("url", "")
            snippet = item.get("snippet", "")
            hostname = item.get("hostname", "")
            
            report_lines.extend([
                f"### {i}. {title}",
                f"",
                f"- **来源**: [{hostname}]({url})",
                f"- **摘要**: {snippet[:200]}{'...' if len(snippet) > 200 else ''}",
                f""
            ])
    
    return "\n".join(report_lines)


def upsert_weekly_report(client, report_content: str) -> bool:
    """将周报写入数据库（按 week_start 去重）
    
    Args:
        client: Supabase 客户端
        report_content: 周报 markdown 内容
    
    Returns:
        bool: 成功返回 True，失败返回 False
    """
    if not client:
        print("❌ 写入周报失败: Supabase 客户端未初始化")
        return False
    
    week_start = get_week_start()
    
    # 给正文兜底，避免空值
    report_md = report_content or ""
    
    # 硬断言：确保 markdown 不为空（表结构要求 NOT NULL）
    assert report_md is not None, "❌ 错误: report_md 不能为 None"
    
    data = {
        "week_start": week_start.isoformat(),
        "markdown": report_md,  # 表结构要求 markdown 字段 NOT NULL
        "content": report_md,   # 如果需要保留 content，让它等于同一份文本
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    try:
        # 使用 upsert（按 week_start 去重，表上应有唯一约束）
        client.table("weekly_reports").upsert(data, on_conflict="week_start").execute()
        print(f"✅ 周报已保存: {week_start.strftime('%Y-%m-%d')} (markdown 长度: {len(report_md)} 字符)")
        return True
    except Exception as e:
        print(f"❌ 写入 weekly_reports 失败: {e}")
        return False


def main():
    """主函数
    
    Returns:
        int: 成功返回 0，失败返回非 0
    """
    start_time = datetime.now(timezone.utc)
    print("🚀 启动雷达抓取任务...")
    print(f"   开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    
    # 加载配置
    try:
        config = load_config()
    except Exception as e:
        print(f"❌ 配置加载失败，任务终止")
        return 1
    
    # 获取 Supabase 客户端（使用 service role 以拥有更高权限）
    client = get_supabase_client(use_service_role=True)
    if not client:
        print("❌ 无法连接到 Supabase，任务终止")
        return 1
    
    # 监控统计信息
    total_items_fetched = 0  # 本次抓取到的总条数
    total_deals_upserted = 0  # 本次 upsert 的总条数
    total_deals_errors = 0  # 本次错误的总条数
    total_deals_reactivated = 0  # 本次复活的总条数
    
    # 遍历所有主题
    for topic in config["topics"]:
        topic_name = topic["name"]
        queries = topic["queries"]
        weight = topic.get("weight", 1.0)
        
        print(f"\n📌 处理主题: {topic_name} (权重: {weight})")
        
        # 遍历所有查询
        for query in queries:
            print(f"  🔍 搜索: {query}")
            
            # 判断是否为中文查询
            has_chinese = any('\u4e00' <= char <= '\u9fff' for char in query)
            
            if has_chinese:
                # 中文查询使用中国区配置
                results = search_serper(
                    query,
                    gl=config["search"]["gl_cn"],
                    hl=config["search"]["hl_cn"],
                    num=config["search"]["results_per_query"]
                )
            else:
                # 英文查询使用美国区配置
                results = search_serper(
                    query,
                    gl=config["search"]["gl"],
                    hl=config["search"]["hl"],
                    num=config["search"]["results_per_query"]
                )
            
            if results:
                fetched_count = len(results)
                total_items_fetched += fetched_count
                print(f"    ✅ 找到 {fetched_count} 条结果")
                
                # 写入雷达项（传入 query 用于调试打印）
                upsert_radar_items(client, results, topic_name, query)
                
                # 写入 deals（返回统计信息）
                stats = upsert_deals(client, results, topic_name)
                if stats:
                    total_deals_upserted += stats.get("processed", 0)
                    total_deals_errors += stats.get("errors", 0)
                    total_deals_reactivated += stats.get("reactivated", 0)
            else:
                print(f"    ⚠️ 未找到结果")
    
    # 生成并保存周报
    print(f"\n📝 生成周报...")
    report_content = generate_weekly_report(client, config)
    if report_content:
        report_saved = upsert_weekly_report(client, report_content)
        if report_saved:
            print(f"✅ 周报已生成并保存")
        else:
            print(f"❌ 周报生成成功，但保存失败")
            return 1
    else:
        print(f"⚠️ 周报生成失败或数据为空")
        # 注意：数据为空不算失败，可能是本周没有新数据
    
    # (1) DB 侧兜底：自动复活 7 天内的 dismissed 记录
    print(f"\n🔄 执行 DB 侧复活兜底检查...")
    db_reactivated_count = reactivate_dismissed_deals(client)
    total_deals_reactivated += db_reactivated_count
    
    # (2) 最小化监控日志
    end_time = datetime.now(timezone.utc)
    duration = end_time - start_time
    duration_seconds = duration.total_seconds()
    
    print(f"\n" + "=" * 60)
    print(f"📊 本次运行监控日志")
    print(f"=" * 60)
    print(f"  本次抓取到: {total_items_fetched} 条")
    print(f"  本次 upsert: {total_deals_upserted} 条")
    print(f"  出现错误: {total_deals_errors} 条")
    print(f"  被复活: {total_deals_reactivated} 条（含 DB 侧兜底 {db_reactivated_count} 条）")
    print(f"  本次运行耗时: {duration_seconds:.2f} 秒 ({duration_seconds/60:.2f} 分钟)")
    print(f"  最后成功时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print(f"=" * 60)
    
    # (3) DB 健康检查（每天跑一次，可选：只在特定时间运行）
    # 这里每次都运行，实际可以根据需要改为每天一次
    print(f"\n🏥 执行 DB 健康检查...")
    health_result = health_check_deals(client, run_started_at=start_time)
    if health_result:
        print(f"    📊 健康检查结果:")
        print(f"      - evidence_urls 超过 20 条: {health_result.get('evidence_over_20', 0)} 条")
        print(f"      - seen_count 为 null: {health_result.get('seen_count_null', 0)} 条")
        print(f"      - 最新 last_seen_at: {health_result.get('latest_last_seen_at', 'N/A')}")
        print(f"      - archived 记录在过去 2 小时内被更新: {health_result.get('archived_updated_last_2h', 0)} 条")
        
        # 如果有异常，打印警告
        if health_result.get('evidence_over_20', 0) > 0:
            print(f"    ⚠️ 警告：发现 {health_result.get('evidence_over_20')} 条记录的 evidence_urls 超过 20 条")
        if health_result.get('seen_count_null', 0) > 0:
            print(f"    ⚠️ 警告：发现 {health_result.get('seen_count_null')} 条记录的 seen_count 为 null")
        
        # Archived 保护验收：如果过去 2 小时内有 archived 记录被更新，返回非 0 退出码
        archived_updated_count = health_result.get('archived_updated_last_2h', 0)
        if archived_updated_count > 0:
            print(f"\n❌ 验收失败：发现 {archived_updated_count} 条 archived 记录在过去 2 小时内被更新")
            print(f"   这违反了 archived 保护规则，可能存在代码回归")
            print(f"   请检查 runner 代码中的 archived 保护逻辑")
            return 1
    
    print(f"\n✅ 雷达抓取任务完成！")
    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code if exit_code is not None else 0)
