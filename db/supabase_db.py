"""Supabase 数据库客户端"""
import os
from supabase import create_client, Client
from typing import Optional


def get_supabase_client(use_service_role: bool = False) -> Optional[Client]:
    """
    创建并返回 Supabase 客户端
    
    Args:
        use_service_role: 是否使用 service role key（拥有更高权限）
    
    Returns:
        Supabase Client 实例，如果环境变量未配置则返回 None
    """
    supabase_url = os.getenv("SUPABASE_URL")
    
    if use_service_role:
        supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    else:
        supabase_key = os.getenv("SUPABASE_ANON_KEY")
    
    if not supabase_url or not supabase_key:
        print("⚠️ Supabase 环境变量未配置")
        return None
    
    try:
        client = create_client(supabase_url, supabase_key)
        return client
    except Exception as e:
        print(f"❌ 创建 Supabase 客户端失败: {e}")
        return None
