const REPO_OWNER = "odinx-svg";
const REPO_NAME = "bus-route-optimizer";
const FALLBACK_RELEASES = `https://github.com/${REPO_OWNER}/${REPO_NAME}/releases`;
const FALLBACK_DOWNLOAD = `${FALLBACK_RELEASES}/latest`;

const releaseInfoEl = document.getElementById("releaseInfo");
const releaseBtn = document.getElementById("releaseBtn");
const downloadTop = document.getElementById("downloadBtn");
const downloadBottom = document.getElementById("downloadBtnBottom");
const yearEl = document.getElementById("year");

const setDownloadHref = (href) => {
  [downloadTop, downloadBottom].forEach((el) => {
    if (!el) {
      return;
    }

    el.href = href;
  });
};

const applyLatestRelease = async () => {
  try {
    const response = await fetch(`https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/releases/latest`, {
      headers: {
        Accept: "application/vnd.github+json",
      },
    });

    if (!response.ok) {
      throw new Error(`GitHub API status: ${response.status}`);
    }

    const release = await response.json();
    const assets = Array.isArray(release.assets) ? release.assets : [];

    const preferredAsset =
      assets.find((asset) => /tutti|desktop/i.test(asset.name || "") && /\.zip$/i.test(asset.name || "")) ||
      assets.find((asset) => /\.zip$/i.test(asset.name || ""));

    const downloadHref = preferredAsset?.browser_download_url || release.html_url || FALLBACK_DOWNLOAD;
    const versionLabel = release.tag_name || release.name || "release";

    setDownloadHref(downloadHref);

    if (releaseBtn) {
      releaseBtn.href = release.html_url || FALLBACK_RELEASES;
    }

    if (releaseInfoEl) {
      releaseInfoEl.textContent = preferredAsset
        ? `Ultima version: ${versionLabel} | Archivo: ${preferredAsset.name}`
        : `Ultima version: ${versionLabel} | Descargar desde GitHub Releases`;
    }
  } catch (error) {
    setDownloadHref(FALLBACK_DOWNLOAD);

    if (releaseBtn) {
      releaseBtn.href = FALLBACK_RELEASES;
    }

    if (releaseInfoEl) {
      releaseInfoEl.textContent = "No se pudo leer GitHub API. Usando enlace de releases.";
    }

    // Keep console trace for troubleshooting if needed.
    console.error("Failed loading latest release", error);
  }
};

if (yearEl) {
  yearEl.textContent = String(new Date().getFullYear());
}

applyLatestRelease();
