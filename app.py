import os
import json
import streamlit as st
import requests
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# ==================== 配置 ====================
MODEL_NAME = "qwen-plus"

# 优先从 Streamlit secrets 读，其次从环境变量读
def get_secret(key, default=None):
    try:
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.getenv(key, default)

API_KEY = get_secret("DASHSCOPE_API_KEY")
BASE_URL = get_secret("DASHSCOPE_BASE_URL",
                     "https://dashscope.aliyuncs.com/compatible-mode/v1")
GAODE_API_KEY = get_secret("GAODE_API_KEY")

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)


# ==================== 1. 天气工具函数 ====================
def get_weather(city: str, extensions: str = "base") -> str:
    """
    根据城市名称查询高德天气。
    :param city: 城市名称，例如："北京"、"上海"、"杭州"
    :param extensions: base=实况天气（默认），all=未来预报天气
    """
    url = "https://restapi.amap.com/v3/weather/weatherInfo"
    params = {
        "key": GAODE_API_KEY,
        "city": city,
        "extensions": extensions,
    }
    try:
        response = requests.get(url, params=params, timeout=5)
        data = response.json()

        if data.get("status") != "1":
            return f"查询天气失败，高德接口返回提示：{data.get('info', '未知错误')}"

        if extensions == "base":
            lives = data.get("lives", [])
            if not lives:
                return "未查询到该城市的实况天气。"
            live = lives[0]
            province = live.get("province", "")
            city_name = live.get("city", "")
            weather = live.get("weather", "")
            temperature = live.get("temperature", "")
            winddirection = live.get("winddirection", "")
            windpower = live.get("windpower", "")
            humidity = live.get("humidity", "")
            reporttime = live.get("reporttime", "")
            return (
                f"{province}{city_name}当前天气：{weather}，"
                f"气温 {temperature}℃，{winddirection}风 {windpower}级，"
                f"相对湿度 {humidity}%，发布时间 {reporttime}。"
            )
        else:
            forecasts = data.get("forecasts", [])
            if not forecasts:
                return "未查询到该城市的预报天气。"
            city_name = forecasts[0].get("city", "")
            casts = forecasts[0].get("casts", [])
            if not casts:
                return "未查询到该城市的预报天气。"

            lines = [f"{city_name}未来天气预报："]
            for c in casts:
                date = c.get("date", "")
                dayweather = c.get("dayweather", "")
                nightweather = c.get("nightweather", "")
                daytemp = c.get("daytemp", "")
                nighttemp = c.get("nighttemp", "")
                daywind = c.get("daywind", "")
                daypower = c.get("daypower", "")
                lines.append(
                    f"  {date}：白天{dayweather} {daytemp}℃，"
                    f"夜间{nightweather} {nighttemp}℃，"
                    f"{daywind}风 {daypower}级"
                )
            return "\n".join(lines)

    except requests.exceptions.RequestException as e:
        return f"请求高德天气接口时发生网络异常：{str(e)}"


# ==================== 2. 工具映射表 ====================
FUNCTION_MAP = {
    "get_weather": get_weather,
}


# ==================== 3. 工具 Schema ====================
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "根据城市名称查询该城市的天气，可查实况或未来预报。",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "城市名称，例如：北京、上海、杭州",
                    },
                    "extensions": {
                        "type": "string",
                        "enum": ["base", "all"],
                        "description": (
                            "base=实况天气（默认，适合问“今天/现在天气”）；"
                            "all=未来预报天气（适合问“未来几天/明天天气”）"
                        ),
                    },
                },
                "required": ["city"],
            },
        },
    }
]

SYSTEM_PROMPT = (
    "你是一个乐于助人的天气助手，可以根据用户需求调用天气工具回答问题。"
    "如果用户问的是当前天气，用 extensions=base；"
    "如果用户问的是未来天气或预报，用 extensions=all。"
    "回答时用简洁自然的中文，可以适当加入一点生活化建议。"
)


# ==================== 4. 页面设置 ====================
st.set_page_config(
    page_title="嘉豪天气查询",
    page_icon="🌤️",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# 移动端友好的 CSS
st.markdown(
    """
    <style>
        .block-container { padding-top: 1.2rem; padding-bottom: 6rem; }
        h1 { font-size: 1.5rem !important; }
        .stChatMessage { border-radius: 12px; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🌤️ 嘉豪天气查询")
st.caption("问问我天气吧，例如「杭州今天天气」或「北京未来三天天气」")

# 侧边栏：清空按钮 + 常用城市快捷入口
with st.sidebar:
    st.header("设置")
    st.caption("嘉豪天气查询 · 由通义千问驱动")

    if st.button("🗑️ 清空对话", use_container_width=True):
        st.session_state.messages = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
        st.rerun()

    st.divider()
    st.subheader("快捷提问")
    quick_queries = [
        "杭州今天天气怎么样？",
        "北京未来三天天气如何？",
        "上海现在天气怎么样？",
        "广州明天会下雨吗？",
    ]
    for q in quick_queries:
        if st.button(q, use_container_width=True, key=f"quick_{q}"):
            st.session_state.pending_query = q
            st.rerun()


# ==================== 5. 会话初始化 ====================
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]

# 渲染历史（跳过 system）
for m in st.session_state.messages:
    if m["role"] == "user" and m.get("content"):
        with st.chat_message("user"):
            st.write(m["content"])
    elif m["role"] == "assistant" and m.get("content"):
        with st.chat_message("assistant"):
            st.write(m["content"])


# ==================== 6. 核心处理函数 ====================
def handle_query(query: str):
    """把一条用户消息走一遍完整的 LLM + 工具流程，并返回最终回答。"""
    st.session_state.messages.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.write(query)

    with st.chat_message("assistant"):
        with st.spinner("思考中…"):
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=st.session_state.messages,
                tools=tools,
                tool_choice="auto",
            )
            msg = response.choices[0].message

            if msg.tool_calls:
                st.session_state.messages.append(msg)

                with st.expander(f"🔧 调用 {len(msg.tool_calls)} 个工具", expanded=False):
                    for tc in msg.tool_calls:
                        fn_name = tc.function.name
                        fn_args = json.loads(tc.function.arguments)
                        st.write(f"**{fn_name}** `{fn_args}`")

                        if fn_name in FUNCTION_MAP:
                            result = FUNCTION_MAP[fn_name](**fn_args)
                        else:
                            result = f"Error: 函数 {fn_name} 未定义"
                        st.write(f"↳ {result}")

                        st.session_state.messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "name": fn_name,
                            "content": result,
                        })

                final = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=st.session_state.messages,
                )
                answer = final.choices[0].message.content
            else:
                answer = msg.content

            st.write(answer)
            st.session_state.messages.append(
                {"role": "assistant", "content": answer}
            )


# ==================== 7. 输入 ====================
if "pending_query" in st.session_state and st.session_state.pending_query:
    q = st.session_state.pending_query
    st.session_state.pending_query = None
    handle_query(q)

query = st.chat_input("输入你的问题…")
if query:
    handle_query(query)