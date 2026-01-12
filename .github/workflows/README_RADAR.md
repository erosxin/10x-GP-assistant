# Radar Runner GitHub Actions Workflow

## 配置说明

### 1. GitHub Secrets 配置

在 GitHub 仓库的 Settings → Secrets and variables → Actions 中配置以下 Secrets：

- `SUPABASE_URL`: Supabase 项目 URL
- `SUPABASE_SERVICE_ROLE_KEY`: Supabase Service Role Key（拥有完整权限）
- `SUPABASE_ANON_KEY`: Supabase Anonymous Key（可选，用于前端）
- `SERPER_API_KEY`: Serper API 密钥（用于搜索）

### 2. Workflow 配置

- **调度时间**: 每周六 09:00 北京时间（UTC 01:00）
- **手动触发**: 支持在 GitHub Actions 页面手动运行
- **并发控制**: 同一时间只运行一个实例（不取消进行中的任务）
- **超时时间**: 30 分钟

## 验收检查清单

### 在 GitHub Actions 中手动触发一次，验证以下三点：

1. **Job 成功结束**
   - ✅ 在 Actions 页面查看 workflow 运行状态
   - ✅ 所有步骤显示绿色 ✓
   - ✅ 最终状态为 "Success"

2. **日志包含监控信息**
   - ✅ 查看 "Run radar" 步骤的日志输出
   - ✅ 应该看到以下监控日志：
     ```
     ============================================================
     📊 本次运行监控日志
     ============================================================
       本次抓取到: X 条
       本次 upsert: X 条
       出现错误: X 条
       被复活: X 条（含 DB 侧兜底 X 条）
       本次运行耗时: X.XX 秒 (X.XX 分钟)
       最后成功时间: YYYY-MM-DD HH:MM:SS UTC
     ============================================================
     ```
   - ✅ 应该看到健康检查结果：
     ```
     🏥 执行 DB 健康检查...
        📊 健康检查结果:
          - evidence_urls 超过 20 条: X 条
          - seen_count 为 null: X 条
          - 最新 last_seen_at: YYYY-MM-DDTHH:MM:SS
     ```

3. **Supabase 数据更新**
   - ✅ 在 Supabase Dashboard 中查询 `deals` 表
   - ✅ 检查 `last_seen_at` 字段是否有最新更新（应该是 workflow 运行时间）
   - ✅ 检查 `seen_count` 是否有增长
   - ✅ 检查是否有新记录被创建或更新

## 手动触发步骤

1. 进入 GitHub 仓库页面
2. 点击 "Actions" 标签
3. 在左侧选择 "radar-runner" workflow
4. 点击 "Run workflow" 按钮
5. 选择分支（通常是 `main` 或 `master`）
6. 点击 "Run workflow" 确认

## 故障排查

如果 workflow 失败：

1. **检查 Secrets 配置**
   - 确认所有必需的 Secrets 都已配置
   - 确认 Secret 名称拼写正确

2. **检查日志输出**
   - 查看失败步骤的详细日志
   - 查找错误信息（通常以 ❌ 或 ⚠️ 开头）

3. **检查依赖安装**
   - 确认 `requirements.txt` 包含所有必需的包
   - 确认 Python 版本兼容（3.11）

4. **检查 Supabase 连接**
   - 确认 `SUPABASE_URL` 和 `SUPABASE_SERVICE_ROLE_KEY` 正确
   - 确认 Supabase 服务可访问
