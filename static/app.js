/**
 * AI 产品经理知识库 - 语音播放前端
 * 使用 Edge-TTS 高质量中文语音，支持缓存、预加载、断点续播和段落高亮。
 */

const STORAGE_KEY = 'ai-pm-tts-player';
const MAX_RETRIES = 2;

const state = {
    voices: [],
    segments: [],
    currentIndex: 0,
    currentFile: null,
    currentFileName: '',
    currentVoice: '',
    isPlaying: false,
    isPaused: false,
    isLoadingAudio: false,
    hasFinished: false,
    audio: null,
    playbackId: 0,
    preloading: new Set(),
};

const $ = (id) => document.getElementById(id);
const el = {
    fileList: $('fileList'),
    searchBox: $('searchBox'),
    playerTitle: $('playerTitle'),
    playerInfo: $('playerInfo'),
    playBtn: $('playBtn'),
    pauseBtn: $('pauseBtn'),
    stopBtn: $('stopBtn'),
    prevBtn: $('prevBtn'),
    nextBtn: $('nextBtn'),
    voiceSelect: $('voiceSelect'),
    speedSelect: $('speedSelect'),
    docViewer: $('docViewer'),
    toast: $('toast'),
    progressFill: $('progressFill'),
    preloadIndicator: $('preloadIndicator'),
};

function loadPrefs() {
    try {
        return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
    } catch {
        return {};
    }
}

function savePrefs(patch) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...loadPrefs(), ...patch }));
}

function showToast(message, duration = 2000) {
    el.toast.textContent = message;
    el.toast.classList.add('show');
    clearTimeout(showToast.timer);
    showToast.timer = setTimeout(() => el.toast.classList.remove('show'), duration);
}

function buildTtsUrl(text, voice, rate) {
    const params = new URLSearchParams({ text, voice, rate });
    return `/api/tts/cached?${params}`;
}

function getCurrentRate() {
    return el.speedSelect.value || '+0%';
}

function setButtonContent(button, icon, label) {
    button.innerHTML = `<span>${icon}</span><span>${label}</span>`;
}

async function loadFileList() {
    try {
        const res = await fetch('/api/files');
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        renderFileList(data.tree || {});
    } catch (error) {
        console.error(error);
        showToast('加载文件列表失败');
    }
}

function renderFileList(tree) {
    el.fileList.innerHTML = '';
    Object.keys(tree).forEach((dirName) => {
        const group = document.createElement('div');
        group.className = 'file-group';

        const title = document.createElement('div');
        title.className = 'file-group-title';
        title.textContent = `${dirName} (${tree[dirName].length})`;
        group.appendChild(title);

        tree[dirName].forEach((file) => {
            const item = document.createElement('div');
            item.className = 'file-item';
            item.dataset.path = file.path;
            item.dataset.name = file.name;

            const name = document.createElement('span');
            name.className = 'file-name';
            name.textContent = file.name.replace(/\.md$/, '');
            item.appendChild(name);

            const btn = document.createElement('button');
            btn.className = 'play-btn';
            btn.innerHTML = '&#9654;';
            btn.title = '播放';
            btn.addEventListener('click', (event) => {
                event.stopPropagation();
                handleFilePlay(file, btn);
            });
            item.appendChild(btn);

            item.addEventListener('click', () => loadDoc(file.path, item));
            group.appendChild(item);
        });
        el.fileList.appendChild(group);
    });
}

el.searchBox.addEventListener('input', () => {
    const query = el.searchBox.value.trim().toLowerCase();
    document.querySelectorAll('.file-item').forEach((item) => {
        const matched = item.dataset.name.toLowerCase().includes(query)
            || item.dataset.path.toLowerCase().includes(query);
        item.style.display = matched ? '' : 'none';
    });
});

async function loadVoices() {
    try {
        const res = await fetch('/api/voices');
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        const prefs = loadPrefs();

        state.voices = data.voices || [];
        state.currentVoice = prefs.voice || data.default;

        el.voiceSelect.innerHTML = '';
        state.voices.forEach((voice) => {
            const option = document.createElement('option');
            option.value = voice.id;
            option.textContent = `${voice.name}（${voice.gender}）- ${voice.desc}`;
            el.voiceSelect.appendChild(option);
        });

        if (!state.voices.some((voice) => voice.id === state.currentVoice)) {
            state.currentVoice = data.default;
        }
        el.voiceSelect.value = state.currentVoice;

        if (prefs.rate) {
            el.speedSelect.value = prefs.rate;
        }
    } catch (error) {
        console.error(error);
        showToast('加载语音列表失败');
    }
}

el.voiceSelect.addEventListener('change', () => {
    state.currentVoice = el.voiceSelect.value;
    savePrefs({ voice: state.currentVoice });
    if (state.isPlaying) {
        playFrom(state.currentIndex);
    }
});

async function loadDoc(path, itemEl) {
    stopPlayback({ keepIndex: false, silent: true });
    document.querySelectorAll('.file-item').forEach((item) => item.classList.remove('active'));
    if (itemEl) itemEl.classList.add('active');

    el.docViewer.innerHTML = '<div class="doc-placeholder"><div class="spinner"></div><div>加载中...</div></div>';
    state.segments = [];
    state.currentFile = null;
    state.currentFileName = '';
    state.currentIndex = 0;
    state.hasFinished = false;
    updateUI();

    try {
        const res = await fetch(`/api/doc?path=${encodeURIComponent(path)}`);
        const data = await res.json();
        if (!res.ok || data.error) {
            el.docViewer.innerHTML = `<div class="doc-placeholder"><div>${data.error || '加载失败'}</div></div>`;
            return false;
        }

        state.currentFile = path;
        state.currentFileName = data.name;
        state.segments = data.segments || [];
        state.currentIndex = 0;

        el.playerTitle.textContent = data.name;
        el.playerInfo.textContent = `${data.segment_count} 段 · ${data.total_chars || 0} 字`;
        renderSegments(state.segments);
        updateProgress();
        updateUI();
        return true;
    } catch (error) {
        console.error(error);
        el.docViewer.innerHTML = '<div class="doc-placeholder"><div>加载失败</div></div>';
        updateUI();
        return false;
    }
}

function renderSegments(segments) {
    el.docViewer.innerHTML = '';
    if (!segments.length) {
        el.docViewer.innerHTML = '<div class="doc-placeholder"><div>文档没有可朗读内容</div></div>';
        return;
    }

    segments.forEach((segment, index) => {
        const div = document.createElement('div');
        div.className = 'segment';
        div.id = `seg-${index}`;
        div.textContent = segment.text;
        div.title = '点击从这里开始播放';

        const meta = document.createElement('span');
        meta.className = 'segment-meta';
        meta.textContent = `第 ${index + 1} 段 · ${segment.length} 字`;
        div.appendChild(meta);

        div.addEventListener('click', () => playFrom(index));
        el.docViewer.appendChild(div);
    });
}

async function handleFilePlay(file, button) {
    if (state.currentFile === file.path && state.isPlaying) {
        pausePlayback();
        return;
    }

    if (state.currentFile !== file.path) {
        const loaded = await loadDoc(file.path, button.closest('.file-item'));
        if (!loaded) return;
    }
    playFrom(state.currentFile === file.path ? state.currentIndex : 0);
}

async function playFrom(index) {
    if (!state.segments.length) return;
    const safeIndex = Math.min(Math.max(index, 0), state.segments.length - 1);

    state.playbackId += 1;
    const sessionId = state.playbackId;
    state.currentIndex = safeIndex;
    state.isPlaying = true;
    state.isPaused = false;
    state.hasFinished = false;
    updateUI();

    await playSegment(safeIndex, sessionId, 0);
}

async function playSegment(index, sessionId, retryCount) {
    if (sessionId !== state.playbackId) return;
    if (index >= state.segments.length) {
        finishPlayback();
        return;
    }

    state.currentIndex = index;
    state.isLoadingAudio = true;
    markSegmentState(index, 'loading');
    highlightSegment(index);
    updateProgress();
    updateUI();

    const segment = state.segments[index];
    const url = buildTtsUrl(segment.text, state.currentVoice, getCurrentRate());

    try {
        releaseAudio();
        const audio = new Audio(url);
        audio.preload = 'auto';
        state.audio = audio;

        audio.oncanplay = () => {
            if (sessionId !== state.playbackId) return;
            state.isLoadingAudio = false;
            markSegmentState(index);
            updateUI();
        };

        audio.onended = () => {
            if (sessionId !== state.playbackId) return;
            state.isLoadingAudio = false;
            markSegmentPlayed(index);
            preloadNext(index + 1);
            setTimeout(() => playSegment(index + 1, sessionId, 0), 180);
        };

        audio.onerror = () => {
            if (sessionId !== state.playbackId) return;
            retryOrSkip(index, sessionId, retryCount);
        };

        await audio.play();
        state.isLoadingAudio = false;
        markSegmentState(index);
        updateUI();
    } catch (error) {
        if (sessionId !== state.playbackId) return;
        console.error(`段 ${index + 1} 播放异常:`, error);
        retryOrSkip(index, sessionId, retryCount);
    }
}

function retryOrSkip(index, sessionId, retryCount) {
    state.isLoadingAudio = false;
    markSegmentState(index, 'error');
    if (retryCount < MAX_RETRIES) {
        showToast(`第 ${index + 1} 段合成中，正在重试`);
        setTimeout(() => playSegment(index, sessionId, retryCount + 1), 1200);
        return;
    }
    showToast(`第 ${index + 1} 段播放失败，已跳过`);
    setTimeout(() => playSegment(index + 1, sessionId, 0), 500);
}

async function preloadNext(nextIndex) {
    if (nextIndex >= state.segments.length || state.preloading.has(nextIndex)) return;
    state.preloading.add(nextIndex);
    updatePreloadIndicator();
    try {
        const segment = state.segments[nextIndex];
        await fetch(buildTtsUrl(segment.text, state.currentVoice, getCurrentRate()));
    } catch (error) {
        console.warn(`第 ${nextIndex + 1} 段预加载失败`, error);
    } finally {
        state.preloading.delete(nextIndex);
        updatePreloadIndicator();
    }
}

function releaseAudio() {
    if (!state.audio) return;
    state.audio.pause();
    state.audio.removeAttribute('src');
    state.audio.load();
    state.audio = null;
}

function highlightSegment(index) {
    document.querySelectorAll('.segment.highlight').forEach((segment) => {
        segment.classList.remove('highlight');
    });
    const segment = document.getElementById(`seg-${index}`);
    if (segment) {
        segment.classList.add('highlight');
        segment.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
}

function markSegmentState(index, className = '') {
    const segment = document.getElementById(`seg-${index}`);
    if (!segment) return;
    segment.classList.remove('loading', 'error');
    if (className) segment.classList.add(className);
}

function markSegmentPlayed(index) {
    const segment = document.getElementById(`seg-${index}`);
    if (segment) {
        segment.classList.remove('loading', 'error');
        segment.classList.add('played');
    }
}

function resetPlayedSegments() {
    document.querySelectorAll('.segment.played, .segment.loading, .segment.error').forEach((segment) => {
        segment.classList.remove('played', 'loading', 'error');
    });
}

function updateProgress() {
    const total = state.segments.length;
    const progress = total ? ((state.currentIndex + (state.hasFinished ? 1 : 0)) / total) * 100 : 0;
    el.progressFill.style.width = `${Math.min(progress, 100)}%`;
    if (total) {
        const status = state.isLoadingAudio ? '合成中' : state.isPaused ? '已暂停' : state.isPlaying ? '播放中' : '已就绪';
        el.playerInfo.textContent = `${status} · ${state.currentIndex + 1} / ${total} 段`;
    }
}

function updateFileButtons() {
    document.querySelectorAll('.play-btn').forEach((button) => {
        const item = button.closest('.file-item');
        const isCurrent = item?.dataset.path === state.currentFile;
        button.classList.toggle('playing', Boolean(isCurrent && state.isPlaying && !state.isPaused));
        button.classList.toggle('loading', Boolean(isCurrent && state.isLoadingAudio));
        button.innerHTML = isCurrent && state.isPlaying && !state.isPaused ? '&#10074;&#10074;' : '&#9654;';
        button.title = isCurrent && state.isPlaying ? '暂停' : '播放';
    });
}

function updatePreloadIndicator() {
    el.preloadIndicator.classList.toggle('show', state.preloading.size > 0);
}

function updateUI() {
    const hasDoc = state.segments.length > 0;
    el.playBtn.disabled = !hasDoc || state.isLoadingAudio;
    el.pauseBtn.disabled = !state.isPlaying || state.isLoadingAudio;
    el.stopBtn.disabled = !state.isPlaying && !state.isPaused;
    el.prevBtn.disabled = !hasDoc || state.currentIndex === 0 || state.isLoadingAudio;
    el.nextBtn.disabled = !hasDoc || state.currentIndex >= state.segments.length - 1 || state.isLoadingAudio;

    if (state.isLoadingAudio) {
        el.playBtn.classList.add('loading');
        setButtonContent(el.playBtn, '<span class="spinner"></span>', '合成中');
    } else {
        el.playBtn.classList.remove('loading');
        setButtonContent(el.playBtn, '&#9654;', state.hasFinished ? '重播' : '播放');
    }

    setButtonContent(el.pauseBtn, state.isPaused ? '&#9654;' : '&#10074;&#10074;', state.isPaused ? '继续' : '暂停');
    updateFileButtons();
}

function stopPlayback(options = {}) {
    const { keepIndex = true, silent = false } = options;
    state.playbackId += 1;
    state.isPlaying = false;
    state.isPaused = false;
    state.isLoadingAudio = false;
    state.hasFinished = false;
    releaseAudio();
    document.querySelectorAll('.segment.highlight').forEach((segment) => segment.classList.remove('highlight'));
    document.querySelectorAll('.segment.loading, .segment.error').forEach((segment) => {
        segment.classList.remove('loading', 'error');
    });
    if (!keepIndex) {
        state.currentIndex = 0;
        el.progressFill.style.width = '0%';
        resetPlayedSegments();
    }
    updateProgress();
    updateUI();
    if (!silent) showToast('已停止');
}

function pausePlayback() {
    if (!state.audio || state.isLoadingAudio) return;
    if (state.audio.paused) {
        state.audio.play();
        state.isPlaying = true;
        state.isPaused = false;
        showToast('继续播放');
    } else {
        state.audio.pause();
        state.isPlaying = true;
        state.isPaused = true;
        showToast('已暂停');
    }
    updateProgress();
    updateUI();
}

function finishPlayback() {
    state.isPlaying = false;
    state.isPaused = false;
    state.isLoadingAudio = false;
    state.hasFinished = true;
    releaseAudio();
    document.querySelectorAll('.segment.highlight').forEach((segment) => segment.classList.remove('highlight'));
    el.progressFill.style.width = '100%';
    updateUI();
    showToast('播放完成');
}

el.playBtn.addEventListener('click', () => {
    if (!state.segments.length) return;
    if (state.hasFinished) {
        resetPlayedSegments();
        playFrom(0);
        return;
    }
    playFrom(state.currentIndex);
});
el.pauseBtn.addEventListener('click', pausePlayback);
el.stopBtn.addEventListener('click', () => stopPlayback());
el.prevBtn.addEventListener('click', () => {
    if (state.currentIndex > 0) playFrom(state.currentIndex - 1);
});
el.nextBtn.addEventListener('click', () => {
    if (state.currentIndex < state.segments.length - 1) playFrom(state.currentIndex + 1);
});
el.speedSelect.addEventListener('change', () => {
    savePrefs({ rate: getCurrentRate() });
    if (state.isPlaying) {
        playFrom(state.currentIndex);
    }
});

document.addEventListener('keydown', (event) => {
    if (event.target.matches('input, select, textarea')) return;
    if (event.code === 'Space') {
        event.preventDefault();
        if (state.isPlaying) pausePlayback();
        else if (state.segments.length) playFrom(state.currentIndex);
    }
    if (event.code === 'ArrowLeft' && state.currentIndex > 0) {
        playFrom(state.currentIndex - 1);
    }
    if (event.code === 'ArrowRight' && state.currentIndex < state.segments.length - 1) {
        playFrom(state.currentIndex + 1);
    }
});

window.addEventListener('beforeunload', () => releaseAudio());

loadFileList();
loadVoices();
updateUI();
