let currentChain = "megaeth";
let currentMode = "fast";
let liveSearchEnabled = false;
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
      formData.append("live_search", liveSearchEnabled);
      options = { method: "POST", body: formData };
    } else {
      payload = {
        image_path: selectedImagePath,
        chain: currentChain,
        mode: currentMode,
        live_search: liveSearchEnabled
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

  // 4. Update Face HUD overlay if bbox exists
  if (data.face.bbox && data.face.cropped_image) {
    const box = document.getElementById("faceBoxOverlay");
    box.style.display = "block";
    box.style.left = "20%";
    box.style.top = "15%";
    box.style.width = "60%";
    box.style.height = "70%";
    document.getElementById("faceBoxLabel").textContent = `MATCH: ${(top.similarity_score * 100).toFixed(0)}%`;
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

// Live Web Search Toggle (opt-in, consumes SerpAPI quota)
function setLiveSearch(enabled) {
  liveSearchEnabled = enabled;
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

// Webcam Capture
async function triggerWebcam() {
  showScanning(true);
  showToast("Accessing hardware webcam /dev/video0...");
  try {
    const res = await fetch("/api/camera", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chain: currentChain, mode: currentMode })
    });
    const data = await res.json();
    if (data.success) {
      lastScanResult = data;
      renderScanResults(data);
      showToast("✓ Live webcam face scan verified!");
    } else {
      showToast(`Camera note: ${data.error}`);
    }
  } catch (err) {
    showToast("Could not access camera device");
  } finally {
    showScanning(false);
  }
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

function focusScanner() {
  document.getElementById("scannerCard").scrollIntoView({ behavior: "smooth" });
}

function scrollToBento() {
  document.getElementById("bentoCardSocial").scrollIntoView({ behavior: "smooth" });
}

function scrollToBlockchain() {
  document.getElementById("bentoCardBlockchain").scrollIntoView({ behavior: "smooth" });
}

function scrollToVC() {
  document.getElementById("bentoCardIdentity").scrollIntoView({ behavior: "smooth" });
}
