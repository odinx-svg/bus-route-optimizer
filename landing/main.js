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

const setDownloadLabel = (label) => {
  [downloadTop, downloadBottom].forEach((el) => {
    if (!el) {
      return;
    }

    el.textContent = label;
  });
};

const pickPreferredAsset = (assets) => {
  const installer = assets.find((asset) => {
    const name = (asset.name || "").toLowerCase();
    return name.endsWith(".exe") && /(setup|installer|install)/i.test(name);
  });
  if (installer) {
    return { asset: installer, kind: "installer" };
  }

  const desktopExe = assets.find((asset) => {
    const name = (asset.name || "").toLowerCase();
    return name.endsWith(".exe") && /(tutti|desktop)/i.test(name);
  });
  if (desktopExe) {
    return { asset: desktopExe, kind: "portable-exe" };
  }

  const portableZip = assets.find((asset) => {
    const name = (asset.name || "").toLowerCase();
    return name.endsWith(".zip") && /(tutti|desktop)/i.test(name);
  });
  if (portableZip) {
    return { asset: portableZip, kind: "portable-zip" };
  }

  const anyZip = assets.find((asset) => /\.zip$/i.test(asset.name || ""));
  if (anyZip) {
    return { asset: anyZip, kind: "portable-zip" };
  }

  const anyExe = assets.find((asset) => /\.exe$/i.test(asset.name || ""));
  if (anyExe) {
    return { asset: anyExe, kind: "portable-exe" };
  }

  return { asset: null, kind: "none" };
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
    const { asset: preferredAsset, kind } = pickPreferredAsset(assets);

    const downloadHref = preferredAsset?.browser_download_url || release.html_url || FALLBACK_DOWNLOAD;
    const versionLabel = release.tag_name || release.name || "release";

    setDownloadHref(downloadHref);
    if (kind === "installer") {
      setDownloadLabel("Descargar instalador de Windows");
    } else {
      setDownloadLabel("Descargar TUTTI");
    }

    if (releaseBtn) {
      releaseBtn.href = release.html_url || FALLBACK_RELEASES;
    }

    if (releaseInfoEl) {
      if (!preferredAsset) {
        releaseInfoEl.textContent = `Ultima version: ${versionLabel} | Descargar desde GitHub Releases`;
      } else if (kind === "installer") {
        releaseInfoEl.textContent = `Ultima version: ${versionLabel} | Instalador: ${preferredAsset.name}`;
      } else {
        releaseInfoEl.textContent = `Ultima version: ${versionLabel} | Portable: ${preferredAsset.name}`;
      }
    }
  } catch (error) {
    setDownloadHref(FALLBACK_DOWNLOAD);
    setDownloadLabel("Descargar TUTTI");

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
