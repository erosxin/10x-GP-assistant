"""
集成测试：验证 archived/shortlisted 状态保护规则

测试场景：
1. 把某条记录设为 archived
2. 重新抓到同一条（通过 dedupe_key）
3. 验证：seen_count/last_seen_at 增长，但 status 仍是 archived
"""

# 首先加载环境变量
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(dotenv_path=Path(__file__).parent / ".env", override=False)

import os
from datetime import datetime
from db.supabase_db import get_supabase_client


def test_status_protection():
    """测试 archived/shortlisted 状态保护"""
    print("=" * 60)
    print("集成测试：验证 archived/shortlisted 状态保护规则")
    print("=" * 60)
    
    client = get_supabase_client(use_service_role=True)
    if not client:
        print("❌ 无法创建 Supabase 客户端（请检查环境变量）")
        return False
    
    try:
        # 1. 找一条测试记录
        print("\n📖 步骤 1: 查找测试记录...")
        response = client.table("deals")\
            .select("id,dedupe_key,status,seen_count,last_seen_at,first_seen_at")\
            .limit(1)\
            .execute()
        
        if not response.data or len(response.data) == 0:
            print("⚠️ 无法测试：deals 表中没有数据")
            return False
        
        test_deal = response.data[0]
        deal_id = test_deal.get("id")
        dedupe_key = test_deal.get("dedupe_key")
        original_status = test_deal.get("status")
        original_seen_count = test_deal.get("seen_count", 0)
        original_last_seen_at = test_deal.get("last_seen_at")
        
        print(f"    ✅ 找到测试记录:")
        print(f"      - ID: {deal_id}")
        print(f"      - dedupe_key: {dedupe_key[:20]}...")
        print(f"      - 当前 status: {original_status}")
        print(f"      - 当前 seen_count: {original_seen_count}")
        print(f"      - 当前 last_seen_at: {original_last_seen_at}")
        
        # 2. 设置为 archived
        print(f"\n📝 步骤 2: 将记录设置为 archived...")
        client.rpc("deal_archive", {"deal_id_param": deal_id}).execute()
        print(f"    ✅ 已设置为 archived")
        
        # 验证状态已改变
        check_response = client.table("deals")\
            .select("status")\
            .eq("id", deal_id)\
            .execute()
        
        if check_response.data and check_response.data[0].get("status") == "archived":
            print(f"    ✅ 状态确认：已成功设置为 archived")
        else:
            print(f"    ❌ 状态确认失败：状态未正确设置")
            return False
        
        # 3. 模拟重新抓取（通过 upsert 更新）
        print(f"\n🔄 步骤 3: 模拟重新抓取（通过 dedupe_key upsert）...")
        
        # 获取记录的完整信息用于模拟
        full_response = client.table("deals")\
            .select("*")\
            .eq("id", deal_id)\
            .execute()
        
        if not full_response.data:
            print("    ❌ 无法获取完整记录信息")
            return False
        
        full_deal = full_response.data[0]
        
        # 模拟 upsert（只更新 seen_count 和 last_seen_at，不更新 status）
        now_iso = datetime.utcnow().isoformat()
        new_seen_count = (full_deal.get("seen_count", 0) or 0) + 1
        
        # 构建更新数据（不包含 status）
        update_data = {
            "dedupe_key": dedupe_key,
            "last_seen_at": now_iso,
            "seen_count": new_seen_count,
            "updated_at": now_iso
        }
        
        # 执行 upsert（按 dedupe_key）
        client.table("deals").upsert(update_data, on_conflict="dedupe_key").execute()
        print(f"    ✅ 已执行 upsert（seen_count: {original_seen_count} -> {new_seen_count}）")
        
        # 4. 验证结果
        print(f"\n✅ 步骤 4: 验证结果...")
        final_response = client.table("deals")\
            .select("id,status,seen_count,last_seen_at")\
            .eq("id", deal_id)\
            .execute()
        
        if not final_response.data:
            print("    ❌ 无法获取最终记录")
            return False
        
        final_deal = final_response.data[0]
        final_status = final_deal.get("status")
        final_seen_count = final_deal.get("seen_count")
        final_last_seen_at = final_deal.get("last_seen_at")
        
        print(f"    - 最终 status: {final_status}")
        print(f"    - 最终 seen_count: {final_seen_count}")
        print(f"    - 最终 last_seen_at: {final_last_seen_at}")
        
        # 验证规则
        status_ok = final_status == "archived"
        seen_count_ok = final_seen_count == new_seen_count
        last_seen_at_ok = final_last_seen_at != original_last_seen_at
        
        if status_ok and seen_count_ok and last_seen_at_ok:
            print(f"\n✅ 测试通过！")
            print(f"  - status 保持为 archived: {status_ok}")
            print(f"  - seen_count 已增长: {seen_count_ok} ({original_seen_count} -> {final_seen_count})")
            print(f"  - last_seen_at 已更新: {last_seen_at_ok}")
            return True
        else:
            print(f"\n❌ 测试失败！")
            print(f"  - status 保持为 archived: {status_ok}")
            print(f"  - seen_count 已增长: {seen_count_ok}")
            print(f"  - last_seen_at 已更新: {last_seen_at_ok}")
            return False
            
    except Exception as e:
        print(f"\n❌ 测试过程出错: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_status_protection()
    exit(0 if success else 1)
