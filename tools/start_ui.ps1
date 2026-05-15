$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$env:STREAMLIT_SERVER_ADDRESS = 'localhost'
$env:STREAMLIT_SERVER_PORT = '8501'
python -m streamlit run "$root\src\youtube_content_studio\ui\app.py" --server.address localhost --server.port 8501 --server.headless true
