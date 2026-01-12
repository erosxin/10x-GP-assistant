# 快速设置指南

## 📋 手动创建文件夹结构

项目需要的文件夹结构如下（大部分已自动创建）：

```
GP_Partner_Clean/
├── app.py                 ✅ 已创建
├── prompts/               ✅ 已存在（包含7个提示词文件）
├── history_data/          ✅ 已创建（用于存储历史记录）
├── .env                   ❌ 需要手动创建（见下方说明）
├── requirements.txt       ✅ 已创建
└── README.md             ✅ 已创建
```

## 🔑 创建 .env 文件

在项目根目录下创建一个名为 `.env` 的文件（注意前面有一个点），内容如下：

```env
OPENROUTER_API_KEY=your_api_key_here
```

**重要提示**：
- 将 `your_api_key_here` 替换为你的实际 OpenRouter API Key
- 如果不想使用 .env 文件，也可以直接在应用的侧边栏手动输入 API Key

## 🚀 安装和运行

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 运行应用

```bash
streamlit run app.py
```

应用将在浏览器中自动打开（默认地址：http://localhost:8501）

## ✨ 使用提示

1. **添加新的分析模式**：只需在 `prompts/` 文件夹中添加新的 `.txt` 文件即可
2. **查看历史记录**：所有分析结果会自动保存到 `history_data/` 文件夹
3. **导出报告**：分析完成后，点击"下载 Word 报告"按钮即可导出
