"use strict";

const videos = Array.from(document.querySelectorAll("video"));
const formatTime = (seconds) => {
  if (!Number.isFinite(seconds)) return "--:--";
  const value = Math.max(0, Math.floor(seconds));
  return `${Math.floor(value / 60)}:${String(value % 60).padStart(2, "0")}`;
};

document.querySelectorAll("[data-player]").forEach((section) => {
  const video = section.querySelector("video");
  const play = section.querySelector("[data-play]");
  const clock = section.querySelector("[data-clock]");
  const seek = section.querySelector("[data-seek]");
  const status = section.querySelector("[data-status]");
  const error = section.querySelector("[data-error]");
  const title = section.dataset.title;

  const update = () => {
    clock.textContent = `${formatTime(video.currentTime)} / ${formatTime(video.duration)}`;
    if (Number.isFinite(video.duration) && video.duration > 0 && document.activeElement !== seek) {
      seek.value = String(Math.round((video.currentTime / video.duration) * 1000));
    }
    play.textContent = video.paused ? "▶ 播放" : "Ⅱ 暂停";
    play.setAttribute("aria-label", `${video.paused ? "播放" : "暂停"}${title}`);
  };

  const start = async () => {
    error.hidden = true;
    videos.forEach((other) => { if (other !== video) other.pause(); });
    if (video.ended) video.currentTime = 0;
    try {
      await video.play();
    } catch {
      status.textContent = "尚未开始";
      error.textContent = "请点击视频中的播放按钮；也可以下载 MP4 在本机播放器打开。";
      error.hidden = false;
    }
  };

  play.addEventListener("click", () => { if (video.paused) start(); else video.pause(); });
  section.querySelector("[data-restart]").addEventListener("click", () => { video.currentTime = 0; start(); });
  section.querySelectorAll("[data-skip]").forEach((button) => button.addEventListener("click", () => {
    if (Number.isFinite(video.duration)) {
      video.currentTime = Math.max(0, Math.min(video.duration, video.currentTime + Number(button.dataset.skip)));
      update();
    }
  }));
  seek.addEventListener("input", () => {
    if (Number.isFinite(video.duration)) video.currentTime = (Number(seek.value) / 1000) * video.duration;
  });
  section.querySelector("[data-rate]").addEventListener("change", (event) => {
    video.playbackRate = Number(event.target.value);
  });

  video.addEventListener("loadedmetadata", () => { status.textContent = "点击播放"; update(); });
  video.addEventListener("timeupdate", update);
  video.addEventListener("play", () => { status.textContent = "正在播放"; update(); });
  video.addEventListener("pause", () => { status.textContent = video.ended ? "播放结束" : "已暂停"; update(); });
  video.addEventListener("ended", () => { status.textContent = "播放结束"; update(); });
  video.addEventListener("waiting", () => { status.textContent = "正在缓冲"; });
  video.addEventListener("playing", () => { status.textContent = "正在播放"; });
  video.addEventListener("error", () => {
    status.textContent = "暂时无法播放";
    error.textContent = "视频未能加载，请刷新重试，或通过“下载 MP4”在本机查看。";
    error.hidden = false;
  });
  if (video.readyState >= 1) { status.textContent = "点击播放"; update(); }
});
