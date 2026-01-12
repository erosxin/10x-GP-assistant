# GP Partner Ultimate

高级投资辅助系统 - 基于 Streamlit 和 OpenRouter API 的多模式投资分析工具

## 🚀 功能特性

- **多模式切换**: 自动扫描 `prompts/` 文件夹，支持动态加载不同的分析策略
- **OpenRouter API 集成**: 支持多种 AI 模型（默认使用 Google Gemini Flash 1.5）
- **文件上传**: 支持 PDF 和 DOCX 格式文件上传
- **流式响应**: 实时显示 AI 分析结果，提供流畅的用户体验
- **历史记录**: 自动保存所有分析记录，支持查看和回溯
- **Word 导出**: 智能将 Markdown 格式的分析结果转换为格式化的 Word 文档

## 📁 项目结构

```
GP_Partner_Ultimate/
├── app.py                 # 主程序文件
├── prompts/               # 提示词文件夹（存放 .txt 文件）
│   ├── 01_通用主神_Eros_v26.txt
│   ├── 02_Ares_执行官_v3.1.txt
│   └── ...
├── history_data/          # 历史记录文件夹（自动生成）
│   └── *.json            # 分析历史记录（JSON 格式）
├── .env                   # API Key 配置文件（需手动创建）
├── .env.example          # API Key 配置示例
├── requirements.txt      # Python 依赖包列表
└── README.md            # 本文件
```

## 🛠️ 安装步骤

### 1. 创建虚拟环境（推荐）

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置 API Key

**方式一：使用 .env 文件（推荐）**

1. 复制 `.env.example` 文件并重命名为 `.env`
2. 编辑 `.env` 文件，填入你的 OpenRouter API Key：
   ```
   OPENROUTER_API_KEY=your_actual_api_key_here
   ```

**方式二：在应用中手动输入**

直接在应用侧边栏的 "API Key" 输入框中输入你的 API Key（不会保存到文件）

### 4. 准备提示词文件

确保 `prompts/` 文件夹中已经包含 `.txt` 格式的提示词文件。每个文件将作为一个分析模式选项出现在侧边栏中。

### 5. 运行应用

```bash
streamlit run app.py
```

应用将在浏览器中自动打开（通常是 `http://localhost:8501`）

## 📖 使用指南

### 基本流程

1. **选择分析模式**: 在侧边栏的"选择分析模式"下拉框中选择要使用的提示词策略
2. **配置 API**: 确保 API Key 和 Model 配置正确（Model 默认使用 `google/gemini-flash-1.5`）
3. **上传文件**: 在主界面点击"上传分析文件"，选择 PDF 或 DOCX 文件
4. **开始分析**: 点击"开始分析"按钮，等待 AI 处理
5. **查看结果**: 分析结果会实时流式显示在界面上
6. **导出报告**: 点击"下载 Word 报告"按钮，将分析结果导出为格式化的 Word 文档

### 历史记录功能

- 所有分析结果会自动保存到 `history_data/` 文件夹
- 在侧边栏的"历史记录"部分可以查看所有历史分析
- 点击历史记录的"查看完整内容"按钮可以重新加载该分析结果

### Word 导出格式

Markdown 格式会自动转换为 Word 格式：
- `# Title` → 一级标题（Heading 1）
- `## Title` → 二级标题（Heading 2）
- `### Title` → 三级标题（Heading 3）
- `- Item` → 项目符号列表
- 粗体、斜体等格式也会正确转换

## 🔧 技术栈

- **Streamlit**: Web 应用框架
- **OpenAI SDK**: 用于调用 OpenRouter API（兼容 OpenAI API 格式）
- **PyPDF2**: PDF 文件解析
- **python-docx**: Word 文档生成
- **python-dotenv**: 环境变量管理
- **tenacity**: 重试机制（备用）

## ⚠️ 注意事项

1. **API Key 安全**: 请妥善保管你的 OpenRouter API Key，不要将包含真实 Key 的 `.env` 文件提交到版本控制系统
2. **文件大小**: 建议上传的文件不要过大（建议 < 10MB），以确保处理速度
3. **提示词格式**: 确保 `prompts/` 文件夹中的 `.txt` 文件使用 UTF-8 编码
4. **历史记录**: 历史记录文件会不断积累，建议定期清理不需要的记录

## 📝 自定义提示词

要添加新的分析模式，只需：

1. 在 `prompts/` 文件夹中创建一个新的 `.txt` 文件
2. 文件名将作为模式名称显示在下拉框中
3. 文件内容将作为 System Prompt 发送给 AI 模型
4. 重启应用后，新模式会自动出现在选择列表中

## 🐛 故障排除

### 问题：提示"请在 prompts 文件夹放入 .txt 提示词文件"

**解决**: 确保 `prompts/` 文件夹中存在至少一个 `.txt` 文件

### 问题：API 调用失败

**解决**: 
- 检查 API Key 是否正确
- 确认网络连接正常
- 检查 OpenRouter 账户余额

### 问题：PDF 文件无法解析

**解决**: 
- 确保 PDF 文件不是扫描版（纯图片）
- 尝试将 PDF 转换为 DOCX 格式后上传

## 🔍 雷达抓取与周报生成

本项目包含一个自动化雷达抓取系统，每周定期扫描市场动态并生成周报。

### 本地运行雷达抓取

1. **设置环境变量**

   创建 `.env` 文件或设置系统环境变量：
   ```bash
   SERPER_API_KEY=your_serper_api_key
   SUPABASE_URL=your_supabase_url
   SUPABASE_ANON_KEY=your_supabase_anon_key
   SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key
   ```

2. **安装依赖**

   确保已安装所有依赖（包括 `pyyaml`, `requests`, `supabase`, `python-dateutil`）：
   ```bash
   pip install -r requirements.txt
   ```

3. **运行抓取任务**

   ```bash
   python radar/runner.py
   ```

   任务将：
   - 读取 `radar/config.yaml` 配置文件
   - 使用 Serper API 进行搜索
   - 将结果写入 Supabase 数据库的 `radar_items` 和 `deals` 表
   - 生成本周周报并写入 `weekly_reports` 表

### 自动运行

GitHub Actions 工作流 `.github/workflows/radar_mo_we.yml` 会在每周一和周三 UTC 02:00（北京时间 10:00）自动运行。

你也可以在 GitHub Actions 页面手动触发该工作流。

### 数据库表结构

- **radar_items**: 存储所有抓取的雷达项（按 `url_hash` 去重）
- **deals**: 存储项目信息（按 `hostname+title` 去重）
- **weekly_reports**: 存储生成的周报（按 `week_start` 去重）

## 📄 许可证

本项目仅供内部使用。

## 👥 贡献

如有问题或建议，请联系开发团队。
