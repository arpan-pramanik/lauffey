let currentChain = "megaeth";
let currentMode = "fast";
let skipLiveSearch = false; // live web search is the default; checking the box opts into the free local gallery instead
let selectedImagePath = "test_images/alex_query.png";
let lastScanResult = null;
let webcamStream = null;

const CHAINS = ["megaeth", "solana", "evm"];
const CHAIN_LABELS = {
  megaeth: "MegaETH (10ms)",
  solana: "Solana (400ms)",
  evm: "EVM L2 (1s)"
};

// Initialize Application
document.addEventListener("DOMContentLoaded", () => {
  loadProfiles();
  setupDragAndDrop();
  updateChainUI();
  // Auto-run baseline demo scan with first image
  setTimeout(() => {
    executeCurrentScan();
  }, 400);
});

window.addEventListener("pagehide", () => {
  if (webcamStream) webcamStream.getTracks().forEach(track => track.stop());
});

// Load Profiles & Test Queries from Server
async function loadProfiles() {
  try {
    const res = await fetch("/api/profiles");
    const data = await res.json();
    
    const container = document.getElementById("galleryChipsContainer");
    container.innerHTML = "";

    data.test_queries.forEach((t, idx) => {
      const chip = document.createElement("div");
      chip.className = `gallery-chip ${idx === 0 ? "active" : ""}`;
      chip.dataset.path = t.path;
      chip.dataset.img = t.image_url;
      chip.dataset.name = t.subject;
      chip.innerHTML = `
        <img src="${t.image_url}" alt="${t.subject}" onerror="this.style.display='none'">
        <span>${t.subject}</span>
      `;
      chip.onclick = () => selectQuerySubject(t.path, t.image_url, chip);
      container.appendChild(chip);
    });
  } catch (err) {
    console.error("Failed to load profiles:", err);
  }
}

// Select a subject from gallery chips
function selectQuerySubject(path, imgUrl, chipElem) {
  if (webcamStream) stopWebcamStream();
  selectedImagePath = path;

  // Update active chip
  document.querySelectorAll(".gallery-chip").forEach(c => c.classList.remove("active"));
  if (chipElem) chipElem.classList.add("active");

  // Show preview
  const imgPreview = document.getElementById("imagePreview");
  imgPreview.src = imgUrl;
  imgPreview.style.display = "block";
  document.getElementById("dropzonePrompt").style.display = "none";
  document.getElementById("faceBoxOverlay").style.display = "none";

  // Trigger scan
  executeCurrentScan();
}

// Execute Biometric Scan
// fileData: a File (drag/drop or file input) or a base64 data URL string (webcam capture)
async function executeCurrentScan(fileData = null) {
  showScanning(true);

  try {
    let payload = {};
    let options = {};

    if (fileData instanceof File) {
      const formData = new FormData();
      formData.append("file", fileData);
      formData.append("chain", currentChain);
      formData.append("mode", currentMode);
      formData.append("live_search", !skipLiveSearch);
      options = { method: "POST", body: formData };
    } else if (typeof fileData === "string" && fileData.startsWith("data:")) {
      payload = {
        image_base64: fileData,
        chain: currentChain,
        mode: currentMode,
        live_search: !skipLiveSearch
      };
      options = {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      };
    } else {
      payload = {
        image_path: selectedImagePath,
        chain: currentChain,
        mode: currentMode,
        live_search: !skipLiveSearch
      };
      options = {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      };
    }

    const res = await fetch("/api/scan", options);
    const data = await res.json();

    if (!data.success) {
      showToast(`Scan Error: ${data.error}`);
      showScanning(false);
      return;
    }

    lastScanResult = data;
    renderScanResults(data);
    showToast(`✓ Provenance Verified on ${data.chain_label}`);
  } catch (err) {
    console.error("Scan error:", err);
    showToast("Pipeline error occurred during scan");
  } finally {
    showScanning(false);
  }
}

// Render Results into Bento Cards
function renderScanResults(data) {
  // 1. Identity & Liveness Attestation
  const top = data.discovery.top_match;
  const rawTitle = top.title || "Unknown Subject";
  const displayName = rawTitle.split("]")[0].replace("[", "").trim();

  document.getElementById("resIdentityName").textContent = displayName;
  document.getElementById("resLiveness").textContent = `${(data.liveness.liveness_score * 100).toFixed(1)}%`;
  document.getElementById("resAntiSpoof").textContent = data.liveness.status === "GENUINE_LIVE_SUBJECT" ? "GENUINE" : "FLAGGED";
  document.getElementById("resPHash").textContent = data.face.perceptual_hash || "N/A";
  document.getElementById("resVectorDim").textContent = `${data.face.embedding_dim}-d (${data.face.engine.split(" ")[0]})`;
  
  const geom = data.face.geometry || {};
  document.getElementById("resGeometryMetrics").textContent = 
    `Spatial: Aspect ${geom.aspect_ratio || "1.00"} | ${geom.area_px || 0} px² | Latency: ${data.total_elapsed_sec}s`;

  // 2. Discovered Social Content
  const searchModeLabel = { live: "Live Web Search", local_fallback: "Local Gallery (live search failed)", local: "Local Gallery" };
  const modeTag = searchModeLabel[data.discovery.search_mode] || "Local Gallery";
  document.getElementById("resSocialPlatform").textContent = `${top.source || "Social Web"} · ${modeTag}`;
  document.getElementById("resSocialTitle").textContent = top.title || "No social claim matched";
  document.getElementById("resSimilarity").textContent = top.similarity_score ? `${(top.similarity_score * 100).toFixed(1)}% Match` : "--";
  document.getElementById("resEngine").textContent = data.face.engine;
  
  const socialLink = document.getElementById("resSocialLink");
  if (top.link) {
    socialLink.href = top.link;
    socialLink.style.display = "inline-flex";
  } else {
    socialLink.style.display = "none";
  }

  // 3. Real-Time Blockchain Telemetry
  const bc = data.blockchain;
  document.getElementById("resChainHeader").textContent = data.chain_label;
  document.getElementById("resBlockNumber").textContent = `Block #${bc.block_number || "1"}`;
  document.getElementById("resLedgerStatus").textContent = bc.verified ? "100% UNTAMPERED" : "UNCONFIRMED";
  document.getElementById("resLatency").textContent = `${bc.block_time_ms}ms finality`;
  document.getElementById("resMerkleRoot").textContent = `Root: ${bc.merkle_root}`;
  document.getElementById("resTxHash").textContent = `TX: ${bc.tx_hash}`;

  const explorerLink = document.getElementById("resExplorerLink");
  if (bc.is_live && bc.explorer_url) {
    explorerLink.href = bc.explorer_url;
    explorerLink.style.display = "inline-flex";
  } else {
    explorerLink.style.display = "none";
  }

  // 4. Update Face HUD overlay if bbox exists
  if (data.face.bbox && data.face.cropped_image) {
    const box = document.getElementById("faceBoxOverlay");
    box.style.display = "block";
    box.style.left = "20%";
    box.style.top = "15%";
    box.style.width = "60%";
    box.style.height = "70%";
    document.getElementById("faceBoxLabel").textContent = typeof top.similarity_score === "number"
      ? `MATCH: ${(top.similarity_score * 100).toFixed(0)}%`
      : "LIVE WEB MATCH";
  }
}

// Simulate Tamper Attack
async function simulateTamperAttack() {
  if (!lastScanResult) {
    showToast("Run a scan first before testing tamper rejection!");
    return;
  }

  showToast("Testing cryptographic tamper rejection...");

  try {
    const res = await fetch("/api/tamper", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        manifest: lastScanResult.manifest,
        tx_hash: lastScanResult.blockchain.tx_hash,
        chain: currentChain
      })
    });
    const data = await res.json();

    if (data.tamper_detected) {
      alert(
        "⚡ TAMPER REJECTION VERIFIED!\n\n" +
        "A malicious actor altered the verified profile URL in the manifest.\n" +
        "Result: REJECTED_BY_BLOCKCHAIN\n" +
        "Merkle Proof Valid: False\n\n" +
        "The on-chain ledger mathematically detected and rejected the counterfeit data!"
      );
      showToast("✓ Tampered claim successfully rejected by blockchain!");
    } else {
      showToast("Tamper detection failed");
    }
  } catch (err) {
    console.error("Tamper test error:", err);
    showToast("Tamper request failed");
  }
}

// Chain Toggle
function toggleChain() {
  const nextIdx = (CHAINS.indexOf(currentChain) + 1) % CHAINS.length;
  currentChain = CHAINS[nextIdx];
  updateChainUI();
  executeCurrentScan();
}

function updateChainUI() {
  const btn = document.getElementById("chainBtnText");
  const badge = document.getElementById("activeChainBadge");
  if (btn) btn.textContent = currentChain.toUpperCase();
  if (badge) badge.textContent = `CHAIN: ${CHAIN_LABELS[currentChain]}`;
}

// Mode Toggle (Fast vs High Accuracy)
function setMode(mode) {
  currentMode = mode;
  document.getElementById("modeFastBtn").classList.toggle("active", mode === "fast");
  document.getElementById("modeHighBtn").classList.toggle("active", mode === "high");
  executeCurrentScan();
}

// Live web search is the default; checking this box opts OUT into the free local gallery
function setLiveSearch(enabled) {
  skipLiveSearch = enabled;
}

// Drag and Drop
function setupDragAndDrop() {
  const dropzone = document.getElementById("dropzone");
  
  ["dragenter", "dragover"].forEach(event => {
    dropzone.addEventListener(event, (e) => {
      e.preventDefault();
      dropzone.classList.add("dragover");
    });
  });

  ["dragleave", "drop"].forEach(event => {
    dropzone.addEventListener(event, (e) => {
      e.preventDefault();
      dropzone.classList.remove("dragover");
    });
  });

  dropzone.addEventListener("drop", (e) => {
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      handleUploadedFile(files[0]);
    }
  });
}

function handleFileSelect(event) {
  if (event.target.files.length > 0) {
    handleUploadedFile(event.target.files[0]);
  }
}

function handleUploadedFile(file) {
  if (webcamStream) stopWebcamStream();
  const reader = new FileReader();
  reader.onload = (e) => {
    const imgPreview = document.getElementById("imagePreview");
    imgPreview.src = e.target.result;
    imgPreview.style.display = "block";
    document.getElementById("dropzonePrompt").style.display = "none";
    document.getElementById("faceBoxOverlay").style.display = "none";
    
    // Clear active chip
    document.querySelectorAll(".gallery-chip").forEach(c => c.classList.remove("active"));
    
    // Run scan
    executeCurrentScan(file);
  };
  reader.readAsDataURL(file);
}

// Live Webcam Capture (real browser camera access via getUserMedia, not a
// server-side hardware call — works with whatever camera the browser grants
// permission for, and actually shows a live preview before capturing).
async function triggerWebcam() {
  if (webcamStream) return; // already active

  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    showToast("This browser does not support camera access (getUserMedia unavailable)");
    return;
  }

  try {
    webcamStream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "user", width: { ideal: 640 }, height: { ideal: 480 } },
      audio: false
    });
  } catch (err) {
    console.error("Camera access error:", err);
    showToast("Camera permission denied or no camera found");
    webcamStream = null;
    return;
  }

  const video = document.getElementById("videoPreview");
  video.srcObject = webcamStream;
  video.style.display = "block";

  document.getElementById("imagePreview").style.display = "none";
  document.getElementById("dropzonePrompt").style.display = "none";
  document.getElementById("faceBoxOverlay").style.display = "none";
  document.getElementById("cameraControls").style.display = "flex";
  document.querySelectorAll(".gallery-chip").forEach(c => c.classList.remove("active"));

  showToast("Live camera active — click Capture when ready");
}

// Grabs the current video frame, stops the stream, and runs the scan on it.
function captureWebcamPhoto() {
  const video = document.getElementById("videoPreview");
  if (!webcamStream || !video.videoWidth) {
    showToast("Camera not ready yet");
    return;
  }

  const canvas = document.createElement("canvas");
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);
  const dataUrl = canvas.toDataURL("image/jpeg", 0.92);

  // Show the captured frame before tearing down the stream — stopWebcamStream
  // checks whether an image is already showing to decide if it should bring
  // back the "drop a photo" placeholder prompt.
  const imgPreview = document.getElementById("imagePreview");
  imgPreview.src = dataUrl;
  imgPreview.style.display = "block";

  stopWebcamStream();

  executeCurrentScan(dataUrl);
}

// Stops all camera tracks and resets the dropzone back to its idle state.
function stopWebcamStream() {
  if (webcamStream) {
    webcamStream.getTracks().forEach(track => track.stop());
    webcamStream = null;
  }
  const video = document.getElementById("videoPreview");
  video.srcObject = null;
  video.style.display = "none";
  document.getElementById("cameraControls").style.display = "none";

  const hasImage = document.getElementById("imagePreview").style.display === "block";
  if (!hasImage) {
    document.getElementById("dropzonePrompt").style.display = "flex";
  }
}

// The dropzone itself opens the file picker on click, but not while a live
// camera stream is showing (that would be a confusing double-purpose click).
function handleDropzoneClick() {
  if (webcamStream) return;
  document.getElementById("fileInput").click();
}

// Copy Receipt JSON to Clipboard
function copyReceiptJSON() {
  if (!lastScanResult) {
    showToast("Run a scan first to generate a receipt");
    return;
  }
  const str = JSON.stringify(lastScanResult.manifest, null, 2);
  navigator.clipboard.writeText(str).then(() => {
    showToast("✓ Provenance Receipt JSON copied to clipboard!");
  }).catch(() => {
    showToast("Clipboard access denied");
  });
}

// UI Helpers
function showScanning(active) {
  document.getElementById("scanningBar").style.display = active ? "block" : "none";
}

function showToast(text) {
  const toast = document.getElementById("toastMsg");
  const msg = document.getElementById("toastText");
  msg.textContent = text;
  toast.style.display = "flex";
  setTimeout(() => {
    toast.style.display = "none";
  }, 3500);
}

// Card 02: open the discovered social media post from the last scan
function openSocialMatch() {
  const link = lastScanResult && lastScanResult.discovery && lastScanResult.discovery.top_match && lastScanResult.discovery.top_match.link;
  if (!link) {
    showToast("Run a scan first to discover a social match");
    return;
  }
  window.open(link, "_blank", "noopener");
}

// Card 03: open the real block explorer link if this scan anchored to a live
// chain, otherwise copy the local ledger tx hash (still genuinely re-verifiable
// via verify_receipt.py, just not on a public explorer).
function openBlockchainProof() {
  if (!lastScanResult) {
    showToast("Run a scan first to generate an on-chain proof");
    return;
  }
  const bc = lastScanResult.blockchain;
  if (bc.is_live && bc.explorer_url) {
    window.open(bc.explorer_url, "_blank", "noopener");
  } else {
    navigator.clipboard.writeText(bc.tx_hash).then(() => {
      showToast(`✓ Copied local ledger TX hash (${lastScanResult.chain} is a local simulated chain, no public explorer)`);
    }).catch(() => showToast("Clipboard access denied"));
  }
}

// Card 04: download the W3C Verifiable Credential issued for the last scan
function downloadVerifiableCredential() {
  if (!lastScanResult || !lastScanResult.verifiable_credential) {
    showToast("Run a scan first to issue a verifiable credential");
    return;
  }
  const blob = new Blob([JSON.stringify(lastScanResult.verifiable_credential, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `lauffey_credential_${lastScanResult.blockchain.tx_hash.slice(2, 12)}.json`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
  showToast("✓ W3C Verifiable Credential downloaded");
}
