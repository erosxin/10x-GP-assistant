"""
测试脚本：验证 "雷达候选池" 和 "周报" 页面的 Supabase 读写功能
"""
import os
from db.supabase_db import get_supabase_client
from datetime import datetime

def test_deals_read():
    """测试从 deals 表读取数据"""
    print("=" * 60)
    print("测试 1: 读取 deals 表")
    print("=" * 60)
    
    supabase_client = get_supabase_client(use_service_role=False)
    
    if not supabase_client:
        print("❌ Supabase 客户端创建失败（请检查环境变量）")
        return False
    
    try:
        response = supabase_client.table("deals")\
            .select("*")\
            .order("updated_at", desc=True)\
            .limit(50)\
            .execute()
        
        deals = response.data if hasattr(response, 'data') else []
        
        print(f"✅ 成功读取 deals 表")
        print(f"📊 总记录数: {len(deals)} 条")
        
        if deals:
            print("\n📌 示例数据（第1条）:")
            first_deal = deals[0]
            print(f"  - ID/dedupe_key: {first_deal.get('id') or first_deal.get('dedupe_key', 'N/A')}")
            print(f"  - canonical_name: {first_deal.get('canonical_name', first_deal.get('title', 'N/A'))}")
            print(f"  - one_liner: {first_deal.get('one_liner', first_deal.get('description', 'N/A'))[:50]}...")
            print(f"  - website: {first_deal.get('website', first_deal.get('url', 'N/A'))}")
            print(f"  - updated_at: {first_deal.get('updated_at', first_deal.get('created_at', 'N/A'))}")
        else:
            print("⚠️ 表中暂无数据")
        
        return True
        
    except Exception as e:
        print(f"❌ 读取失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_deal_actions_write():
    """测试写入 deal_actions 表"""
    print("\n" + "=" * 60)
    print("测试 2: 写入 deal_actions 表")
    print("=" * 60)
    
    supabase_client = get_supabase_client(use_service_role=False)
    
    if not supabase_client:
        print("❌ Supabase 客户端创建失败（请检查环境变量）")
        return False
    
    # 先读取一条 deal 来获取 deal_id
    try:
        deals_response = supabase_client.table("deals")\
            .select("*")\
            .limit(1)\
            .execute()
        
        deals = deals_response.data if hasattr(deals_response, 'data') else []
        
        if not deals:
            print("⚠️ 无法测试：deals 表中没有数据，无法获取 deal_id")
            return False
        
        test_deal = deals[0]
        deal_id = test_deal.get('id') or test_deal.get('dedupe_key', '')
        
        if not deal_id:
            print("⚠️ 无法测试：deal 缺少 id 或 dedupe_key")
            return False
        
        print(f"📌 使用测试 deal_id: {deal_id}")
        print(f"📌 Deal 名称: {test_deal.get('canonical_name', test_deal.get('title', 'N/A'))}")
        
        # 测试写入 Intro action
        test_action = "intro"
        action_data = {
            "deal_id": deal_id,
            "action": test_action,
            "notes": f"测试记录 - {datetime.utcnow().isoformat()}",
            "created_at": datetime.utcnow().isoformat()
        }
        
        print(f"\n🔄 尝试写入 action: {test_action}")
        insert_response = supabase_client.table("deal_actions").insert(action_data).execute()
        
        inserted_data = insert_response.data if hasattr(insert_response, 'data') else []
        
        if inserted_data:
            print(f"✅ 成功写入 deal_actions 表")
            print(f"📊 插入的记录:")
            for key, value in inserted_data[0].items():
                print(f"  - {key}: {value}")
            
            # 验证：读取刚写入的记录
            print(f"\n🔍 验证：读取刚写入的记录...")
            verify_response = supabase_client.table("deal_actions")\
                .select("*")\
                .eq("deal_id", deal_id)\
                .eq("action", test_action)\
                .order("created_at", desc=True)\
                .limit(1)\
                .execute()
            
            verify_data = verify_response.data if hasattr(verify_response, 'data') else []
            if verify_data:
                print(f"✅ 验证成功：在表中找到刚写入的记录")
                print(f"📊 验证记录 ID: {verify_data[0].get('id', 'N/A')}")
            else:
                print(f"⚠️ 警告：写入成功但验证读取时未找到记录（可能需要稍等片刻）")
            
            return True
        else:
            print(f"❌ 写入失败：未返回插入的数据")
            return False
        
    except Exception as e:
        print(f"❌ 写入失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_weekly_reports_read():
    """测试从 weekly_reports 表读取最新一条"""
    print("\n" + "=" * 60)
    print("测试 3: 读取 weekly_reports 表（最新一条）")
    print("=" * 60)
    
    supabase_client = get_supabase_client(use_service_role=False)
    
    if not supabase_client:
        print("❌ Supabase 客户端创建失败（请检查环境变量）")
        return False
    
    try:
        response = supabase_client.table("weekly_reports")\
            .select("*")\
            .order("week_start", desc=True)\
            .limit(1)\
            .execute()
        
        reports = response.data if hasattr(response, 'data') else []
        
        print(f"✅ 成功读取 weekly_reports 表")
        print(f"📊 找到记录数: {len(reports)} 条")
        
        if reports:
            report = reports[0]
            print("\n📌 最新周报信息:")
            print(f"  - week_start: {report.get('week_start', 'N/A')}")
            print(f"  - created_at: {report.get('created_at', 'N/A')}")
            print(f"  - report_type: {report.get('report_type', 'N/A')}")
            
            content = report.get('content', '')
            if content:
                content_preview = content[:200] + "..." if len(content) > 200 else content
                print(f"  - content 长度: {len(content)} 字符")
                print(f"  - content 预览:\n{content_preview}")
                print(f"\n✅ Markdown 内容可正常读取和显示")
            else:
                print(f"  ⚠️ content 为空")
        else:
            print("⚠️ 表中暂无周报数据")
        
        return True
        
    except Exception as e:
        print(f"❌ 读取失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("Supabase 页面功能测试")
    print("=" * 60)
    print("\n⚠️ 注意：需要设置环境变量 SUPABASE_URL 和 SUPABASE_ANON_KEY")
    print("\n开始测试...\n")
    
    # 检查环境变量
    if not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_ANON_KEY"):
        print("❌ 错误：未设置 Supabase 环境变量")
        print("请设置以下环境变量：")
        print("  - SUPABASE_URL")
        print("  - SUPABASE_ANON_KEY")
        exit(1)
    
    results = []
    
    # 运行测试
    results.append(("读取 deals 表", test_deals_read()))
    results.append(("写入 deal_actions 表", test_deal_actions_write()))
    results.append(("读取 weekly_reports 表", test_weekly_reports_read()))
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    for test_name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{status}: {test_name}")
    
    all_passed = all(result[1] for result in results)
    print("\n" + ("=" * 60))
    if all_passed:
        print("🎉 所有测试通过！")
    else:
        print("⚠️ 部分测试失败，请检查上述错误信息")
    print("=" * 60 + "\n")
