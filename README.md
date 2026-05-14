## 项目描述
B站智能视频下载器是一款基于 Python 后端与原生前端构建的视频下载应用，核心价值在于将视频下载功能与AI内容分析能力相结合，为用户提供智能化的视频获取体验。

### 核心功能
项目具备视频解析、智能下载、AI摘要、Cookie管理、收藏系统和历史记录六大核心功能。视频解析模块支持B站网页链接、BV链接和短链接的解析；智能下载功能实现了多级分辨率自动选择，优先获取1080P画质，同时支持Cookie认证以获取更高权限内容；AI摘要功能通过调用DeepSeek大语言模型API，自动生成视频内容摘要、关键要点和标签；Cookie管理模块能够一键从浏览器提取并验证Cookie；收藏系统和历史记录则采用JSON文件实现本地数据持久化。

### 技术架构
项目采用三层架构设计。前端层使用HTML5、CSS3和原生JavaScript构建用户界面；后端层基于Python的BaseHTTPRequestHandler实现HTTP服务，提供/api/parse、/api/summary和/api/download2等核心API接口；依赖层集成了yt-dlp用于视频解析、ffmpeg用于媒体处理、DeepSeek API用于AI摘要生成，以及browser-cookie3库用于浏览器Cookie提取。

### 特色亮点
项目具有AI驱动的内容理解能力，通过大语言模型自动分析视频元数据并生成结构化摘要，帮助用户快速判断视频价值。智能Cookie管理功能降低了高画质下载的门槛，支持Chrome、Edge、Firefox、Opera等主流浏览器的Cookie提取。同时项目具备优雅降级机制，在网络或API不可用时自动切换到本地兜底数据，保证基础功能的可用性。此外，项目集成了预编译的yt-dlp和ffmpeg二进制文件，实现零依赖开箱即用。

### 使用场景
该工具适用于个人用户下载B站视频离线观看、创作者备份自己的视频作品、学习资源的收集与整理，以及通过AI摘要快速筛选视频内容等场景。
## 项目前置部件
- 需要在.../tools/bin中安装ffmpeg和yt-dlp、fprobe组件。
- FFmpeg和fprobe ：https://ffmpeg.org/download.html#build-windows
- yt-dlp ：https://github.com/yt-dlp/yt-dlp/releases

## 启动器
- 直接双击项目根目录的 启动项目.bat，它会在项目根目录启动后端并打开浏览器。
- 如果你更习惯 PowerShell，也可以运行 启动项目.ps1。
- 本地下载依赖放在tools/bin，分别是 yt-dlp.exe、fmpeg.exe 和 fprobe.exe。

