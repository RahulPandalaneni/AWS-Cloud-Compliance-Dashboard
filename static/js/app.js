/**
 * AWS Cloud Compliance Dashboard - Frontend Controller
 * Handles live data fetching, CRR status updates, search/filtering, and error handling.
 */

document.addEventListener("DOMContentLoaded", () => {
    // State management
    let state = {
        complianceData: null,
        currentFilter: "all",
        searchQuery: "",
        isLoading: false,
    };

    // DOM Elements
    const elements = {
        refreshBtn: document.getElementById("refresh-btn"),
        lastUpdatedText: document.getElementById("last-updated-text"),
        dataSourceBadge: document.getElementById("data-source-badge"),
        dataSourceText: document.getElementById("data-source-text"),
        sidebarConnectionPill: document.getElementById("sidebar-connection-pill"),
        sidebarConnectionText: document.getElementById("sidebar-connection-text"),

        // Alert banner
        alertBanner: document.getElementById("aws-alert-banner"),
        alertTitle: document.getElementById("alert-title"),
        alertMessage: document.getElementById("alert-message"),
        bannerActionBtn: document.getElementById("banner-action-btn"),

        // Metric Cards
        compliantCount: document.getElementById("compliant-count"),
        complianceRate: document.getElementById("compliance-rate"),
        compliantSubtext: document.getElementById("compliant-subtext"),
        nonCompliantCount: document.getElementById("non-compliant-count"),
        nonCompliantSubtext: document.getElementById("non-compliant-subtext"),
        warningsCount: document.getElementById("warnings-count"),
        warningsSubtext: document.getElementById("warnings-subtext"),
        resourcesCount: document.getElementById("resources-count"),
        resourcesSubtext: document.getElementById("resources-subtext"),

        // CRR Pipeline
        pipelineStatusBadge: document.getElementById("pipeline-status-badge"),
        pipelineStatusText: document.getElementById("pipeline-status-text"),
        connectorSyncBadge: document.getElementById("connector-sync-badge"),
        connectorTransferDesc: document.getElementById("connector-transfer-desc"),

        // Source Bucket Card
        sourceBucketName: document.getElementById("source-bucket-name"),
        sourceVersioning: document.getElementById("source-versioning"),
        sourceReplication: document.getElementById("source-replication"),
        sourcePab: document.getElementById("source-pab"),
        sourceEncryption: document.getElementById("source-encryption"),
        sourceObjects: document.getElementById("source-objects"),
        sourceBytes: document.getElementById("source-bytes"),
        sourceLiveTag: document.getElementById("source-live-tag"),

        // Dest Bucket Card
        destBucketName: document.getElementById("dest-bucket-name"),
        destVersioning: document.getElementById("dest-versioning"),
        destReplication: document.getElementById("dest-replication"),
        destPab: document.getElementById("dest-pab"),
        destEncryption: document.getElementById("dest-encryption"),
        destObjects: document.getElementById("dest-objects"),
        destBytes: document.getElementById("dest-bytes"),
        destLiveTag: document.getElementById("dest-live-tag"),

        // Table
        tableBody: document.getElementById("table-body"),
        tableSearch: document.getElementById("table-search"),
        filterTabs: document.querySelectorAll(".filter-tab"),
        tableRecordCount: document.getElementById("table-record-count"),

        // Modal
        setupModal: document.getElementById("setup-modal"),
        openSetupModalBtn: document.getElementById("open-setup-modal-btn"),
        closeModalBtn: document.getElementById("close-modal-btn"),
        modalCancelBtn: document.getElementById("modal-cancel-btn"),
        modalTestBtn: document.getElementById("modal-test-btn"),
        modalStatusText: document.getElementById("modal-status-text"),
    };

    // Initialize
    initEventListeners();
    fetchComplianceData();

    // Auto-refresh every 30 seconds
    setInterval(() => {
        if (!state.isLoading) {
            fetchComplianceData(true);
        }
    }, 30000);

    function initEventListeners() {
        // Manual refresh button
        elements.refreshBtn.addEventListener("click", () => {
            fetchComplianceData();
        });

        // Search bar
        elements.tableSearch.addEventListener("input", (e) => {
            state.searchQuery = e.target.value.toLowerCase().trim();
            renderTable();
        });

        // Filter tabs
        elements.filterTabs.forEach((tab) => {
            tab.addEventListener("click", () => {
                elements.filterTabs.forEach((t) => t.classList.remove("active"));
                tab.classList.add("active");
                state.currentFilter = tab.dataset.filter;
                renderTable();
            });
        });

        // Setup modal controls
        elements.openSetupModalBtn.addEventListener("click", () => openModal());
        elements.bannerActionBtn.addEventListener("click", () => openModal());
        elements.closeModalBtn.addEventListener("click", () => closeModal());
        elements.modalCancelBtn.addEventListener("click", () => closeModal());

        // Close modal when clicking outside
        elements.setupModal.addEventListener("click", (e) => {
            if (e.target === elements.setupModal) {
                closeModal();
            }
        });

        // Test connection button in modal
        elements.modalTestBtn.addEventListener("click", async () => {
            elements.modalStatusText.textContent = "Testing AWS STS & S3 authorization...";
            elements.modalStatusText.style.color = "#3b82f6";

            try {
                const res = await fetch("/api/status");
                const data = await res.json();
                if (data.connected) {
                    elements.modalStatusText.textContent = `Connected! ${data.message}`;
                    elements.modalStatusText.style.color = "#10b981";
                    fetchComplianceData();
                } else {
                    elements.modalStatusText.textContent = `Failed: ${data.message || data.error_code}`;
                    elements.modalStatusText.style.color = "#ef4444";
                }
            } catch (err) {
                elements.modalStatusText.textContent = `Network error: ${err.message}`;
                elements.modalStatusText.style.color = "#ef4444";
            }
        });
    }

    function openModal() {
        elements.setupModal.style.display = "flex";
    }

    function closeModal() {
        elements.setupModal.style.display = "none";
    }

    async function fetchComplianceData(isBackground = false) {
        state.isLoading = true;
        const refreshIcon = elements.refreshBtn.querySelector(".refresh-icon");
        if (refreshIcon) refreshIcon.classList.add("spinning");

        if (!isBackground) {
            elements.lastUpdatedText.textContent = "Connecting to AWS S3...";
        }

        try {
            const response = await fetch("/api/compliance");
            const data = await response.json();
            state.complianceData = data;

            updateConnectionStatus(data);
            updateSummaryCards(data);
            updateReplicationPipeline(data);
            renderTable();

            const now = new Date();
            elements.lastUpdatedText.textContent = `Last synced: ${now.toLocaleTimeString()}`;
        } catch (error) {
            console.error("Failed to load compliance data:", error);
            renderErrorState(error.message);
        } finally {
            state.isLoading = false;
            if (refreshIcon) refreshIcon.classList.remove("spinning");
        }
    }

    function updateConnectionStatus(data) {
        const isConnected = data.connected === true;
        const isDemo = data.is_demo_mode === true;

        if (isConnected) {
            // Header badge
            elements.dataSourceBadge.className = "mode-badge";
            elements.dataSourceBadge.style.borderColor = "#a7f3d0";
            elements.dataSourceBadge.style.backgroundColor = "#ecfdf5";
            elements.dataSourceBadge.querySelector(".badge-dot").style.backgroundColor = "#10b981";
            elements.dataSourceText.textContent = "AWS Live (ap-south-1 & ap-southeast-1)";
            elements.dataSourceText.style.color = "#065f46";

            // Sidebar pill
            elements.sidebarConnectionPill.innerHTML = `
                <span class="status-dot dot-connected"></span>
                <span class="status-label">AWS Connected</span>
            `;

            // Hide alert banner
            elements.alertBanner.style.display = "none";
        } else {
            // Unauthenticated or Error state
            elements.dataSourceBadge.className = "mode-badge";
            elements.dataSourceBadge.style.borderColor = "#fde68a";
            elements.dataSourceBadge.style.backgroundColor = "#fffbeb";
            elements.dataSourceBadge.querySelector(".badge-dot").style.backgroundColor = "#f59e0b";
            elements.dataSourceText.textContent = "Demo Mode (Awaiting AWS Credentials)";
            elements.dataSourceText.style.color = "#92400e";

            // Sidebar pill
            elements.sidebarConnectionPill.innerHTML = `
                <span class="status-dot dot-warning"></span>
                <span class="status-label">Awaiting Credentials</span>
            `;

            // Show alert banner with setup guidance
            elements.alertBanner.style.display = "flex";
            if (data.error) {
                elements.alertTitle.textContent = `AWS Notice: ${data.error_code || "Connection Required"}`;
                elements.alertMessage.textContent = `${data.error} Configure credentials in .env to pull live S3 objects.`;
            }
        }
    }

    function updateSummaryCards(data) {
        const summary = data.summary || {};
        const isDemo = data.is_demo_mode;

        // Compliant Card
        elements.compliantCount.textContent = summary.compliant_count || 0;
        elements.complianceRate.textContent = `${summary.compliance_rate || 0}%`;
        elements.compliantSubtext.textContent = isDemo
            ? "[Demo Value] Awaiting AWS connection"
            : "Evaluated security controls passed";

        // Non-Compliant Card
        elements.nonCompliantCount.textContent = summary.non_compliant_count || 0;
        elements.nonCompliantSubtext.textContent = isDemo
            ? "[Demo Value] Awaiting AWS connection"
            : (summary.non_compliant_count > 0 ? "Action required" : "Zero non-compliant items");

        // Warnings Card
        elements.warningsCount.textContent = summary.warnings_count || 0;
        elements.warningsSubtext.textContent = isDemo
            ? "[Demo Value] Awaiting AWS connection"
            : "Replication sync notices";

        // Resources Monitored Card
        elements.resourcesCount.textContent = summary.resources_monitored || 0;
        elements.resourcesSubtext.textContent = isDemo
            ? "[Demo Value] 2 Buckets configured"
            : `${summary.resources_monitored} Total monitored items`;
    }

    function updateReplicationPipeline(data) {
        const isDemo = data.is_demo_mode;
        const src = data.source_bucket || {};
        const dst = data.destination_bucket || {};
        const pipeline = data.replication_pipeline || {};

        // Pipeline Status
        elements.pipelineStatusText.textContent = pipeline.status || "Checking...";
        elements.pipelineStatusBadge.className = `pipeline-status-badge ${pipeline.status_badge || ""}`;

        // Source Bucket
        elements.sourceBucketName.textContent = src.name || "compliance-source-rahul-2026";
        elements.sourceVersioning.textContent = src.versioning || (isDemo ? "[Demo] Enabled" : "Unknown");
        elements.sourceReplication.textContent = src.replication || (isDemo ? "[Demo] Enabled" : "Unknown");
        elements.sourcePab.textContent = src.public_access_block || (isDemo ? "[Demo] Fully Blocked" : "Unknown");
        elements.sourceEncryption.textContent = src.encryption || (isDemo ? "[Demo] Enabled (AES256)" : "Unknown");
        elements.sourceObjects.textContent = src.object_count !== undefined ? src.object_count : (isDemo ? "[Demo] 1" : 0);
        elements.sourceBytes.textContent = formatBytes(src.total_bytes || (isDemo ? 91 : 0));
        elements.sourceLiveTag.textContent = isDemo ? "Preview Mode" : "Live AWS";
        elements.sourceLiveTag.className = isDemo ? "live-tag badge-warning" : "live-tag";

        // Destination Bucket
        elements.destBucketName.textContent = dst.name || "compliance-destination-rahul-2026";
        elements.destVersioning.textContent = dst.versioning || (isDemo ? "[Demo] Enabled" : "Unknown");
        elements.destReplication.textContent = isDemo ? "[Demo] Active Target" : (dst.accessible ? "Active Target" : "Unknown");
        elements.destPab.textContent = dst.public_access_block || (isDemo ? "[Demo] Fully Blocked" : "Unknown");
        elements.destEncryption.textContent = dst.encryption || (isDemo ? "[Demo] Enabled (AES256)" : "Unknown");
        elements.destObjects.textContent = dst.object_count !== undefined ? dst.object_count : (isDemo ? "[Demo] 1" : 0);
        elements.destBytes.textContent = formatBytes(dst.total_bytes || (isDemo ? 91 : 0));
        elements.destLiveTag.textContent = isDemo ? "Preview Mode" : "Live AWS";
        elements.destLiveTag.className = isDemo ? "live-tag badge-warning" : "live-tag";

        // Connector Details
        elements.connectorTransferDesc.textContent = `${src.region || "ap-south-1"} ➔ ${dst.region || "ap-southeast-1"}`;
        elements.connectorSyncBadge.textContent = isDemo ? "Pipeline Ready" : (pipeline.status || "Syncing");
    }

    function renderTable() {
        if (!state.complianceData) return;

        const isDemo = state.complianceData.is_demo_mode;
        const objects = state.complianceData.recent_objects || [];
        const checks = state.complianceData.compliance_checks || [];

        // Combine both object-level replication and compliance security checks
        let rows = [];

        // 1. Add objects
        objects.forEach((obj) => {
            rows.push({
                key: obj.key,
                type: obj.type || "S3 Object",
                sourceBucket: `${obj.source_bucket} (${obj.source_region})`,
                destBucket: `${obj.dest_bucket} (${obj.dest_region})`,
                repStatus: obj.replication_status,
                complianceStatus: obj.compliance_status,
                size: obj.size_formatted,
                lastModified: formatDate(obj.last_modified),
                isDemo: false,
            });
        });

        // 2. If in demo mode and no real objects could be fetched, add sample items clearly labeled
        if (isDemo && rows.length === 0) {
            rows.push({
                key: "compliance-report.txt [DEMO PREVIEW]",
                type: "S3 Object",
                sourceBucket: `compliance-source-rahul-2026 (ap-south-1)`,
                destBucket: `compliance-destination-rahul-2026 (ap-southeast-1)`,
                repStatus: "COMPLETED",
                complianceStatus: "Compliant",
                size: "91.0 B",
                lastModified: "2026-09-14 12:35:04 (Preview)",
                isDemo: true,
            });
        }

        // 3. Add security control evaluations to the table
        checks.forEach((chk) => {
            rows.push({
                key: `${chk.control_id}: ${chk.title}${chk.is_demo ? " [DEMO]" : ""}`,
                type: "Security Control",
                sourceBucket: chk.resource || "S3 Bucket",
                destBucket: "N/A (Control Policy)",
                repStatus: chk.status === "Compliant" ? "ENFORCED" : (chk.status === "Warning" ? "PENDING" : "DEFICIENT"),
                complianceStatus: chk.status,
                size: "Policy",
                lastModified: "Continuous Audit",
                isDemo: chk.is_demo,
            });
        });

        // Filter rows based on search and status
        const filtered = rows.filter((item) => {
            // Status tab filter
            if (state.currentFilter === "compliant" && item.complianceStatus !== "Compliant") return false;
            if (state.currentFilter === "warning" && item.complianceStatus !== "Warning") return false;
            if (state.currentFilter === "non-compliant" && item.complianceStatus !== "Non-Compliant") return false;

            // Search query filter
            if (state.searchQuery) {
                const q = state.searchQuery;
                const matchKey = item.key.toLowerCase().includes(q);
                const matchType = item.type.toLowerCase().includes(q);
                const matchRep = item.repStatus.toLowerCase().includes(q);
                const matchStatus = item.complianceStatus.toLowerCase().includes(q);
                return matchKey || matchType || matchRep || matchStatus;
            }

            return true;
        });

        // Update record count
        elements.tableRecordCount.textContent = `Showing ${filtered.length} of ${rows.length} monitored records`;

        // Render HTML
        if (filtered.length === 0) {
            elements.tableBody.innerHTML = `
                <tr>
                    <td colspan="8" class="table-loading-cell">
                        <span>No records match the current filter or search criteria.</span>
                    </td>
                </tr>
            `;
            return;
        }

        elements.tableBody.innerHTML = filtered.map((row) => {
            const repPillClass = getRepPillClass(row.repStatus);
            const compPillClass = getCompBadgeClass(row.complianceStatus);

            return `
                <tr>
                    <td>
                        <div class="resource-key-cell">
                            <svg class="resource-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                ${row.type === "S3 Object" 
                                    ? '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline>'
                                    : '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>'}
                            </svg>
                            <span title="${escapeHtml(row.key)}">${escapeHtml(row.key)}</span>
                        </div>
                    </td>
                    <td><span class="info-tag">${escapeHtml(row.type)}</span></td>
                    <td><span class="info-value">${escapeHtml(row.sourceBucket)}</span></td>
                    <td><span class="info-value">${escapeHtml(row.destBucket)}</span></td>
                    <td><span class="status-pill ${repPillClass}">${escapeHtml(row.repStatus)}</span></td>
                    <td><span class="status-pill ${compPillClass}">${escapeHtml(row.complianceStatus)}</span></td>
                    <td><span class="info-value">${escapeHtml(row.size)}</span></td>
                    <td><span class="info-value">${escapeHtml(row.lastModified)}</span></td>
                </tr>
            `;
        }).join("");
    }

    function getRepPillClass(status) {
        switch (status) {
            case "COMPLETED":
            case "ENFORCED":
                return "pill-completed";
            case "REPLICA":
                return "pill-replica";
            case "PENDING":
                return "pill-pending";
            case "FAILED":
            case "DEFICIENT":
                return "pill-failed";
            default:
                return "pill-not-replicated";
        }
    }

    function getCompBadgeClass(status) {
        switch (status) {
            case "Compliant":
                return "badge-compliant";
            case "Warning":
                return "badge-warning";
            case "Non-Compliant":
                return "badge-non-compliant";
            default:
                return "badge-unknown";
        }
    }

    function renderErrorState(errorMsg) {
        elements.lastUpdatedText.textContent = "Error connecting to server";
        elements.tableBody.innerHTML = `
            <tr>
                <td colspan="8" class="table-loading-cell">
                    <span style="color: #ef4444;">Failed to fetch compliance data: ${escapeHtml(errorMsg)}</span>
                </td>
            </tr>
        `;
    }

    function formatBytes(bytes) {
        if (!bytes || bytes === 0) return "0 B";
        const k = 1024;
        const sizes = ["B", "KB", "MB", "GB", "TB"];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
    }

    function formatDate(dateStr) {
        if (!dateStr || dateStr.includes("Preview") || dateStr === "Continuous Audit") return dateStr;
        try {
            const d = new Date(dateStr);
            if (isNaN(d.getTime())) return dateStr;
            return d.toLocaleString();
        } catch {
            return dateStr;
        }
    }

    function escapeHtml(text) {
        if (!text) return "";
        const div = document.createElement("div");
        div.textContent = text;
        return div.innerHTML;
    }
});
