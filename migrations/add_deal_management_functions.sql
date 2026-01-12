-- 迁移脚本：为 deals 表添加人工操作接口（RPC 函数）
-- 执行方式：在 Supabase SQL Editor 中执行，或通过 Supabase CLI

-- 规则 C：人工操作接口
-- 前端/后台管理对状态的修改只调用这些 RPC 函数

-- 1. deal_dismiss: 标记为 dismissed
create or replace function public.deal_dismiss(
    deal_id_param bigint,
    reason_param text default null
)
returns void
language plpgsql
security definer
as $$
begin
    update public.deals
    set 
        status = 'dismissed',
        dismissed_reason = reason_param,
        dismissed_at = now(),
        updated_at = now()
    where id = deal_id_param;
    
    if not found then
        raise exception 'Deal with id % not found', deal_id_param;
    end if;
end;
$$;

-- 2. deal_shortlist: 标记为 shortlisted
create or replace function public.deal_shortlist(
    deal_id_param bigint
)
returns void
language plpgsql
security definer
as $$
begin
    update public.deals
    set 
        status = 'shortlisted',
        updated_at = now()
    where id = deal_id_param;
    
    if not found then
        raise exception 'Deal with id % not found', deal_id_param;
    end if;
end;
$$;

-- 3. deal_archive: 标记为 archived
create or replace function public.deal_archive(
    deal_id_param bigint
)
returns void
language plpgsql
security definer
as $$
begin
    update public.deals
    set 
        status = 'archived',
        updated_at = now()
    where id = deal_id_param;
    
    if not found then
        raise exception 'Deal with id % not found', deal_id_param;
    end if;
end;
$$;

-- 使用示例（id 类型为 bigint）：
-- select public.deal_dismiss(1299, '不符合投资标准');
-- select public.deal_shortlist(1299);
-- select public.deal_archive(1299);
