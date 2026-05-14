from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = ROOT / "frontend"
DATA_DIR = ROOT / "data"
DOWNLOADS_DIR = DATA_DIR / "downloads"
FAVORITES_FILE = DATA_DIR / "favorites.json"
HISTORY_FILE = DATA_DIR / "history.json"
COOKIES_FILE = DATA_DIR / "cookies.txt"

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "sk-c3668a2b3f184672be8dc01c473eac32").strip()
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1").rstrip("/")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

print(f"DEBUG: DEEPSEEK_API_KEY set: {len(DEEPSEEK_API_KEY) > 0}")
print(f"DEBUG: DEEPSEEK_API_KEY length: {len(DEEPSEEK_API_KEY)}")
print(f"DEBUG: DEEPSEEK_BASE_URL: {DEEPSEEK_BASE_URL}")

DATA_DIR.mkdir(exist_ok=True)
DOWNLOADS_DIR.mkdir(exist_ok=True)
_lock = threading.Lock()


def fetch_bilibili_cookies_from_browser() -> tuple[str, str]:
    """从浏览器获取B站Cookie，返回(cookies_content, error_message)"""
    try:
        import browser_cookie3
        
        cookies_content = ""
        browsers = ["chrome", "edge", "firefox", "opera", "chromium"]
        error_messages = []
        
        for browser in browsers:
            try:
                print(f"DEBUG: 尝试从 {browser} 获取Cookie...")
                if browser == "chrome":
                    cj = browser_cookie3.chrome(domain_name='bilibili.com')
                elif browser == "edge":
                    cj = browser_cookie3.edge(domain_name='bilibili.com')
                elif browser == "firefox":
                    cj = browser_cookie3.firefox(domain_name='bilibili.com')
                elif browser == "opera":
                    cj = browser_cookie3.opera(domain_name='bilibili.com')
                elif browser == "chromium":
                    cj = browser_cookie3.chromium(domain_name='bilibili.com')
                else:
                    continue
                
                # 转换为Netscape格式
                cookies_list = []
                for cookie in cj:
                    # Netscape Cookie格式: domain\tflag\tpath\tsecure\texpiration\tname\tvalue
                    domain = cookie.domain
                    flag = "TRUE" if domain.startswith('.') else "FALSE"
                    path = cookie.path
                    secure = "TRUE" if cookie.secure else "FALSE"
                    expiration = str(int(cookie.expires)) if cookie.expires else "0"
                    name = cookie.name
                    value = cookie.value
                    cookies_list.append(f"{domain}\t{flag}\t{path}\t{secure}\t{expiration}\t{name}\t{value}")
                
                if cookies_list:
                    cookies_content = "\n".join(cookies_list)
                    print(f"DEBUG: 成功从 {browser} 获取到 {len(cookies_list)} 个Cookie")
                    return cookies_content, ""
                else:
                    error_messages.append(f"{browser}: 未找到B站Cookie（请确保已登录）")
                    
            except Exception as e:
                error_msg = f"{browser}: {str(e)[:50]}"
                error_messages.append(error_msg)
                print(f"DEBUG: 从 {browser} 获取Cookie失败: {e}")
                continue
        
        error_summary = "、".join(error_messages[:3])
        return "", error_summary
    except ImportError:
        print("DEBUG: browser-cookie3 库未安装")
        return "", "browser-cookie3库未安装"
    except Exception as e:
        print(f"DEBUG: 获取Cookie时出错: {e}")
        return "", str(e)


def save_cookies_to_file(cookies_content: str) -> bool:
    """保存Cookie到文件，支持JSON和Netscape格式"""
    try:
        cookies_content = cookies_content.strip()
        lines = []

        if cookies_content.startswith("["):
            cookies_json = json.loads(cookies_content)
            for cookie in cookies_json:
                domain = cookie.get("domain", ".bilibili.com")
                flag = "TRUE" if domain.startswith(".") else "FALSE"
                path = cookie.get("path", "/")
                secure = "TRUE" if cookie.get("secure", True) else "FALSE"
                expiration = str(int(cookie.get("expirationDate", 0))) if cookie.get("expirationDate") else "0"
                name = cookie.get("name", "")
                value = cookie.get("value", "")
                lines.append(f"{domain}\t{flag}\t{path}\t{secure}\t{expiration}\t{name}\t{value}")
        else:
            for line in cookies_content.splitlines():
                line = line.strip()
                if line and (not line.startswith("#") or line.startswith("#HttpOnly_")):
                    if line.startswith("#HttpOnly_"):
                        line = line.replace("#HttpOnly_", "", 1)
                    lines.append(line)

        # 删除旧文件，确保每次都是全新创建
        if COOKIES_FILE.exists():
            COOKIES_FILE.unlink()

        with COOKIES_FILE.open("w", encoding="utf-8") as f:
            f.write("# Netscape HTTP Cookie File\n")
            f.write("# https://curl.se/rfc/cookie_spec.html\n")
            f.write("# This file was generated by bilibili video downloader\n")
            for line in lines:
                line = line.strip()
                if line and not line.startswith("#"):
                    f.write(line + "\n")
        print(f"DEBUG: Cookie已保存到 {COOKIES_FILE}")
        return True
    except Exception as e:
        print(f"DEBUG: 保存Cookie失败: {e}")
        return False


def json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def html_response(handler: BaseHTTPRequestHandler, html: str, status: int = 200) -> None:
    data = html.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_bilibili_url(url: str) -> str | None:
    text = (url or "").strip()
    if not text:
        return None
    if "b23.tv" in text:
        try:
            req = urllib.request.Request(text, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.geturl()
        except Exception:
            return text
    return text


def extract_bvid(text: str) -> str | None:
    match = re.search(r"(BV[0-9A-Za-z]+)", text or "")
    return match.group(1) if match else None


def extract_cid(html: str) -> str | None:
    match = re.search(r'"cid"\s*:\s*(\d+)', html or "")
    return match.group(1) if match else None


def fetch_html(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Referer": "https://www.bilibili.com/",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def load_json_file(path: Path, fallback):
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def save_json_file(path: Path, payload) -> None:
    with _lock:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_favorites() -> dict[str, dict]:
    return load_json_file(FAVORITES_FILE, {})


def save_favorites(favorites: dict[str, dict]) -> None:
    save_json_file(FAVORITES_FILE, favorites)


def load_history() -> list[dict]:
    data = load_json_file(HISTORY_FILE, [])
    return data if isinstance(data, list) else []


def save_history(items: list[dict]) -> None:
    save_json_file(HISTORY_FILE, items)


def push_history(item: dict) -> None:
    history = [entry for entry in load_history() if entry.get("bvid") != item.get("bvid")]
    history.insert(0, item)
    save_history(history[:20])


def demo_info(url: str) -> dict:
    bvid = extract_bvid(url) or "BVDEMO12345"
    return {
        "title": "演示视频",
        "cover": "https://dummyimage.com/1280x720/10203a/6ae4ff.png&text=AI+Preview",
        "description": "当前环境无法访问真实 B 站页面时，系统会返回演示数据。",
        "author": "演示作者",
        "duration": "03:21",
        "sourceUrl": url,
        "bvid": bvid,
        "cid": "0",
    }


def fetch_bilibili_page(url: str) -> dict:
    tools_dir = ROOT / "tools" / "bin"
    ytdlp_exe = tools_dir / "yt-dlp.exe"
    
    print(f"DEBUG: fetch_bilibili_page called with url: {url}")
    print(f"DEBUG: ytdlp_exe exists: {ytdlp_exe.exists()}, path: {ytdlp_exe}")
    
    if ytdlp_exe.exists():
        try:
            cmd = [
                str(ytdlp_exe),
                "--dump-json",
                "--no-playlist",
                "--skip-download",
                url,
            ]
            print(f"DEBUG: Running command: {' '.join(cmd)}")
            print(f"DEBUG: cwd: {tools_dir}")
            result = subprocess.run(cmd, capture_output=True, text=True, check=False, cwd=str(tools_dir))
            print(f"DEBUG: Command completed with return code: {result.returncode}")
            print(f"DEBUG: stdout length: {len(result.stdout)}")
            print(f"DEBUG: stderr: {result.stderr[:500]}")
            if result.returncode != 0:
                print(f"DEBUG: Command failed")
                raise Exception(f"Command failed with return code {result.returncode}")
            info = json.loads(result.stdout)
            print(f"DEBUG: Parsed info keys: {list(info.keys())}")
            
            title = info.get("title", "")
            
            # 优先从 thumbnails 数组获取封面
            thumbnails = info.get("thumbnails", [])
            cover = ""
            if thumbnails and isinstance(thumbnails, list) and len(thumbnails) > 0:
                cover = thumbnails[0].get("url", "")
            # 如果 thumbnails 没有，尝试 thumbnail 字段
            if not cover:
                cover = info.get("thumbnail", "")
            # 转换为 https
            cover = cover.replace("http://", "https://")
            
            description = info.get("description", "")
            author = info.get("uploader", "") or info.get("creator", "") or info.get("channel", "")
            duration = int(info.get("duration", 0))
            bvid = extract_bvid(url) or info.get("id", "") or info.get("display_id", "") or "BVUNKNOWN"
            cid = info.get("chapter_id", "0")
            
            duration_text = ""
            if duration > 0:
                if duration > 3600:
                    duration_text = f"{duration // 3600}:{(duration % 3600) // 60:02d}:{duration % 60:02d}"
                else:
                    duration_text = f"{duration // 60}:{duration % 60:02d}"
            
            result = {
                "title": title or "B站视频",
                "cover": cover if cover else "https://dummyimage.com/1280x720/10203a/6ae4ff.png&text=No+Cover",
                "description": description if description and description.strip() != "-" else "暂无简介",
                "author": author if author else "未知作者",
                "duration": duration_text if duration_text else "未知时长",
                "sourceUrl": url,
                "bvid": bvid,
                "cid": cid,
            }
            print(f"DEBUG: Returning result: {json.dumps(result, ensure_ascii=False)[:200]}...")
            return result
        except Exception as e:
            print(f"DEBUG: yt-dlp failed: {e}")
            return demo_info(url)
    
    return demo_info(url)


def build_download_page(info: dict) -> str:
    title = info.get("title", "视频下载")
    cover = info.get("cover", "")
    source_url = info.get("sourceUrl", "")
    author = info.get("author", "") or "未知作者"
    duration = info.get("duration", "") or "未知时长"
    if cover:
        proxy_cover = f'/api/proxy-image?url={urllib.parse.quote(cover)}'
        thumb_html = f'<img src="{proxy_cover}" alt="封面" onerror="this.style.display=\'none\'; this.parentElement.innerHTML=\'<div class=\'\'thumb-placeholder\'\'>AI</div>\'" />'
    else:
        thumb_html = '<div class="thumb-placeholder">AI</div>'
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>下载页 - {title}</title>
  <link rel="stylesheet" href="/styles.css" />
</head>
<body class="app-shell">
  <main class="download-page">
    <section class="hero-card">
      <div class="hero-copy">
        <p class="eyebrow">下载阶段</p>
        <h1>视频已解析，准备下载</h1>
        <p class="subtle">先确认资源，再手动点击下载。</p>
      </div>
      <div class="download-panel">
        <div class="result-card compact">
          <div class="thumb-wrap">{thumb_html}</div>
          <div class="meta-stack">
            <h2>{title}</h2>
            <p>{author}</p>
            <p>{duration}</p>
          </div>
        </div>
        <a class="btn btn-primary download-link" href="/api/download2?url={urllib.parse.quote(source_url)}">下载</a>
        <a class="btn btn-secondary" href="/">返回</a>
      </div>
    </section>
  </main>
</body>
</html>"""


def deepseek_summary(video: dict) -> dict:
    print(f"DEBUG: deepseek_summary called with video: {video.get('title', 'No title')}")
    print(f"DEBUG: DEEPSEEK_API_KEY exists: {len(DEEPSEEK_API_KEY) > 0}")
    
    if not DEEPSEEK_API_KEY or len(DEEPSEEK_API_KEY) < 10:
        print("DEBUG: No valid API key, returning fallback")
        return {
            "summary": f"《{video.get('title', '视频')}》来自 B 站，作者为 {video.get('author', '未知作者')}，时长约 {video.get('duration', '未知')}。",
            "keyPoints": [
                "当前未配置 DeepSeek API Key，先返回本地兜底摘要。",
                "后续接入字幕或转写后，可生成更准确的内容提炼。",
                "页面仍然会完整展示 AI 总结流程。",
            ],
            "oneSentence": "这是一个面向 B 站视频的智能下载与摘要页面。",
            "tags": ["B站", "下载", "摘要"],
            "status": "fallback",
        }

    prompt = (
        "请根据以下视频信息生成适合网页展示的中文结构化摘要，返回严格 JSON，"
        "字段必须包含 summary, keyPoints, oneSentence, tags。"
        "keyPoints 为 3 到 5 条，tags 为 3 到 6 个。\n"
        f"视频信息：\n- 标题：{video.get('title', '')}\n- 作者：{video.get('author', '')}\n"
        f"- 时长：{video.get('duration', '')}\n- 简介：{video.get('description', '')}"
    )
    print(f"DEBUG: Generated prompt length: {len(prompt)}")
    
    body = json.dumps(
        {
            "model": DEEPSEEK_MODEL,
            "messages": [
                {"role": "system", "content": "你是一个专业的视频内容总结助手。"},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    
    req = urllib.request.Request(
        f"{DEEPSEEK_BASE_URL}/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    
    try:
        print(f"DEBUG: Sending request to {DEEPSEEK_BASE_URL}/chat/completions")
        with urllib.request.urlopen(req, timeout=60) as resp:
            print(f"DEBUG: Response status: {resp.status}")
            raw = resp.read().decode("utf-8", errors="ignore")
        print(f"DEBUG: Response raw length: {len(raw)}")
        
        data = json.loads(raw or "{}")
        content = (((data.get("choices") or [{}])[0].get("message") or {}).get("content")) or "{}"
        print(f"DEBUG: Extracted content length: {len(content)}")
        
        try:
            parsed = json.loads(content)
            print(f"DEBUG: Successfully parsed JSON response")
        except Exception as e:
            print(f"DEBUG: Failed to parse JSON: {e}")
            print(f"DEBUG: Raw content: {content[:200]}...")
            parsed = {"summary": content, "keyPoints": [], "oneSentence": "", "tags": []}
            
        return {
            "summary": parsed.get("summary", ""),
            "keyPoints": parsed.get("keyPoints", []),
            "oneSentence": parsed.get("oneSentence", ""),
            "tags": parsed.get("tags", []),
            "status": "ok",
        }
        
    except Exception as e:
        print(f"ERROR: DeepSeek API call failed: {type(e).__name__}: {e}")
        # 返回兜底摘要
        return {
            "summary": f"《{video.get('title', '视频')}》来自 B 站，作者为 {video.get('author', '未知作者')}，时长约 {video.get('duration', '未知')}。",
            "keyPoints": [
                f"视频标题：{video.get('title', '未命名')}",
                f"UP主：{video.get('author', '未知')}",
                f"时长：{video.get('duration', '未知')}",
            ],
            "oneSentence": f"这是{video.get('author', '一位UP主')}发布的视频《{video.get('title', '未命名')}》。",
            "tags": ["B站", video.get('author', '未知').split()[0] if video.get('author') else "视频", "视频"],
            "status": "fallback",
        }


def download_with_ytdlp(source_url: str) -> tuple[Path | None, str]:
    tools_dir = ROOT / "tools" / "bin"
    ytdlp_exe = tools_dir / "yt-dlp.exe"
    ffmpeg_exe = tools_dir / "ffmpeg.exe"
    ffprobe_exe = tools_dir / "ffprobe.exe"
    ffmpeg_location = str(ffmpeg_exe) if ffmpeg_exe.exists() else ""
    
    formats = [
        "bv*[height>=1080][ext=mp4]+ba[ext=m4a]/bv*[height>=1080]+ba/b[height>=1080]/best[height>=1080]",
        "bv*[height=1080][ext=mp4]+ba[ext=m4a]/bv*[height=1080]+ba/b[height=1080]/best[height=1080]",
        "bv*[height=720][ext=mp4]+ba[ext=m4a]/bv*[height=720]+ba/b[height=720]/best[height=720]",
        "bv*[height=480][ext=mp4]+ba[ext=m4a]/bv*[height=480]+ba/b[height=480]/best[height=480]",
        "bestvideo+bestaudio/best",
    ]
    
    print(f"DEBUG: download_with_ytdlp called with URL: {source_url}")
    print(f"DEBUG: ytdlp_exe exists: {ytdlp_exe.exists()}")
    print(f"DEBUG: Cookie文件存在: {COOKIES_FILE.exists()}")
    
    if ytdlp_exe.exists():
        run_id = uuid.uuid4().hex
        run_dir = DOWNLOADS_DIR / f"run_{run_id}"
        run_dir.mkdir(parents=True, exist_ok=True)
        outtmpl = str(run_dir / "%(title).80s.%(ext)s")
        
        try:
            env = os.environ.copy()
            env["PATH"] = str(tools_dir) + os.pathsep + env.get("PATH", "")
            
            for target_format in formats:
                base_cmd = [
                    str(ytdlp_exe),
                    "--no-playlist",
                    "--format",
                    target_format,
                    "--merge-output-format",
                    "mp4",
                    "--ffmpeg-location",
                    ffmpeg_location,
                    "-o",
                    outtmpl,
                    source_url,
                ]
                
                if COOKIES_FILE.exists():
                    print(f"DEBUG: 尝试使用Cookie下载 {target_format}")
                    cmd_with_cookie = base_cmd[:1] + ["--cookies", str(COOKIES_FILE)] + base_cmd[1:]
                    result = subprocess.run(cmd_with_cookie, capture_output=True, text=True, check=False, cwd=str(DOWNLOADS_DIR), env=env)
                    print(f"DEBUG: Cookie下载返回码: {result.returncode}")
                    if result.returncode == 0:
                        candidates = [
                            path for path in run_dir.iterdir()
                            if path.is_file()
                            and path.suffix.lower() in {".mp4", ".mkv", ".webm", ".flv", ".mov"}
                            and ".f" not in path.name
                        ]
                        if candidates:
                            candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                            print(f"DEBUG: Cookie下载成功，文件: {candidates[0]}")
                            return candidates[0], ""
                    else:
                        print(f"DEBUG: Cookie下载失败: {result.stderr[:300]}")
                        if run_dir.exists():
                            for f in run_dir.iterdir():
                                if f.is_file():
                                    f.unlink()
                
                print(f"DEBUG: 尝试无Cookie下载 {target_format}")
                result = subprocess.run(base_cmd, capture_output=True, text=True, check=False, cwd=str(DOWNLOADS_DIR), env=env)
                print(f"DEBUG: 无Cookie下载返回码: {result.returncode}")
                if result.returncode == 0:
                    candidates = [
                        path for path in run_dir.iterdir()
                        if path.is_file()
                        and path.suffix.lower() in {".mp4", ".mkv", ".webm", ".flv", ".mov"}
                        and ".f" not in path.name
                    ]
                    if candidates:
                        candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                        print(f"DEBUG: 无Cookie下载成功，文件: {candidates[0]}")
                        return candidates[0], ""
                else:
                    print(f"DEBUG: 无Cookie下载失败: {result.stderr[:300]}")
                    if run_dir.exists():
                        for f in run_dir.iterdir():
                            if f.is_file():
                                f.unlink()
            
            if run_dir.exists():
                shutil.rmtree(run_dir, ignore_errors=True)
                return None, "未能获取视频，请确认视频链接有效或在 data/cookies.txt 提供有效的B站Cookie以获取1080P画质。"
        except Exception as exc:
            print(f"DEBUG: Exception occurred: {exc}")
            if run_dir.exists():
                shutil.rmtree(run_dir, ignore_errors=True)
            return None, str(exc)

    try:
        import yt_dlp  # type: ignore
    except Exception:
        return None, "yt-dlp not installed"

    outtmpl = str(DOWNLOADS_DIR / "%(title).80s.%(ext)s")
    
    for target_format in formats:
        opts = {
            "outtmpl": outtmpl,
            "format": target_format,
            "merge_output_format": "mp4",
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "ffmpeg_location": ffmpeg_location,
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(source_url, download=True)
                filename = ydl.prepare_filename(info)
                path = Path(filename)
                if path.exists() and ".f" not in path.name:
                    return path, ""
                for ext in ("mp4", "mkv", "webm", "flv", "mov"):
                    candidate = path.with_suffix(f".{ext}")
                    if candidate.exists() and ".f" not in candidate.name:
                        return candidate, ""
        except Exception:
            continue
    
    return None, "download failed"


def safe_download_name() -> str:
    return "download.mp4"


class AppHandler(BaseHTTPRequestHandler):
    def serve_static(self, relative_path: str) -> bool:
        for asset_path in [FRONTEND_DIR / relative_path.lstrip("/"), FRONTEND_DIR / "assets" / relative_path.lstrip("/")]:
            if asset_path.exists() and asset_path.is_file():
                data = asset_path.read_bytes()
                self.send_response(200)
                content_type = "text/javascript; charset=utf-8" if asset_path.suffix == ".js" else "text/css; charset=utf-8"
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return True
        return False

    def read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        return json.loads(body or "{}")

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/":
            html_response(self, read_text(FRONTEND_DIR / "index.html"))
            return
        if parsed.path == "/health":
            json_response(self, 200, {"ok": True, "service": "视频下载后端"})
            return
        if parsed.path == "/download":
            query = urllib.parse.parse_qs(parsed.query)
            source_url = normalize_bilibili_url(query.get("url", [""])[0]) or ""
            try:
                info = fetch_bilibili_page(source_url)
            except Exception:
                info = demo_info(source_url)
            html_response(self, build_download_page(info))
            return
        if parsed.path == "/api/download2":
            try:
                query = urllib.parse.parse_qs(parsed.query)
                source_url = query.get("url", [""])[0]
                if not source_url:
                    html_response(self, "<h1>缺少下载地址</h1>", 400)
                    return
                file_path, err = download_with_ytdlp(source_url)
                if file_path and file_path.exists() and file_path.is_file():
                    self.send_response(200)
                    self.send_header("Content-Type", "application/octet-stream")
                    self.send_header("Content-Disposition", f'attachment; filename="{safe_download_name()}"')
                    self.send_header("Content-Length", str(file_path.stat().st_size))
                    self.end_headers()
                    with file_path.open("rb") as fp:
                        shutil.copyfileobj(fp, self.wfile)
                    return
                html_response(self, f"<h1>下载失败</h1><p>{err or '未知错误'}</p>", 500)
            except Exception as exc:
                html_response(self, f"<h1>下载异常</h1><p>{exc}</p>", 500)
            return
        if parsed.path == "/api/proxy-image":
            try:
                query = urllib.parse.parse_qs(parsed.query)
                image_url = query.get("url", [""])[0]
                if not image_url:
                    html_response(self, "<h1>缺少图片地址</h1>", 400)
                    return
                req = urllib.request.Request(
                    image_url,
                    headers={
                        "User-Agent": "Mozilla/5.0",
                        "Referer": "https://www.bilibili.com/",
                    }
                )
                with urllib.request.urlopen(req, timeout=15) as resp:
                    content_type = resp.headers.get("Content-Type", "image/jpeg")
                    content_length = resp.headers.get("Content-Length", "")
                    self.send_response(200)
                    self.send_header("Content-Type", content_type)
                    if content_length:
                        self.send_header("Content-Length", content_length)
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    shutil.copyfileobj(resp, self.wfile)
                return
            except Exception as exc:
                html_response(self, f"<h1>图片获取失败</h1><p>{exc}</p>", 500)
            return
        if parsed.path in {"/app.js", "/styles.css"} and self.serve_static(parsed.path):
            return
        if parsed.path.startswith("/assets/") and self.serve_static(parsed.path):
            return
        if parsed.path == "/cookie-helper":
            html_response(self, read_text(FRONTEND_DIR / "cookie-helper.html"))
            return
        self.send_error(404, "Not Found")

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/parse":
            self.handle_parse()
            return
        if parsed.path == "/api/summary":
            self.handle_summary()
            return
        if parsed.path == "/api/favorites":
            self.handle_favorites()
            return
        if parsed.path == "/api/favorites/list":
            self.handle_favorites_list()
            return
        if parsed.path == "/api/history":
            self.handle_history()
            return
        if parsed.path == "/api/history/list":
            self.handle_history_list()
            return
        if parsed.path == "/api/cookies/fetch":
            self.handle_fetch_cookies()
            return
        if parsed.path == "/api/cookies/upload":
            self.handle_upload_cookies()
            return
        self.send_error(404, "Not Found")
    
    def handle_fetch_cookies(self) -> None:
        """从浏览器获取Cookie"""
        try:
            cookies_content, error_msg = fetch_bilibili_cookies_from_browser()
            if not cookies_content:
                json_response(self, 400, {
                    "ok": False,
                    "message": f"未能从浏览器获取到B站Cookie。\n\n错误信息：{error_msg}\n\n请尝试：\n1. 确保已在浏览器中登录B站\n2. 使用Chrome浏览器（推荐）\n3. 如果是Edge浏览器，请以管理员身份运行\n4. 如果以上方法都不行，请手动导出Cookie到 data/cookies.txt"
                })
                return
            
            success = save_cookies_to_file(cookies_content)
            if success:
                cookie_count = len([line for line in cookies_content.splitlines() if line and not line.startswith("#")])
                json_response(self, 200, {
                    "ok": True,
                    "message": f"成功获取 {cookie_count} 个Cookie，已保存到 data/cookies.txt，现在可以下载1080P视频了！"
                })
            else:
                json_response(self, 500, {
                    "ok": False,
                    "message": "获取Cookie成功，但保存到文件时失败，请检查文件权限。"
                })
        except ImportError:
            json_response(self, 500, {
                "ok": False,
                "message": "缺少 browser-cookie3 库，请先安装：\npip install browser-cookie3"
            })
        except Exception as exc:
            json_response(self, 500, {
                "ok": False,
                "message": f"获取Cookie时出错：{exc}"
            })

    def handle_upload_cookies(self) -> None:
        """接收上传的Cookie并保存"""
        try:
            payload = self.read_json_body()
            cookies_content = payload.get("cookies", "")
            if not cookies_content:
                json_response(self, 400, {
                    "ok": False,
                    "message": "未提供Cookie内容"
                })
                return

            valid, error_msg = validate_cookies(cookies_content)
            if not valid:
                json_response(self, 400, {
                    "ok": False,
                    "message": error_msg
                })
                return

            success = save_cookies_to_file(cookies_content)
            if success:
                cookies_content = cookies_content.strip()
                if cookies_content.startswith("["):
                    cookie_count = len(json.loads(cookies_content))
                else:
                    cookie_count = len([l for l in cookies_content.splitlines() if l and not l.startswith("#")])
                json_response(self, 200, {
                    "ok": True,
                    "message": f"成功保存 {cookie_count} 个Cookie到 data/cookies.txt，现在可以下载1080P视频了！"
                })
            else:
                json_response(self, 500, {
                    "ok": False,
                    "message": "保存Cookie失败，请检查文件权限"
                })
        except Exception as exc:
            json_response(self, 500, {
                "ok": False,
                "message": f"保存Cookie时出错：{exc}"
            })


    def handle_parse(self) -> None:
        payload = self.read_json_body()
        source_url = normalize_bilibili_url(payload.get("url", ""))
        if not source_url:
            json_response(self, 400, {"ok": False, "message": "请输入有效的 B 站视频链接。"})
            return
        if not extract_bvid(source_url):
            json_response(self, 400, {"ok": False, "message": "当前仅支持单个视频链接、BV 链接和短链接。"})
            return
        try:
            info = fetch_bilibili_page(source_url)
        except Exception:
            info = demo_info(source_url)
        info["downloadPageUrl"] = f"/download?url={urllib.parse.quote(source_url)}"
        info["ok"] = True
        info["favorite"] = load_favorites().get(info["bvid"]) is not None
        push_history(
            {
                "bvid": info.get("bvid", ""),
                "title": info.get("title", ""),
                "author": info.get("author", ""),
                "cover": info.get("cover", ""),
                "sourceUrl": info.get("sourceUrl", ""),
                "duration": info.get("duration", ""),
                "visitedAt": now_iso(),
            }
        )
        json_response(self, 200, info)

    def handle_summary(self) -> None:
        try:
            body = self.read_json_body()
            print(f"DEBUG: handle_summary received body: {body}")
            summary = deepseek_summary(body)
            print(f"DEBUG: handle_summary returning: {summary}")
            json_response(self, 200, {"ok": True, **summary})
        except Exception as e:
            print(f"ERROR: handle_summary failed: {type(e).__name__}: {e}")
            json_response(self, 500, {"ok": False, "message": str(e)})

    def handle_favorites(self) -> None:
        payload = self.read_json_body()
        action = payload.get("action")
        video = payload.get("video") or {}
        bvid = (video.get("bvid") or "").strip()
        if not bvid:
            json_response(self, 400, {"ok": False, "message": "缺少视频标识。"})
            return
        favorites = load_favorites()
        if action == "remove":
            favorites.pop(bvid, None)
            save_favorites(favorites)
            json_response(self, 200, {"ok": True, "favorited": False})
            return
        favorites[bvid] = {
            "bvid": bvid,
            "title": video.get("title", ""),
            "author": video.get("author", ""),
            "cover": video.get("cover", ""),
            "duration": video.get("duration", ""),
            "sourceUrl": video.get("sourceUrl", ""),
            "savedAt": now_iso(),
        }
        save_favorites(favorites)
        json_response(self, 200, {"ok": True, "favorited": True})

    def handle_favorites_list(self) -> None:
        items = list(load_favorites().values())
        items.sort(key=lambda item: item.get("savedAt", ""), reverse=True)
        json_response(self, 200, {"ok": True, "items": items})

    def handle_history(self) -> None:
        payload = self.read_json_body()
        video = payload.get("video") or {}
        bvid = (video.get("bvid") or "").strip()
        if not bvid:
            json_response(self, 400, {"ok": False, "message": "缺少视频标识。"})
            return
        push_history(
            {
                "bvid": bvid,
                "title": video.get("title", ""),
                "author": video.get("author", ""),
                "cover": video.get("cover", ""),
                "duration": video.get("duration", ""),
                "sourceUrl": video.get("sourceUrl", ""),
                "visitedAt": now_iso(),
            }
        )
        json_response(self, 200, {"ok": True})

    def handle_history_list(self) -> None:
        json_response(self, 200, {"ok": True, "items": load_history()})


def validate_cookies(cookies_content: str) -> tuple[bool, str]:
    """验证Cookie是否包含必要的认证信息"""
    cookies_content = cookies_content.strip()
    required_cookies = ["SESSDATA", "bili_jct", "DedeUserID"]
    missing = required_cookies.copy()

    if cookies_content.startswith("["):
        try:
            cookies_json = json.loads(cookies_content)
            cookie_names = [c.get("name", "") for c in cookies_json]
            for required in required_cookies:
                if required in cookie_names and required in missing:
                    missing.remove(required)
        except:
            return False, "Cookie格式错误，无法解析JSON"
    else:
        for line in cookies_content.splitlines():
            line = line.strip()
            if line and (not line.startswith("#") or line.startswith("#HttpOnly_")):
                if line.startswith("#HttpOnly_"):
                    line = line.replace("#HttpOnly_", "", 1)
                parts = line.split("\t")
                if len(parts) >= 6:
                    name = parts[5]
                    if name in required_cookies and name in missing:
                        missing.remove(name)

    if missing:
        return False, f"缺少必要的登录凭证: {', '.join(missing)}，请确保已登录B站账号后重新导出Cookie"
    return True, ""


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 8000), AppHandler)
    print("Server running on http://127.0.0.1:8000", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
