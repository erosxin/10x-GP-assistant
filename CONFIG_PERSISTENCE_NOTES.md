# 配置持久化功能说明

## 🎯 功能目标

解决用户每次重启应用都需要重新输入 API Key 和选择模型的问题，实现配置自动保存和加载。

## ✨ 实现功能

### 1. 配置文件管理

#### `config.json` 文件结构
```json
{
  "api_key": "sk-xxx...",
  "base_url": "https://openrouter.ai/api/v1",
  "model": "google/gemini-flash-1.5"
}
```

#### 自动加载
- 应用启动时自动读取 `config.json`
- 如果文件不存在，使用默认值：
  - `api_key`: 从环境变量 `OPENROUTER_API_KEY` 读取，否则为空
  - `base_url`: `https://openrouter.ai/api/v1`（固定）
  - `model`: `google/gemini-flash-1.5`（默认）

#### 自动保存
- 用户修改 API Key 或 Model 时，立即自动保存到 `config.json`
- 使用 `on_change` 回调函数实现即时保存
- 无需手动点击保存按钮

### 2. UI 组件绑定

#### 侧边栏输入框
- **API Key**: 
  - 类型：密码输入框
  - 支持自动保存
  - 从配置文件加载默认值
  
- **Base URL**: 
  - 类型：文本输入框（禁用）
  - 固定值，不可修改
  - 但仍然保存在配置中
  
- **Model**: 
  - 类型：文本输入框
  - 支持自动保存
  - 从配置文件加载默认值

### 3. Session State 管理

- 使用 `st.session_state` 存储输入框的值
- 确保配置在应用重新运行时保持
- 避免重复加载配置文件

## 🔧 技术实现

### 核心函数

1. **`load_config()`**
   - 读取 `config.json` 文件
   - 如果文件不存在，返回默认配置
   - 处理读取错误，返回默认值

2. **`save_config()`**
   - 从 `st.session_state` 读取当前输入值
   - 保存到 `config.json` 文件
   - 使用 UTF-8 编码，支持中文

### 配置加载时机

- **首次加载**：应用启动时，如果 `config_loaded` 不在 session_state 中，加载配置
- **初始化输入框**：将加载的配置值设置到 session_state 中
- **输入框渲染**：使用 session_state 中的值作为默认值

### 配置保存时机

- **用户修改时**：通过 `on_change` 回调自动触发
- **即时保存**：无需等待或手动触发
- **静默保存**：保存过程对用户透明

## 📁 文件位置

配置文件存储在项目根目录：
```
GP_Partner_Clean/
├── config.json          # 配置文件（自动生成）
├── app.py
└── ...
```

## 🚀 使用说明

### 首次使用
1. 启动应用
2. 在侧边栏输入 API Key 和 Model
3. 配置会自动保存到 `config.json`

### 后续使用
1. 启动应用
2. 配置会自动从 `config.json` 加载
3. API Key 和 Model 已自动填充

### 修改配置
1. 直接在侧边栏修改输入框内容
2. 修改后立即自动保存
3. 无需额外操作

## ⚠️ 注意事项

1. **安全性**：`config.json` 包含 API Key，请确保不要将其提交到版本控制系统
2. **文件权限**：确保应用有权限读写 `config.json` 文件
3. **备份**：建议定期备份配置文件，避免丢失
4. **优先级**：如果 `.env` 文件中存在 `OPENROUTER_API_KEY`，首次加载时会优先使用环境变量

## 🔒 安全建议

1. **添加到 .gitignore**：
   ```
   config.json
   ```

2. **使用环境变量**（更安全）：
   - 仍然可以通过 `.env` 文件设置 API Key
   - 配置文件主要用于存储用户偏好（如 Model 选择）

3. **权限控制**：
   - 确保 `config.json` 文件权限正确（建议仅当前用户可读写）

## 📊 优先级说明

配置加载优先级：
1. `config.json` 文件中的值（如果存在）
2. 环境变量 `OPENROUTER_API_KEY`（仅用于 API Key，如果 config.json 中没有）
3. 默认值（BASE_URL 和 DEFAULT_MODEL）

## 🔄 迁移说明

### 从 .env 迁移
如果之前使用 `.env` 文件：
1. 首次运行会自动读取 `.env` 中的 API Key
2. 输入其他配置后，所有配置会保存到 `config.json`
3. 之后可以直接使用 `config.json`，无需 `.env` 文件

### 手动迁移
可以直接创建 `config.json` 文件：
```json
{
  "api_key": "你的API Key",
  "base_url": "https://openrouter.ai/api/v1",
  "model": "你的模型名称"
}
```
