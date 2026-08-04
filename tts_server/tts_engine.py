"""TTS 引擎模块 - 基于 edge-tts 的语音合成，带文件缓存"""

import hashlib
from pathlib import Path
from typing import AsyncIterator, Optional

import edge_tts

from .config import CACHE_DIR, CACHE_MAX_SIZE_MB, DEFAULT_RATE, DEFAULT_VOLUME


class TTSEngine:
    """语音合成引擎，支持文本到语音转换和缓存"""

    def __init__(self):
        self.cache_dir = Path(CACHE_DIR)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_key(self, text: str, voice: str, rate: str) -> str:
        """生成缓存文件名"""
        raw = f"{text}|{voice}|{rate}"
        return hashlib.md5(raw.encode('utf-8')).hexdigest()

    def _cache_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.mp3"

    def get_cached(self, text: str, voice: str, rate: str) -> Optional[Path]:
        """获取缓存的音频文件路径，不存在返回 None"""
        path = self._cache_path(self._cache_key(text, voice, rate))
        return path if path.exists() else None

    async def synthesize(
        self,
        text: str,
        voice: str,
        rate: str = DEFAULT_RATE,
        volume: str = DEFAULT_VOLUME,
    ) -> Path:
        """合成语音并缓存，返回音频文件路径"""
        key = self._cache_key(text, voice, rate)
        cache_path = self._cache_path(key)

        # 命中缓存
        if cache_path.exists():
            return cache_path

        # 调用 edge-tts 合成，先写临时文件，成功后再进入缓存。
        temp_path = cache_path.with_suffix(".tmp.mp3")
        communicate = edge_tts.Communicate(text, voice, rate=rate, volume=volume)
        try:
            await communicate.save(str(temp_path))
            temp_path.replace(cache_path)
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise
        return cache_path

    async def synthesize_stream(
        self,
        text: str,
        voice: str,
        rate: str = DEFAULT_RATE,
        volume: str = DEFAULT_VOLUME,
    ) -> AsyncIterator[bytes]:
        """流式合成语音，逐块返回音频数据（不缓存）"""
        communicate = edge_tts.Communicate(text, voice, rate=rate, volume=volume)
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                yield chunk["data"]

    def cleanup_cache(self):
        """清理超出上限的缓存文件（LRU 策略）"""
        files = list(self.cache_dir.glob("*.mp3"))
        if not files:
            return

        total_size = sum(f.stat().st_size for f in files)
        max_bytes = CACHE_MAX_SIZE_MB * 1024 * 1024

        if total_size <= max_bytes:
            return

        # 按最后修改时间排序，删除最旧的
        files.sort(key=lambda f: f.stat().st_mtime)
        while total_size > max_bytes and files:
            oldest = files.pop(0)
            total_size -= oldest.stat().st_size
            oldest.unlink(missing_ok=True)

    def get_cache_stats(self) -> dict:
        """获取缓存统计信息"""
        files = list(self.cache_dir.glob("*.mp3"))
        total_size = sum(f.stat().st_size for f in files) if files else 0
        return {
            "file_count": len(files),
            "total_size_mb": round(total_size / 1024 / 1024, 2),
            "max_size_mb": CACHE_MAX_SIZE_MB,
        }
