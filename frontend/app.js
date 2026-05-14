const $ = (id) => document.getElementById(id);

const parseBtn = $("parseBtn");
const videoUrl = $("videoUrl");
const result = $("result");
const summaryArea = $("summaryArea");
const errorBox = $("errorBox");
const downloadPage = $("downloadPage");
const favoriteBtn = $("favoriteBtn");
const favoritesPanel = $("favoritesPanel");
const favoritesList = $("favoritesList");
const refreshFavoritesBtn = $("refreshFavoritesBtn");
const historyPanel = $("historyPanel");
const historyList = $("historyList");
const refreshHistoryBtn = $("refreshHistoryBtn");
const favoriteCount = $("favoriteCount");
const historyCount = $("historyCount");
const summaryState = $("summaryState");
const title = $("title");
const author = $("author");
const duration = $("duration");
const description = $("description");
const cover = $("cover");
const oneSentence = $("oneSentence");
const keyPoints = $("keyPoints");
const tags = $("tags");
const summaryStatus = $("summaryStatus");
const fetchCookiesBtn = $("fetchCookiesBtn");

let currentVideo = null;
let currentFavorite = false;

const show = (node) => node.classList.remove("hidden");
const hide = (node) => node.classList.add("hidden");

function showError(message) {
  errorBox.textContent = message;
  show(errorBox);
}

function clearError() {
  errorBox.textContent = "";
  hide(errorBox);
}

function setLoading(isLoading) {
  parseBtn.disabled = isLoading;
  parseBtn.textContent = isLoading ? "解析中..." : "解析视频";
  summaryStatus.textContent = isLoading ? "正在请求解析结果..." : summaryStatus.textContent;
}

function setFavoriteButtonState(isFavorite) {
  currentFavorite = isFavorite;
  favoriteBtn.textContent = isFavorite ? "移出收藏夹" : "加入收藏夹";
}

function setEmptyCard(container, text) {
  container.innerHTML = `<div class="empty-card">${text}</div>`;
}

function renderSummary(data) {
  show(summaryArea);
  const statusText = data.status === "fallback" ? "本地兜底" : "DeepSeek 完成";
  summaryStatus.innerHTML = `<span class="status-dot"></span><span>${statusText}</span>`;
  keyPoints.innerHTML = "";
  (data.keyPoints || []).forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item;
    keyPoints.appendChild(li);
  });
  tags.innerHTML = "";
  (data.tags || []).forEach((tag) => {
    const span = document.createElement("span");
    span.className = "tag-pill";
    span.textContent = tag;
    tags.appendChild(span);
  });
}

async function refreshFavorites() {
  const response = await fetch("/api/favorites/list", { method: "POST" });
  const data = await response.json();
  if (!response.ok || !data.ok) throw new Error(data.message || "收藏夹获取失败");
  const items = data.items || [];
  favoriteCount.textContent = String(items.length);
  favoritesList.innerHTML = "";
  if (items.length === 0) {
    setEmptyCard(favoritesList, "收藏夹里还没有内容，先把喜欢的视频加入进来吧。");
    show(favoritesPanel);
    return;
  }
  items.forEach((item) => {
    const card = document.createElement("article");
    card.className = "favorite-card";
    
    const coverUrl = item.cover ? `/api/proxy-image?url=${encodeURIComponent(item.cover)}` : "";
    
    card.innerHTML = `
      <div class="favorite-cover">
        ${coverUrl ? `<img src="${coverUrl}" alt="封面">` : '<div class="cover-placeholder">视频封面</div>'}
        ${item.duration ? `<span class="duration-badge">${item.duration}</span>` : ''}
      </div>
      <div class="favorite-meta">
        <h4 class="favorite-title">${item.title || "未命名视频"}</h4>
        <p class="favorite-author">
          <span class="author-icon">UP</span>
          ${item.author || "未知作者"}
        </p>
      </div>
      <button class="btn btn-secondary" type="button">移出收藏夹</button>
    `;
    
    card.querySelector("button").addEventListener("click", async (e) => {
      e.stopPropagation();
      await toggleFavorite(item);
      await refreshFavorites();
    });
    
    card.addEventListener("click", () => {
      if (item.sourceUrl) {
        const downloadUrl = `/download?url=${encodeURIComponent(item.sourceUrl)}`;
        window.location.href = downloadUrl;
      }
    });
    
    favoritesList.appendChild(card);
  });
  show(favoritesPanel);
}

async function refreshHistory() {
  const response = await fetch("/api/history/list", { method: "POST" });
  const data = await response.json();
  if (!response.ok || !data.ok) throw new Error(data.message || "历史记录获取失败");
  const items = data.items || [];
  historyCount.textContent = String(items.length);
  historyList.innerHTML = "";
  if (items.length === 0) {
    setEmptyCard(historyList, "最近还没有浏览过视频，先解析一个链接试试吧。");
    show(historyPanel);
    return;
  }
  items.forEach((item) => {
    const card = document.createElement("article");
    card.className = "history-card";
    
    const coverUrl = item.cover ? `/api/proxy-image?url=${encodeURIComponent(item.cover)}` : "";
    
    card.innerHTML = `
      <div class="history-cover">
        ${coverUrl ? `<img src="${coverUrl}" alt="封面">` : '<div class="cover-placeholder">视频封面</div>'}
        ${item.duration ? `<span class="duration-badge">${item.duration}</span>` : ''}
      </div>
      <div class="history-meta">
        <h4 class="history-title">${item.title || "未命名视频"}</h4>
        <p class="history-author">
          <span class="author-icon">UP</span>
          ${item.author || "未知作者"}
        </p>
      </div>
    `;
    
    card.addEventListener("click", () => {
      if (item.sourceUrl) {
        const downloadUrl = `/download?url=${encodeURIComponent(item.sourceUrl)}`;
        window.location.href = downloadUrl;
      }
    });
    
    historyList.appendChild(card);
  });
  show(historyPanel);
}

async function toggleFavorite(video) {
  const action = currentFavorite ? "remove" : "add";
  const response = await fetch("/api/favorites", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action, video }),
  });
  const data = await response.json();
  if (!response.ok || !data.ok) throw new Error(data.message || "收藏操作失败");
  setFavoriteButtonState(Boolean(data.favorited));
}

parseBtn.addEventListener("click", async () => {
  clearError();
  hide(result);
  hide(summaryArea);
  const url = videoUrl.value.trim();
  if (!url) {
    showError("请先输入 B 站视频链接。");
    return;
  }

  setLoading(true);
  try {
    const parseResponse = await fetch("/api/parse", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
    const parseData = await parseResponse.json();
    if (!parseResponse.ok || !parseData.ok) throw new Error(parseData.message || "解析失败");

    currentVideo = parseData;
    setFavoriteButtonState(Boolean(parseData.favorite));
    title.textContent = parseData.title || "-";
    author.textContent = parseData.author ? `UP 主：${parseData.author}` : "UP 主：未知";
    duration.textContent = parseData.duration ? `时长：${parseData.duration}` : "时长：未知";
    description.textContent = parseData.description || "暂无简介";
    if (parseData.cover) {
      const proxyUrl = `/api/proxy-image?url=${encodeURIComponent(parseData.cover)}`;
      cover.innerHTML = `<img src="${proxyUrl}" alt="封面">`;
      cover.querySelector('img').onerror = function() {
        cover.innerHTML = "AI";
        cover.classList.remove("thumb-wrap");
        cover.classList.add("thumb-placeholder");
      };
      cover.classList.remove("thumb-placeholder");
      cover.classList.add("thumb-wrap");
    } else {
      cover.innerHTML = "AI";
      cover.classList.remove("thumb-wrap");
      cover.classList.add("thumb-placeholder");
    }
    downloadPage.href = parseData.downloadPageUrl || "#";
    show(result);

    await fetch("/api/history", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ video: parseData }),
    });
    await refreshHistory();

    summaryStatus.textContent = "正在生成 AI 摘要...";
    const summaryResponse = await fetch("/api/summary", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: parseData.title,
        author: parseData.author,
        duration: parseData.duration,
        description: parseData.description,
      }),
    });
    const summaryData = await summaryResponse.json();
    if (!summaryResponse.ok || !summaryData.ok) throw new Error(summaryData.message || "AI 总结失败");
    renderSummary(summaryData);
  } catch (error) {
    showError(error.message || "发生未知错误");
    summaryStatus.textContent = "总结失败，请重试";
    summaryState.textContent = "待重试";
  } finally {
    setLoading(false);
  }
});

favoriteBtn.addEventListener("click", async () => {
  try {
    if (!currentVideo) {
      showError("请先解析一个视频再收藏。");
      return;
    }
    await toggleFavorite(currentVideo);
  } catch (error) {
    showError(error.message || "收藏操作失败");
  }
});

refreshFavoritesBtn.addEventListener("click", async () => {
  try {
    await refreshFavorites();
  } catch (error) {
    showError(error.message || "收藏夹刷新失败");
  }
});

refreshHistoryBtn.addEventListener("click", async () => {
  try {
    await refreshHistory();
  } catch (error) {
    showError(error.message || "历史记录刷新失败");
  }
});

fetchCookiesBtn.addEventListener("click", async () => {
  try {
    clearError();
    fetchCookiesBtn.disabled = true;
    fetchCookiesBtn.textContent = "获取中...";

    const response = await fetch("/api/cookies/fetch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    });
    const data = await response.json();

    if (!response.ok || !data.ok) {
      throw new Error(data.message || "获取Cookie失败");
    }

    alert(data.message);
  } catch (error) {
    showError(error.message || "获取Cookie时发生错误");
  } finally {
    fetchCookiesBtn.disabled = false;
    fetchCookiesBtn.textContent = "从浏览器获取Cookie";
  }
});

refreshFavorites().catch(() => {});
refreshHistory().catch(() => {});
