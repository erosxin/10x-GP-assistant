@echo off
echo 正在启动 AI 分析助手...
echo 请勿关闭此黑框，在浏览器中使用即可。

:: 检查是否安装了依赖 (可选，为了保险)
:: pip install -r requirements.txt

:: 启动 Streamlit
streamlit run app.py

pause