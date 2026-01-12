-- 迁移脚本：为 deals 表添加状态管理字段
-- 执行方式：在 Supabase SQL Editor 中执行，或通过 Supabase CLI

-- 添加状态相关字段
alter table public.deals
add column if not exists status text default 'new',
add column if not exists first_seen_at timestamptz,
add column if not exists last_seen_at timestamptz,
add column if not exists seen_count int default 1,
add column if not exists dismissed_reason text,
add column if not exists dismissed_at timestamptz;

-- 添加状态约束（确保 status 只能是有效值）
do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'deals_status_check'
  ) then
    alter table public.deals
    add constraint deals_status_check
    check (status in ('new','shortlisted','dismissed','archived'));
  end if;
end$$;

-- 确保 dedupe_key 唯一索引（如果之前没有创建）
create unique index if not exists deals_dedupe_key_uidx
on public.deals (dedupe_key);

-- 为现有记录设置默认值（如果字段刚添加）
update public.deals
set 
  status = coalesce(status, 'new'),
  seen_count = coalesce(seen_count, 1),
  first_seen_at = coalesce(first_seen_at, created_at),
  last_seen_at = coalesce(last_seen_at, updated_at)
where status is null or first_seen_at is null or last_seen_at is null or seen_count is null;

-- 修改 seen_count 默认值为 1（更合理，避免未来任何写入漏掉也正确）
alter table public.deals alter column seen_count set default 1;

-- 更新现有数据：将 seen_count 为 null 或 0 的记录设为 1
update public.deals
set seen_count = 1
where seen_count is null or seen_count = 0;
