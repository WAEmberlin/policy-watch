/**
 * Shared stream / YouTube embed helpers for CivicWatch pages.
 */
const CivicWatchStreamUtils = (() => {
    const YOUTUBE_RE = /(?:youtube\.com\/(?:watch\?(?:[^&]+&)*v=|embed\/|live\/)|youtu\.be\/)([A-Za-z0-9_-]{6,})/i;

    function isYouTubeUrl(url) {
        if (!url) return false;
        return /youtube\.com|youtu\.be/i.test(url);
    }

    function extractYouTubeVideoId(url) {
        if (!url) return "";
        const m = url.match(YOUTUBE_RE);
        return m ? m[1] : "";
    }

    function youtubeEmbedUrl(videoId, autoplay) {
        if (!videoId) return "";
        const params = autoplay ? "?autoplay=1&playsinline=1" : "";
        return `https://www.youtube.com/embed/${videoId}${params}`;
    }

    function resolveHearingStream(hearing) {
        if (!hearing) return null;

        const streamUrl = hearing.stream_url || hearing.streamUrl || "";
        const link = hearing.link || hearing.url || "";
        const embedUrl = hearing.embed_url || hearing.embedUrl || "";
        const videoId = hearing.youtube_video_id || extractYouTubeVideoId(streamUrl) || extractYouTubeVideoId(link);

        if (embedUrl) {
            return {
                type: "embed",
                embedUrl,
                watchUrl: streamUrl || link || embedUrl,
                videoId: videoId || "",
            };
        }

        if (videoId) {
            return {
                type: "youtube",
                embedUrl: youtubeEmbedUrl(videoId),
                watchUrl: streamUrl || link || `https://www.youtube.com/watch?v=${videoId}`,
                videoId,
            };
        }

        const livestreamId = hearing.livestream_id || hearing.livestreamId;
        if (livestreamId) {
            return {
                type: "livestream",
                livestreamId,
                watchUrl: `livestreams.html#${livestreamId}`,
            };
        }

        const externalWatch = streamUrl || (link && !/leg\.colorado\.gov\/bills|openstates\.org/i.test(link) ? link : "");
        if (externalWatch) {
            return {
                type: "external",
                watchUrl: externalWatch,
            };
        }

        return null;
    }

    function renderStreamActions(stream, options = {}) {
        if (!stream) return "";
        const compact = options.compact;
        const hearingTitle = options.hearingTitle || "";
        const watchLabel = options.watchLabel
            || (stream.type === "external" ? "Watch live" : "Watch on YouTube");
        const playLabel = options.playLabel || "▶ Play here";
        const playAriaLabel = hearingTitle
            ? `Play hearing stream here: ${hearingTitle}`
            : "Play hearing stream here";

        let watchBtn = "";
        if (stream.watchUrl && stream.type !== "livestream") {
            watchBtn = `<a href="${stream.watchUrl}" target="_blank" rel="noopener noreferrer"
                class="inline-flex items-center gap-1 px-3 py-1.5 bg-red-600 hover:bg-red-700 text-white rounded-lg text-sm font-medium transition-colors">
                ${watchLabel}
            </a>`;
        } else if (stream.type === "livestream" && stream.watchUrl) {
            watchBtn = `<a href="${stream.watchUrl}"
                class="inline-flex items-center gap-1 px-3 py-1.5 bg-sky-600 hover:bg-sky-700 text-white rounded-lg text-sm font-medium transition-colors">
                Open live streams
            </a>`;
        }

        let playBtn = "";
        if (stream.embedUrl) {
            playBtn = `<button type="button"
                class="hearing-play-btn inline-flex items-center gap-1 px-3 py-1.5 bg-civic-blue hover:bg-civic-blue-dark text-white rounded-lg text-sm font-medium transition-colors"
                data-embed-url="${stream.embedUrl}"
                aria-label="${playAriaLabel}">
                ${playLabel}
            </button>`;
        } else if (stream.livestreamId) {
            playBtn = `<button type="button"
                class="hearing-play-livestream-btn inline-flex items-center gap-1 px-3 py-1.5 bg-civic-blue hover:bg-civic-blue-dark text-white rounded-lg text-sm font-medium transition-colors"
                data-livestream-id="${stream.livestreamId}"
                aria-label="Open live stream page${hearingTitle ? ': ' + hearingTitle : ''}">
                ${playLabel}
            </button>`;
        }

        if (!watchBtn && !playBtn) return "";

        const wrapClass = compact
            ? "flex flex-wrap gap-2 mt-3"
            : "flex flex-wrap gap-2 mt-3 pt-3 border-t border-slate-200";

        return `<div class="${wrapClass}">${watchBtn}${playBtn}</div>`;
    }

    function renderInlinePlayer(embedUrl, title) {
        if (!embedUrl) return "";
        const iframeTitle = title || "Hearing live stream";
        const sep = embedUrl.includes("?") ? "&" : "?";
        return `
            <div class="hearing-embed mt-3 rounded-xl overflow-hidden border border-slate-200 bg-slate-900">
                <div class="relative pb-[56.25%] h-0">
                    <iframe class="absolute inset-0 w-full h-full" src="${embedUrl}${sep}autoplay=1&playsinline=1"
                        title="${iframeTitle}" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                        allowfullscreen loading="lazy"></iframe>
                </div>
            </div>`;
    }

    return {
        isYouTubeUrl,
        extractYouTubeVideoId,
        youtubeEmbedUrl,
        resolveHearingStream,
        renderStreamActions,
        renderInlinePlayer,
    };
})();
