"""
统一主题与全局 CSS 注入。
每个 page 文件在最顶端调用 `apply_theme()` 即可继承相同样式。

set_page_config 必须由整个 app 的入口文件（dashboard.py）先调用一次；
子页面不再重复调用，以免 Streamlit 抛 "set_page_config can only be called once" 警告。
"""

import streamlit as st


_FONT_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;1,9..40,300;1,9..40,400&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,400,0,0&display=swap');

* {
    font-family: 'DM Sans', sans-serif !important;
}

html, body, div, span, p, h1, h2, h3, h4, h5, h6,
input, button, select, textarea, label,
[class*="css"], [class*="st-"],
.stApp, .main, .block-container,
[data-testid], [data-baseweb] {
    font-family: 'DM Sans', sans-serif !important;
}

/* 关键：上面的 `*` 通配符 + !important 会把 Material Symbols 图标按钮
   （sidebar 折叠/展开按钮）的字体也改成 DM Sans，导致图标 ligature 文本
   "keyboard_double_arrow_left/right" 原样显示出来。这里恢复成图标字体。 */
[class*="material-symbols"],
[class*="material-icons"],
.material-symbols-rounded,
.material-symbols-outlined,
.material-icons,
[data-testid="stSidebarCollapseButton"] *,
[data-testid="stSidebarCollapsedControl"] *,
[data-testid="baseButton-headerNoPadding"] * {
    font-family: 'Material Symbols Rounded', 'Material Symbols Outlined',
                 'Material Icons', sans-serif !important;
}
</style>
"""


_PALETTE_CSS = """
<style>
html, body, [class*="css"], .stApp {
    font-family: 'DM Sans', sans-serif !important;
    background-color: #f9f7f4 !important;
    color: #1a1a1a !important;
}

[data-testid="stSidebar"] {
    background-color: #f0ede8 !important;
    border-right: 1px solid #e5e0d8 !important;
}

[data-testid="stSidebar"] * { color: #1a1a1a !important; }

[data-testid="stSidebar"] .stButton button {
    background: #ffffff !important;
    border: 1px solid #e5e0d8 !important;
    color: #374151 !important;
    border-radius: 8px !important;
    font-size: 13px !important;
    font-weight: 400 !important;
    transition: all 0.15s !important;
    text-align: left !important;
}
[data-testid="stSidebar"] .stButton button:hover {
    background: #ffffff !important;
    border-color: #9ca3af !important;
    color: #111 !important;
}

.main .block-container {
    background-color: #f9f7f4 !important;
    max-width: 1100px !important;
    padding: 2rem 2.5rem !important;
}

[data-testid="metric-container"] {
    background: #ffffff !important;
    border: 1px solid #e5e0d8 !important;
    border-radius: 12px !important;
    padding: 1.2rem !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05) !important;
}
[data-testid="metric-container"] label {
    color: #6b7280 !important;
    font-size: 12px !important;
    font-weight: 500 !important;
    letter-spacing: 0.05em !important;
    text-transform: uppercase !important;
}
[data-testid="metric-container"] [data-testid="stMetricValue"] {
    color: #111827 !important;
    font-size: 28px !important;
    font-weight: 600 !important;
}

h1 {
    font-size: 22px !important;
    font-weight: 600 !important;
    color: #111827 !important;
    letter-spacing: -0.01em !important;
}
h2, h3 {
    font-size: 14px !important;
    font-weight: 500 !important;
    color: #6b7280 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.08em !important;
}

.stButton > button {
    background: #1a1a1a !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 8px !important;
    font-size: 14px !important;
    font-weight: 500 !important;
    padding: 0.5rem 1.5rem !important;
    transition: all 0.15s !important;
}
.stButton > button:hover { background: #374151 !important; }

.stTextInput input {
    background: #ffffff !important;
    border: 1px solid #e5e0d8 !important;
    border-radius: 8px !important;
    color: #1a1a1a !important;
    font-size: 14px !important;
    padding: 0.6rem 1rem !important;
}
.stTextInput input:focus {
    border-color: #9ca3af !important;
    box-shadow: 0 0 0 3px rgba(0,0,0,0.05) !important;
}

[data-testid="stDataFrame"] {
    border: 1px solid #e5e0d8 !important;
    border-radius: 12px !important;
    overflow: hidden !important;
}

hr { border-color: #e5e0d8 !important; margin: 1.5rem 0 !important; }

[data-testid="stStatus"] {
    background: #ffffff !important;
    border: 1px solid #e5e0d8 !important;
    border-radius: 12px !important;
    font-size: 13px !important;
}

.ai-report {
    background: #ffffff;
    border: 1px solid #e5e0d8;
    border-radius: 12px;
    padding: 1.5rem 2rem;
    font-size: 14px;
    line-height: 1.8;
    color: #374151;
}
.ai-report h1, .ai-report h2, .ai-report h3, .ai-report h4 {
    font-size: 0.72rem !important;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: #6b7280;
    margin: 1.25rem 0 0.35rem 0;
    padding-bottom: 4px;
    border-bottom: 1px solid #f3f4f6;
}
.ai-report h1:first-child, .ai-report h2:first-child,
.ai-report h3:first-child, .ai-report h4:first-child { margin-top: 0; }
.ai-report p { margin: 0 0 0.5rem 0; }
.ai-report strong { color: #111827; }

.brand-bio {
    background: #fbfaf7;
    border: 1px solid #e5e0d8;
    border-left: 3px solid #b8a888;
    border-radius: 10px;
    padding: 1.1rem 1.5rem;
    font-size: 13.5px;
    line-height: 1.75;
    color: #4b5563;
    font-style: italic;
}

.conf-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    line-height: 1;
    border: 1px solid;
    vertical-align: middle;
}
.conf-badge .dot { width: 6px; height: 6px; border-radius: 50%; }
.conf-high   { background:#ecfdf5; border-color:#a7f3d0; color:#047857; }
.conf-high   .dot { background:#10b981; }
.conf-medium { background:#fffbeb; border-color:#fde68a; color:#b45309; }
.conf-medium .dot { background:#f59e0b; }
.conf-low    { background:#fef2f2; border-color:#fecaca; color:#b91c1c; }
.conf-low    .dot { background:#ef4444; }
.conf-detail {
    margin-left: 8px;
    font-size: 11px;
    color: #9ca3af;
    font-weight: 400;
    letter-spacing: 0;
    text-transform: none;
}

.page-header {
    font-size: 11px;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: #9ca3af;
    margin-bottom: 2rem;
    border-bottom: 1px solid #e5e0d8;
    padding-bottom: 1rem;
}

div[data-testid="stVerticalBlock"] > div { border-radius: 12px !important; }
.stSlider > div > div { background: #e5e0d8 !important; }
[data-testid="stProgress"] > div > div > div > div { background-color: #374151 !important; }
[data-testid="stSlider"] div[role="slider"] { background-color: #374151 !important; }
[data-testid="stSlider"] > div > div > div > div {
    background: linear-gradient(to right, #374151, #374151) !important;
}
.stSlider [data-baseweb="slider"] div[role="slider"] {
    background-color: #374151 !important;
    border-color: #374151 !important;
}

[data-baseweb="tag"] {
    background-color: #f3f4f6 !important;
    border: 1px solid #d1d5db !important;
    border-radius: 6px !important;
}
[data-baseweb="tag"] span { color: #374151 !important; }
[data-baseweb="tag"] button { color: #9ca3af !important; }

[data-testid="stMultiSelect"] span[data-baseweb="tag"] {
    background-color: #f3f4f6 !important;
    border: 1px solid #d1d5db !important;
    color: #374151 !important;
    border-radius: 6px !important;
}
[data-testid="stMultiSelect"] span[data-baseweb="tag"] span { color: #374151 !important; }
[data-testid="stRadio"] label[data-checked="true"] { color: #111827 !important; }
[data-testid="stMetricValue"] { color: #111827 !important; }
</style>
"""


_LAYOUT_CSS = """
<style>
.block-container {
    padding-top: 1rem !important;
    padding-bottom: 0.5rem !important;
    max-width: 100% !important;
}
div[data-testid="stVerticalBlock"] > div { gap: 0.35rem; }

[data-testid="stVerticalBlock"] {
    position: relative !important;
    z-index: auto !important;
}

.metric-value { color: var(--text-color); }
.report-text  { color: var(--text-color); }
.table-label  { color: var(--text-color); opacity: 0.6; }

.dash-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.3rem 0 0.7rem 0;
    border-bottom: 2px solid #e5e7eb;
    margin-bottom: 0.7rem;
}
.dash-title {
    font-size: 1.3rem;
    font-weight: 700;
    color: var(--text-color);
    letter-spacing: 0.01em;
    white-space: nowrap;
}
.dash-meta {
    font-size: 0.78rem;
    color: #9ca3af;
    text-align: right;
    line-height: 1.5;
    white-space: nowrap;
}

.overview-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 10px;
    margin-bottom: 0.7rem;
}
.ov-card {
    background: var(--background-color);
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    padding: 12px 14px;
    text-align: center;
}
.ov-num {
    font-size: 1.5rem;
    font-weight: 800;
    color: #2563eb;
    line-height: 1.2;
}
.ov-num.gold  { color: #d97706; }
.ov-num.green { color: #059669; }
.ov-num.rose  { color: #e11d48; }
.ov-label {
    font-size: 0.68rem;
    color: #9ca3af;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 3px;
}
.ov-detail {
    font-size: 0.7rem;
    color: #6b7280;
    margin-top: 2px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.kpi-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 10px;
    margin-bottom: 0.7rem;
}
.kpi-card {
    background: var(--background-color);
    border: 1px solid #e5e7eb;
    border-radius: 10px;
    padding: 12px 14px;
    position: relative;
    overflow: hidden;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}
.kpi-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
}
.kpi-card.gold::before { background: #d1d5db; }
.kpi-card.blue::before { background: #d1d5db; }
.kpi-card.rose::before { background: #d1d5db; }
.kpi-label {
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #9ca3af;
    margin-bottom: 3px;
}
.kpi-value {
    font-size: 0.9rem;
    font-weight: 700;
    color: var(--text-color);
    overflow: hidden;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    line-height: 1.3;
    min-height: 2.4em;
}
.kpi-sub {
    font-size: 0.7rem;
    color: #9ca3af;
    margin-top: 2px;
}

.section-title {
    font-size: 0.78rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: #9ca3af;
    margin: 0.5rem 0 0.4rem 0;
    padding-bottom: 4px;
    border-bottom: 1px solid #f3f4f6;
}

@media (max-width: 640px) {
    .overview-grid {
        grid-template-columns: 1fr !important;
        gap: 0.5rem !important;
    }
    .dash-table { font-size: 12px !important; }
    .ai-report, .brand-bio {
        padding: 1rem 1.1rem !important;
        font-size: 13px !important;
    }
    .ov-num { font-size: 1.5rem !important; }
    .dash-title { font-size: 1.1rem !important; }
}

.dash-table { width: 100%; border-collapse: collapse; font-size: 0.78rem; }
.dash-table thead tr {
    background: var(--background-color);
    border-bottom: 2px solid #e5e7eb;
}
.dash-table th {
    padding: 7px 10px;
    text-align: left;
    font-weight: 600;
    color: #6b7280;
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    white-space: nowrap;
}
.dash-table td {
    padding: 7px 10px;
    color: var(--text-color);
    border-bottom: 1px solid #f3f4f6;
    white-space: nowrap;
}
.dash-table tbody tr:hover { background: var(--background-color); }
.dash-table .rank { color: #9ca3af; font-size: 0.72rem; }
.dash-table .name {
    color: var(--text-color); font-weight: 500;
    white-space: nowrap; max-width: 200px;
    overflow: hidden; text-overflow: ellipsis;
}
.score-bar-wrap {
    width: 46px; background: #e5e7eb; border-radius: 3px;
    height: 5px; display: inline-block;
    vertical-align: middle; margin-right: 5px;
}
.score-bar-fill {
    height: 5px; border-radius: 3px;
    background: linear-gradient(90deg, #93c5fd, #2563eb);
}
.score-val { vertical-align: middle; color: #2563eb; font-weight: 600; }
.dash-table th:last-child, .dash-table td:last-child { min-width: 110px; }

.footer-box {
    background: var(--background-color);
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    padding: 14px 18px;
    margin-top: 0.6rem;
}
.footer-box h4 {
    color: #6b7280;
    font-size: 0.9rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin: 0 0 10px 0;
}
.footer-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
}
.footer-item .fi-title {
    font-size: 0.88rem;
    font-weight: 600;
    color: var(--text-color);
    margin-bottom: 3px;
}
.footer-item .fi-weight {
    font-size: 0.78rem;
    color: #2563eb;
    margin-bottom: 3px;
}
.footer-item .fi-desc {
    font-size: 0.8rem;
    color: #6b7280;
    line-height: 1.5;
}
</style>
"""


def set_page(title: str, layout: str = "wide") -> None:
    """每个 page 文件第一行调用。Streamlit 允许子页面再调一次 set_page_config 改 title。"""
    st.set_page_config(page_title=title, page_icon="A", layout=layout)


def apply_theme() -> None:
    """注入全部主题 CSS。每个页面顶端调用一次。"""
    st.markdown(_FONT_CSS, unsafe_allow_html=True)
    st.markdown(_PALETTE_CSS, unsafe_allow_html=True)
    st.markdown(_LAYOUT_CSS, unsafe_allow_html=True)
