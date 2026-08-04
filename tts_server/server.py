"""Web 服务器 - aiohttp 异步服务器，提供 API 和静态文件服务"""

import logging
import os
import re
from pathlib import Path

from aiohttp import web

from .config import BASE_DIR, CHINESE_VOICES, DEFAULT_RATE, DEFAULT_VOICE, HOST, PORT, MAX_SEGMENT_LENGTH
from .markdown_parser import markdown_to_text, split_into_segments
from .tts_engine import TTSEngine

logger = logging.getLogger("tts_server")

# 全局 TTS 引擎实例
tts_engine = TTSEngine()
VALID_VOICE_IDS = {voice["id"] for voice in CHINESE_VOICES}
RATE_RE = re.compile(r"^[+-](?:[0-9]|[1-9][0-9]|100)%$")
MAX_TTS_TEXT_LENGTH = 1000


def normalize_tts_params(text: str, voice: str, rate: str) -> tuple[str, str, str]:
    """校验并归一化 TTS 参数。"""
    text = text.strip()
    if not text:
        raise ValueError("缺少 text 参数")
    if len(text) > MAX_TTS_TEXT_LENGTH:
        raise ValueError(f"text 过长，最多 {MAX_TTS_TEXT_LENGTH} 字")
    if voice not in VALID_VOICE_IDS:
        voice = DEFAULT_VOICE
    if not RATE_RE.match(rate):
        rate = DEFAULT_RATE
    return text, voice, rate


def scan_markdown_files() -> dict:
    """扫描知识库中所有 markdown 文件，返回按目录分组的树形结构"""
    result = []
    for root, dirs, files in os.walk(BASE_DIR):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']
        for f in files:
            if f.endswith('.md'):
                full_path = Path(root) / f
                rel_path = full_path.relative_to(BASE_DIR)
                result.append({
                    "path": str(rel_path),
                    "name": f,
                    "dir": str(Path(rel_path).parent) if str(Path(rel_path).parent) != '.' else '根目录',
                })
    result.sort(key=lambda x: x['path'])

    tree = {}
    for f in result:
        tree.setdefault(f['dir'], []).append(f)
    return {"tree": tree, "total": len(result)}


async def handle_index(request: web.Request) -> web.Response:
    """返回主页面"""
    html_path = BASE_DIR / "static" / "index.html"
    if not html_path.exists():
        return web.Response(text="index.html not found", status=404)
    return web.FileResponse(html_path)


async def handle_static(request: web.Request) -> web.Response:
    """处理静态文件请求"""
    filename = request.match_info['filename']
    file_path = BASE_DIR / "static" / filename
    if not file_path.exists() or not file_path.is_file():
        return web.Response(text="Not found", status=404)
    return web.FileResponse(file_path)


async def handle_list_files(request: web.Request) -> web.Response:
    """API: 获取文件列表"""
    data = scan_markdown_files()
    return web.json_response(data)


async def handle_list_voices(request: web.Request) -> web.Response:
    """API: 获取可用语音列表"""
    return web.json_response({"voices": CHINESE_VOICES, "default": DEFAULT_VOICE})


async def handle_get_doc(request: web.Request) -> web.Response:
    """API: 获取文档内容，返回分段后的文本列表"""
    path = request.query.get("path", "")
    if not path:
        return web.json_response({"error": "缺少 path 参数"}, status=400)

    full_path = (BASE_DIR / path).resolve()
    # 安全检查
    try:
        full_path.relative_to(BASE_DIR.resolve())
    except ValueError:
        return web.json_response({"error": "非法路径"}, status=403)

    if not full_path.exists() or full_path.suffix != '.md':
        return web.json_response({"error": "文件不存在"}, status=404)

    try:
        content = full_path.read_text(encoding='utf-8')
    except Exception as e:
        return web.json_response({"error": f"读取失败: {e}"}, status=500)

    plain_text = markdown_to_text(content)
    segments = split_into_segments(plain_text, MAX_SEGMENT_LENGTH)

    return web.json_response({
        "path": path,
        "name": full_path.name,
        "segment_count": len(segments),
        "total_chars": sum(segment["length"] for segment in segments),
        "segments": segments,
    })


async def handle_tts_stream(request: web.Request) -> web.StreamResponse:
    """API: 流式 TTS 合成，返回 audio/mp3 流"""
    text = request.query.get("text", "")
    voice = request.query.get("voice", DEFAULT_VOICE)
    rate = request.query.get("rate", DEFAULT_RATE)

    try:
        text, voice, rate = normalize_tts_params(text, voice, rate)
    except ValueError as e:
        return web.json_response({"error": str(e)}, status=400)

    response = web.StreamResponse(
        status=200,
        headers={
            "Content-Type": "audio/mpeg",
            "Cache-Control": "no-cache",
            "Access-Control-Allow-Origin": "*",
        },
    )
    await response.prepare(request)

    try:
        async for chunk in tts_engine.synthesize_stream(text, voice, rate):
            await response.write(chunk)
    except Exception as e:
        logger.error(f"TTS 合成失败: {e}")

    await response.write_eof()
    return response


async def handle_tts_cached(request: web.Request) -> web.Response:
    """API: 缓存式 TTS 合成，返回完整音频文件，支持 Range 请求"""
    text = request.query.get("text", "")
    voice = request.query.get("voice", DEFAULT_VOICE)
    rate = request.query.get("rate", DEFAULT_RATE)

    try:
        text, voice, rate = normalize_tts_params(text, voice, rate)
    except ValueError as e:
        return web.json_response({"error": str(e)}, status=400)

    try:
        # 检查缓存或合成
        cached = tts_engine.get_cached(text, voice, rate)
        if cached:
            logger.info(f"缓存命中: {cached.name}")
            audio_path = cached
        else:
            audio_path = await tts_engine.synthesize(text, voice, rate)
            logger.info(f"合成完成: {audio_path.name} ({audio_path.stat().st_size} bytes)")

        # 读取文件内容
        data = audio_path.read_bytes()
        total = len(data)

        # 处理 Range 请求（HTML5 Audio 会发送）
        range_header = request.headers.get("Range")
        if range_header:
            # 解析 "bytes=0-1023" 或 "bytes=0-"
            range_spec = range_header.replace("bytes=", "")
            parts = range_spec.split("-")
            start = int(parts[0]) if parts[0] else 0
            end = int(parts[1]) if parts[1] and parts[1] else total - 1
            end = min(end, total - 1)
            chunk = data[start:end + 1]
            return web.Response(
                body=chunk,
                status=206,
                headers={
                    "Content-Type": "audio/mpeg",
                    "Content-Range": f"bytes {start}-{end}/{total}",
                    "Content-Length": str(len(chunk)),
                    "Accept-Ranges": "bytes",
                },
            )

        # 无 Range 请求，返回完整文件
        return web.Response(
            body=data,
            status=200,
            headers={
                "Content-Type": "audio/mpeg",
                "Content-Length": str(total),
                "Accept-Ranges": "bytes",
            },
        )
    except Exception as e:
        logger.error(f"TTS 合成失败: {e}")
        return web.json_response({"error": f"合成失败: {e}"}, status=500)


async def handle_cache_stats(request: web.Request) -> web.Response:
    """API: 获取缓存统计"""
    tts_engine.cleanup_cache()
    stats = tts_engine.get_cache_stats()
    return web.json_response(stats)


def create_app() -> web.Application:
    """创建 aiohttp 应用"""
    app = web.Application()

    # 路由
    app.router.add_get("/", handle_index)
    app.router.add_get("/static/{filename}", handle_static)
    app.router.add_get("/api/files", handle_list_files)
    app.router.add_get("/api/voices", handle_list_voices)
    app.router.add_get("/api/doc", handle_get_doc)
    app.router.add_get("/api/tts/stream", handle_tts_stream)
    app.router.add_get("/api/tts/cached", handle_tts_cached)
    app.router.add_get("/api/cache/stats", handle_cache_stats)

    return app


def main():
    """启动服务器"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    app = create_app()
    logger.info(f"AI 产品经理知识库 - 语音播放服务启动中...")
    logger.info(f"访问地址: http://localhost:{PORT}")
    logger.info(f"默认语音: {DEFAULT_VOICE}")
    web.run_app(app, host=HOST, port=PORT, print=None)
