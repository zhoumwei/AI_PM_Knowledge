"""配置模块 - 服务器、TTS、缓存等配置"""

import os
from pathlib import Path

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent

# 服务器配置
HOST = "127.0.0.1"
PORT = 8899

# TTS 配置
DEFAULT_VOICE = "zh-CN-XiaoxiaoNeural"    # 晓晓（女声，自然亲切）
DEFAULT_RATE = "+0%"                        # 语速：-50% 慢 ~ +100% 快
DEFAULT_VOLUME = "+0%"                      # 音量

# 缓存配置
CACHE_DIR = BASE_DIR / ".tts_cache"
CACHE_MAX_SIZE_MB = 500                      # 缓存上限 500MB

# Edge-TTS 中文语音列表
CHINESE_VOICES = [
    {"id": "zh-CN-XiaoxiaoNeural",   "name": "晓晓",   "gender": "女", "desc": "自然亲切，通用场景"},
    {"id": "zh-CN-YunxiNeural",      "name": "云希",   "gender": "男", "desc": "沉稳大气，专业讲解"},
    {"id": "zh-CN-YunyangNeural",    "name": "云扬",   "gender": "男", "desc": "清晰明亮，新闻播报"},
    {"id": "zh-CN-XiaoyiNeural",     "name": "晓伊",   "gender": "女", "desc": "温柔甜美，轻松场景"},
    {"id": "zh-CN-YunjianNeural",    "name": "云健",   "gender": "男", "desc": "浑厚有力，体育解说"},
    {"id": "zh-CN-XiaohanNeural",    "name": "晓涵",   "gender": "女", "desc": "知性优雅，纪录片"},
    {"id": "zh-CN-XiaomengNeural",   "name": "晓梦",   "gender": "女", "desc": "活泼可爱，儿童内容"},
    {"id": "zh-CN-XiaoqiuNeural",    "name": "晓秋",   "gender": "女", "desc": "成熟稳重，商业场景"},
    {"id": "zh-CN-XiaoruiNeural",    "name": "晓睿",   "gender": "女", "desc": "沉稳睿智，专业客服"},
    {"id": "zh-CN-XiaoshuangNeural", "name": "晓双",   "gender": "女", "desc": "童声，儿童故事"},
    {"id": "zh-CN-XiaoxuanNeural",   "name": "晓萱",   "gender": "女", "desc": "活泼俏皮，年轻风格"},
    {"id": "zh-CN-XiaoyanNeural",    "name": "晓颜",   "gender": "女", "desc": "标准女声，通用"},
    {"id": "zh-CN-XiaozhenNeural",   "name": "晓臻",   "gender": "女", "desc": "端庄大方，正式场合"},
    {"id": "zh-CN-YunfengNeural",    "name": "云枫",   "gender": "男", "desc": "温文尔雅，知识科普"},
    {"id": "zh-CN-YunhaoNeural",     "name": "云皓",   "gender": "男", "desc": "活力阳光，运动场景"},
    {"id": "zh-CN-YunxiaNeural",     "name": "云夏",   "gender": "男", "desc": "年轻男声，轻松活泼"},
    {"id": "zh-CN-YunyeNeural",      "name": "云野",   "gender": "男", "desc": "磁性低沉，叙事"},
]

# 文本分段配置
MAX_SEGMENT_LENGTH = 200    # 单段最大字符数，超出则按句子拆分
