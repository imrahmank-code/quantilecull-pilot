// Application State
let uploadedFiles = [];
let duplicateGroups = [];
let discardedFiles = new Set();
let keptFiles = new Set();
let activeMode = 'local'; // 'upload' or 'local'
let reviewMode = 'wizard'; // 'wizard' or 'feed'
let currentWizardIndex = 0;
let scannedDir = ''; // Scanned directory path for local mode
let activeJobId = null; // Track currently running backend analysis/export job
let isLicenseActive = false; // License state tracking
let licenseStatus = 'unactivated';
let currentCullMode = 'smart_cull'; // Store the active scan job's culling mode

// Destructive action confirmation callback registry
let activeDestructiveConfirmCallback = null;

// Animated stats counters helpers
function animateCounter(element, targetValue, suffix = '') {
    if (!element) return;
    const startValue = parseInt(element.textContent.replace(/[^0-9]/g, '')) || 0;
    if (startValue === targetValue) {
        element.textContent = targetValue + suffix;
        return;
    }
    const duration = 250; // ms
    const startTime = performance.now();
    
    function update(now) {
        const elapsed = now - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const easeProgress = progress * (2 - progress);
        const currentValue = Math.round(startValue + (targetValue - startValue) * easeProgress);
        element.textContent = currentValue + suffix;
        if (progress < 1) {
            requestAnimationFrame(update);
        } else {
            element.textContent = targetValue + suffix;
        }
    }
    requestAnimationFrame(update);
}

function animateSpaceCounter(element, targetKb) {
    if (!element) return;
    const currentText = element.textContent || '0';
    let currentKb = 0;
    if (currentText.includes('MB')) {
        currentKb = parseFloat(currentText) * 1024;
    } else {
        currentKb = parseFloat(currentText) || 0;
    }
    
    const duration = 250; // ms
    const startTime = performance.now();
    
    function update(now) {
        const elapsed = now - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const easeProgress = progress * (2 - progress);
        const currentVal = currentKb + (targetKb - currentKb) * easeProgress;
        
        if (currentVal >= 1024) {
            element.textContent = `${(currentVal / 1024).toFixed(1)} MB`;
        } else {
            element.textContent = `${currentVal.toFixed(0)} KB`;
        }
        
        if (progress < 1) {
            requestAnimationFrame(update);
        } else {
            if (targetKb >= 1024) {
                element.textContent = `${(targetKb / 1024).toFixed(1)} MB`;
            } else {
                element.textContent = `${targetKb.toFixed(0)} KB`;
            }
        }
    }
    requestAnimationFrame(update);
}

function toggleModalOpen(modalId, show) {
    const modal = document.getElementById(modalId);
    if (!modal) return;
    if (show) {
        modal.classList.remove('hidden');
        document.body.classList.add('modal-open');
    } else {
        modal.classList.add('hidden');
        const modals = ['compare-modal', 'selected-photos-modal', 'export-modal', 'destructive-confirm-modal', 'recovery-modal'];
        const anyOpen = modals.some(id => {
            const el = document.getElementById(id);
            return el && !el.classList.contains('hidden');
        });
        if (!anyOpen) {
            document.body.classList.remove('modal-open');
        }
    }
}

function showDestructiveConfirm(title, msg1, msg2, onConfirm) {
    const modal = document.getElementById('destructive-confirm-modal');
    const titleEl = document.getElementById('destructive-modal-title');
    const msg1El = document.getElementById('destructive-modal-message-1');
    const msg2El = document.getElementById('destructive-modal-message-2');
    const step1 = document.getElementById('destructive-step-1');
    const step2 = document.getElementById('destructive-step-2');
    const confirmBtn = document.getElementById('btn-destructive-confirm');
    const input = document.getElementById('destructive-confirm-input');

    if (!modal) return;

    titleEl.innerHTML = `
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width: 20px; height: 20px; flex-shrink: 0;">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
            <line x1="12" y1="9" x2="12" y2="13"></line>
            <line x1="12" y1="17" x2="12.01" y2="17"></line>
        </svg>
        ${title}
    `;
    msg1El.textContent = msg1;
    msg2El.textContent = msg2;

    // Reset modal state
    step1.classList.remove('hidden');
    step2.classList.add('hidden');
    input.value = '';
    confirmBtn.disabled = true;

    activeDestructiveConfirmCallback = onConfirm;
    toggleModalOpen('destructive-confirm-modal', true);
}

function closeDestructiveConfirm() {
    toggleModalOpen('destructive-confirm-modal', false);
    activeDestructiveConfirmCallback = null;
}

// DOM Elements
const localPathInput = document.getElementById('local-path-input');
const btnCancelJob = document.getElementById('btn-cancel-job');

// Legacy upload selectors (commented out for local scanning mode)
// const folderInput = document.getElementById('folder-input');
// const uploadProgressContainer = document.getElementById('upload-progress-container');
// const progressBar = document.getElementById('progress-bar');
// const progressPercent = document.getElementById('progress-percent');
// const progressText = document.getElementById('progress-text');
// const filesPreviewContainer = document.getElementById('files-preview-container');
// const previewGrid = document.getElementById('preview-grid');
// const filesPreviewCount = document.getElementById('files-preview-count');
const btnAnalyze = document.getElementById('btn-analyze');
const btnClearAll = document.getElementById('btn-clear-all');
const thresholdSlider = document.getElementById('threshold-slider');
// const thresholdVal = document.getElementById('threshold-val');

const resultsPlaceholder = document.getElementById('results-placeholder');
const loadingOverlay = document.getElementById('loading-overlay');
const loadingStatus = document.getElementById('loading-status');
const loadingSubstatus = document.getElementById('loading-substatus');
const resultsContainer = document.getElementById('results-container');
const duplicateSetsCount = null; // Removed from UI
const uniqueSetsCount = document.getElementById('unique-sets-count');
const groupsFeed = document.getElementById('groups-feed');

const btnModeWizard = document.getElementById('btn-mode-wizard');
const btnModeFeed = document.getElementById('btn-mode-feed');
const wizardNavPanel = document.getElementById('wizard-nav-panel');
const btnWizardPrev = document.getElementById('btn-wizard-prev');
const btnWizardNext = document.getElementById('btn-wizard-next');
const wizardIndex = document.getElementById('wizard-index');
const wizardTotal = document.getElementById('wizard-total');

const exportModal = document.getElementById('export-modal');
const exportPhotoCount = document.getElementById('export-photo-count');
const exportDuplicateCount = document.getElementById('export-duplicate-count');
const btnDeleteDiscarded = document.getElementById('btn-delete-discarded');
const btnBrowseFolder = document.getElementById('btn-browse-folder');
const exportDirInput = document.getElementById('export-dir-input');
const btnDeleteCount = document.getElementById('btn-delete-count');
const btnBackupLocal = document.getElementById('btn-backup-local');
const btnBackupCount = document.getElementById('btn-backup-count');
const btnDownloadZip = document.getElementById('btn-download-zip');
const btnDiscardAll = document.getElementById('btn-discard-all');

const exportResizePreset = document.getElementById('export-resize-preset');
const customDimsContainer = document.getElementById('custom-dims-container');
const customW = document.getElementById('custom-w');
const customH = document.getElementById('custom-h');
const exportPpi = document.getElementById('export-ppi');
const exportFormat = document.getElementById('export-format');
const exportQualitySlider = document.getElementById('export-quality-slider');
const exportQualityValue = document.getElementById('export-quality-value');
const exportQualityPresetDesc = document.getElementById('export-quality-preset-desc');
const exportPngWarning = document.getElementById('export-png-warning');
const exportQualitySliderContainer = document.getElementById('export-quality-slider-container');

function updateQualitySliderVisibility() {
    if (!exportFormat) return;
    const format = exportFormat.value;
    if (format === 'PNG') {
        if (exportQualitySliderContainer) exportQualitySliderContainer.classList.add('hidden');
        if (exportQualityValue) exportQualityValue.classList.add('hidden');
        if (exportPngWarning) exportPngWarning.classList.remove('hidden');
    } else {
        if (exportQualitySliderContainer) exportQualitySliderContainer.classList.remove('hidden');
        if (exportQualityValue) exportQualityValue.classList.remove('hidden');
        if (exportPngWarning) exportPngWarning.classList.add('hidden');
    }
}

// Modal Elements
const compareModal = document.getElementById('compare-modal');
const compareModalBackdrop = document.getElementById('compare-modal-backdrop');
const btnCloseModal = document.getElementById('btn-close-modal');
const leftImg = document.getElementById('left-img');
const rightImg = document.getElementById('right-img');
const leftScore = document.getElementById('left-score');
const rightScore = document.getElementById('right-score');
const leftMetrics = document.getElementById('left-metrics');
const rightMetrics = document.getElementById('right-metrics');
const leftFaceOverlay = document.getElementById('left-face-overlay');
const rightFaceOverlay = document.getElementById('right-face-overlay');
const leftBadge = document.getElementById('left-badge');
const rightBadge = document.getElementById('right-badge');

// About Modal Elements
const aboutModal = document.getElementById('about-modal');
const btnAbout = document.getElementById('btn-about');
const btnCloseAboutModal = document.getElementById('btn-close-about-modal');
const aboutModalBackdrop = document.getElementById('about-modal-backdrop');

// Global Stats Badge selectors
const statTotalPhotosVal = document.querySelector('#stat-total-photos .stat-value');
const statDuplicateGroupsVal = document.querySelector('#stat-duplicate-groups .stat-value');
const statSpaceSavedVal = document.querySelector('#stat-space-saved .stat-value');

// Toolbar Stats selectors
const toolbarStatTotalVal = document.getElementById('toolbar-stat-total');
const toolbarStatGroupsVal = document.getElementById('toolbar-stat-groups');
const toolbarStatSpaceVal = document.getElementById('toolbar-stat-space');

document.addEventListener('DOMContentLoaded', () => {

    // Update slider track gradient fill helper
    const updateSliderTrack = (slider) => {
        const val = parseInt(slider.value);
        const min = parseInt(slider.min) || 1;
        const max = parseInt(slider.max) || 100;
        const pct = ((val - min) / (max - min)) * 100;
        slider.style.background = `linear-gradient(to right, var(--cyan) 0%, var(--cyan) ${pct}%, rgba(255, 255, 255, 0.15) ${pct}%, rgba(255, 255, 255, 0.15) 100%)`;
    };

    const thresholdHelper = document.getElementById('threshold-helper');
    const sliderThumbValue = document.getElementById('slider-thumb-value');

    const updateThumbValuePosition = (val) => {
        if (!sliderThumbValue) return;
        const min = parseInt(thresholdSlider.min) || 1;
        const max = parseInt(thresholdSlider.max) || 100;
        const percent = ((val - min) / (max - min)) * 100;
        const offset = (percent / 100) * 24;
        sliderThumbValue.style.left = `calc(${percent}% - ${offset}px)`;
        sliderThumbValue.textContent = val;
    };

    // Update slider label helper
    const updateSliderLabel = (val) => {
        let desc = '';
        if (val <= 6) desc = 'Strict (Exact)';
        else if (val <= 12) desc = 'Conservative';
        else if (val <= 20) desc = 'Recommended';
        else desc = 'Loose (Different Angles/Crops)';
        
        updateThumbValuePosition(val);

        if (thresholdHelper) {
            thresholdHelper.textContent = desc;
        }
    };

    // Initial slider setup
    if (thresholdSlider) {
        updateSliderTrack(thresholdSlider);
        updateSliderLabel(parseInt(thresholdSlider.value));
        
        thresholdSlider.addEventListener('input', (e) => {
            const val = parseInt(e.target.value);
            updateSliderLabel(val);
            updateSliderTrack(thresholdSlider);
        });

        window.addEventListener('resize', () => {
            updateThumbValuePosition(parseInt(thresholdSlider.value));
        });
    }



    if (localPathInput) {
        const adjustHeight = () => {
            localPathInput.style.height = 'auto';
            localPathInput.style.height = (localPathInput.scrollHeight) + 'px';
        };

        const updateLaunchpadInfo = async (path, silent = false) => {
            const heroInitial = document.getElementById('hero-initial-state');
            const heroSelected = document.getElementById('hero-selected-state');
            const lpFolderName = document.getElementById('launchpad-folder-name');
            const lpFolderPath = document.getElementById('launchpad-folder-path');
            const lpPhotoCount = document.getElementById('launchpad-photo-count');
            const lpEstTime = document.getElementById('launchpad-est-time');
            const lpCollage = document.getElementById('launchpad-collage');

            if (!path || path.trim().length === 0) {
                if (heroInitial) heroInitial.classList.remove('hidden');
                if (heroSelected) heroSelected.classList.add('hidden');
                btnAnalyze.disabled = true;
                return;
            }

            if (window.pywebview && window.pywebview.api) {
                try {
                    const info = await window.pywebview.api.get_folder_info(path);
                    if (info && info.success) {
                        window.pywebview.api.precache_folder(info.folder_path);
                        if (lpFolderName) lpFolderName.textContent = info.folder_name;
                        if (lpFolderPath) lpFolderPath.textContent = info.folder_path;
                        if (lpPhotoCount) lpPhotoCount.textContent = info.photo_count;
                        if (lpEstTime) lpEstTime.textContent = info.estimated_time;

                        // Populate collage grid
                        if (lpCollage) {
                            lpCollage.innerHTML = '';
                            if (info.preview_images && info.preview_images.length > 0) {
                                info.preview_images.forEach(imgSrc => {
                                    const img = document.createElement('img');
                                    img.src = imgSrc.startsWith('static/') ? imgSrc : `/image?path=${encodeURIComponent(imgSrc)}&maxWidth=400`;
                                    img.style.width = '100%';
                                    img.style.height = '100%';
                                    img.style.objectFit = 'cover';
                                    img.style.borderRadius = '6px';
                                    img.style.aspectRatio = '1';
                                    lpCollage.appendChild(img);
                                });
                                // Pad with empty placeholders if less than 4 images
                                for (let i = info.preview_images.length; i < 4; i++) {
                                    const pad = document.createElement('div');
                                    pad.style.background = 'rgba(255, 255, 255, 0.03)';
                                    pad.style.borderRadius = '6px';
                                    lpCollage.appendChild(pad);
                                }
                            } else {
                                // Default grid placeholders if no images found
                                for (let i = 0; i < 4; i++) {
                                    const pad = document.createElement('div');
                                    pad.style.background = 'rgba(255, 255, 255, 0.03)';
                                    pad.style.borderRadius = '6px';
                                    lpCollage.appendChild(pad);
                                }
                            }
                        }

                        if (heroInitial) heroInitial.classList.add('hidden');
                        if (heroSelected) heroSelected.classList.remove('hidden');
                        btnAnalyze.disabled = false;
                    } else {
                        if (heroInitial) heroInitial.classList.remove('hidden');
                        if (heroSelected) heroSelected.classList.add('hidden');
                        btnAnalyze.disabled = true;
                        if (info && info.error && !silent) {
                            alert("Folder rejected: " + info.error);
                        }
                    }
                } catch (err) {
                    console.error('Failed to get folder info:', err);
                    if (heroInitial) heroInitial.classList.remove('hidden');
                    if (heroSelected) heroSelected.classList.add('hidden');
                    btnAnalyze.disabled = true;
                    if (!silent) {
                        alert("Folder rejected: " + err.message);
                    }
                }
            } else {
                // If api not loaded yet, wait for pywebviewready
                window.addEventListener('pywebviewready', () => {
                    updateLaunchpadInfo(path, silent);
                }, { once: true });
            }
        };

        const setFolderPath = (path, silent = false) => {
            if (path) {
                localPathInput.value = path;
                btnAnalyze.disabled = false;
                setTimeout(adjustHeight, 0);
                updateLaunchpadInfo(path, silent);
            }
        };

        if (!localPathInput.value || localPathInput.value.trim().length === 0 || localPathInput.value.startsWith('{{')) {
            window.addEventListener('pywebviewready', () => {
                window.pywebview.api.get_default_path()
                    .then(path => {
                        if (path) {
                            setFolderPath(path, true);
                        }
                    })
                    .catch(err => console.log('Failed to fetch default path via API:', err));
            });
        } else {
            btnAnalyze.disabled = localPathInput.value.trim().length === 0;
            adjustHeight();
            updateLaunchpadInfo(localPathInput.value, true);
        }

        localPathInput.addEventListener('input', (e) => {
            const path = e.target.value;
            btnAnalyze.disabled = path.trim().length === 0;
            adjustHeight();
            updateLaunchpadInfo(path, true);
        });

        // Advanced Options Accordion Toggle
        const btnToggleAdvanced = document.getElementById('btn-toggle-advanced');
        const advancedSettingsBody = document.getElementById('advanced-settings-body');
        const advAccordionArrow = document.getElementById('adv-accordion-arrow');
        if (btnToggleAdvanced && advancedSettingsBody) {
            btnToggleAdvanced.addEventListener('click', () => {
                const isHidden = advancedSettingsBody.classList.contains('hidden');
                if (isHidden) {
                    advancedSettingsBody.classList.remove('hidden');
                    if (advAccordionArrow) {
                        advAccordionArrow.style.transform = 'rotate(90deg)';
                    }
                } else {
                    advancedSettingsBody.classList.add('hidden');
                    if (advAccordionArrow) {
                        advAccordionArrow.style.transform = 'rotate(0deg)';
                    }
                }
            });
        }

        // Hero Select Folder Button
        const btnHeroBrowse = document.getElementById('btn-hero-browse');
        if (btnHeroBrowse) {
            btnHeroBrowse.addEventListener('click', async () => {
                if (window.pywebview && window.pywebview.api) {
                    try {
                        const folderPath = await window.pywebview.api.select_folder();
                        if (folderPath) {
                            localPathInput.value = folderPath;
                            localPathInput.dispatchEvent(new Event('input'));
                        }
                    } catch (e) {
                        console.error('Error selecting folder:', e);
                    }
                } else {
                    alert('Folder browsing is only supported in the desktop application.');
                }
            });
        }

        // Hero Run Analysis Button
        const btnLaunchpadAnalyze = document.getElementById('btn-launchpad-analyze');
        if (btnLaunchpadAnalyze) {
            btnLaunchpadAnalyze.addEventListener('click', () => runAnalysis());
        }

        // Run once on load to ensure proper height
        setTimeout(adjustHeight, 100);
    }


    // Review Mode selectors
    btnModeWizard.addEventListener('click', () => switchReviewMode('wizard'));
    btnModeFeed.addEventListener('click', () => switchReviewMode('feed'));

    // Wizard Nav Controls
    btnWizardPrev.addEventListener('click', () => navigateWizard(-1));
    btnWizardNext.addEventListener('click', () => navigateWizard(1));

    // Buttons
    btnAnalyze.addEventListener('click', () => runAnalysis());
    btnClearAll.addEventListener('click', resetAllUploads);
    btnDeleteDiscarded.addEventListener('click', deleteDiscardedPhotos);
    btnBackupLocal.addEventListener('click', backupLocalDuplicates);
    btnDownloadZip.addEventListener('click', exportCleanedPhotos);
    btnDiscardAll.addEventListener('click', backupLocalDuplicates);
    
    const btnClearCache = document.getElementById('btn-clear-cache');
    if (btnClearCache) {
        btnClearCache.addEventListener('click', () => {
            showDestructiveConfirm(
                'Clear Privacy Cache',
                'This will wipe the entire local analysis database. All generated face mesh coordinates, image hashes, focus scores, and exposure records will be obliterated from disk.',
                'To permanently wipe the analysis metrics and clean up the database cache, authorize below.',
                () => {
                    if (window.pywebview && window.pywebview.api) {
                        window.pywebview.api.clear_cache()
                        .then(success => {
                            if (success) {
                                alert('Cache cleared successfully.');
                            } else {
                                alert('Error clearing cache.');
                            }
                        }).catch(err => alert('Error clearing cache: ' + err));
                    }
                }
            );
        });
    }

    // Custom Destructive Modal Event Handlers
    const btnCloseDestructiveModal = document.getElementById('btn-close-destructive-modal');
    const destructiveModalBackdrop = document.getElementById('destructive-modal-backdrop');
    const btnDestructiveNext = document.getElementById('btn-destructive-next');
    const btnDestructiveBack = document.getElementById('btn-destructive-back');
    const btnDestructiveConfirm = document.getElementById('btn-destructive-confirm');
    const destructiveConfirmInput = document.getElementById('destructive-confirm-input');
    const step1 = document.getElementById('destructive-step-1');
    const step2 = document.getElementById('destructive-step-2');

    if (btnCloseDestructiveModal) btnCloseDestructiveModal.addEventListener('click', closeDestructiveConfirm);
    if (destructiveModalBackdrop) destructiveModalBackdrop.addEventListener('click', closeDestructiveConfirm);

    if (btnDestructiveNext) {
        btnDestructiveNext.addEventListener('click', () => {
            if (step1 && step2) {
                step1.classList.add('hidden');
                step2.classList.remove('hidden');
                if (destructiveConfirmInput) destructiveConfirmInput.focus();
            }
        });
    }

    if (btnDestructiveBack) {
        btnDestructiveBack.addEventListener('click', () => {
            if (step1 && step2) {
                step1.classList.remove('hidden');
                step2.classList.add('hidden');
            }
        });
    }

    if (destructiveConfirmInput) {
        destructiveConfirmInput.addEventListener('input', (e) => {
            if (btnDestructiveConfirm) {
                btnDestructiveConfirm.disabled = (e.target.value.trim().toUpperCase() !== 'CONFIRM');
            }
        });
    }

    if (btnDestructiveConfirm) {
        btnDestructiveConfirm.addEventListener('click', () => {
            if (activeDestructiveConfirmCallback) {
                activeDestructiveConfirmCallback();
            }
            closeDestructiveConfirm();
        });
    }
    
    const btnHardRefresh = document.getElementById('btn-hard-refresh');
    if (btnHardRefresh) {
        btnHardRefresh.addEventListener('click', () => {
            window.location.reload();
        });
    }

    const btnHardRefreshToolbar = document.getElementById('btn-hard-refresh-toolbar');
    if (btnHardRefreshToolbar) {
        btnHardRefreshToolbar.addEventListener('click', () => {
            window.location.reload();
        });
    }

    // Modal Close
    btnCloseModal.addEventListener('click', closeCompareModal);
    compareModalBackdrop.addEventListener('click', closeCompareModal);

    // Selected Photos Modal Close & Open
    const btnSelectedPhotos = document.getElementById('btn-selected-photos');
    const btnCloseSelectedModal = document.getElementById('btn-close-selected-modal');
    const selectedPhotosBackdrop = document.getElementById('selected-photos-modal-backdrop');
    
    if (btnSelectedPhotos) {
        btnSelectedPhotos.addEventListener('click', openSelectedPhotosModal);
    }
    if (btnCloseSelectedModal) {
        btnCloseSelectedModal.addEventListener('click', closeSelectedPhotosModal);
    }
    if (selectedPhotosBackdrop) {
        selectedPhotosBackdrop.addEventListener('click', closeSelectedPhotosModal);
    }

    // About Modal Close & Open
    if (btnAbout) {
        btnAbout.addEventListener('click', () => {
            if (aboutModal) aboutModal.classList.remove('hidden');
        });
    }
    if (btnCloseAboutModal) {
        btnCloseAboutModal.addEventListener('click', () => {
            if (aboutModal) aboutModal.classList.add('hidden');
        });
    }
    if (aboutModalBackdrop) {
        aboutModalBackdrop.addEventListener('click', () => {
            if (aboutModal) aboutModal.classList.add('hidden');
        });
    }

    // Export Options Modal Close & Open
    const btnTriggerExport = document.getElementById('btn-trigger-export');
    const btnCloseExportModal = document.getElementById('btn-close-export-modal');
    const exportModalBackdrop = document.getElementById('export-modal-backdrop');
    
    if (btnTriggerExport) {
        btnTriggerExport.addEventListener('click', openExportModal);
    }
    if (btnCloseExportModal) {
        btnCloseExportModal.addEventListener('click', closeExportModal);
    }
    if (exportModalBackdrop) {
        exportModalBackdrop.addEventListener('click', closeExportModal);
    }

    // Focus Heatmap Toggle
    const toggleFocusHeatmap = document.getElementById('toggle-focus-heatmap');
    if (toggleFocusHeatmap) {
        toggleFocusHeatmap.addEventListener('change', (e) => {
            const svgOverlays = compareModal.querySelectorAll('.face-overlay-container svg');
            svgOverlays.forEach(svg => {
                svg.style.display = e.target.checked ? 'block' : 'none';
            });
        });
    }

    // Settings Gear — open panel-left as modal overlay
    const btnModifySettings = document.getElementById('btn-modify-settings');
    const btnModifySettingsHeader = document.getElementById('btn-modify-settings-header');
    const settingsBackdrop = document.getElementById('settings-modal-backdrop');
    
    const toggleSettings = () => {
        const isOpen = document.body.classList.contains('settings-modal-open');
        if (isOpen) {
            closeSettingsModal();
        } else {
            openSettingsModal();
        }
    };

    if (btnModifySettings) {
        btnModifySettings.addEventListener('click', toggleSettings);
    }
    if (btnModifySettingsHeader) {
        btnModifySettingsHeader.addEventListener('click', toggleSettings);
    }
    if (settingsBackdrop) {
        settingsBackdrop.addEventListener('click', closeSettingsModal);
    }
    const btnCloseSettings = document.getElementById('btn-close-settings');
    if (btnCloseSettings) {
        btnCloseSettings.addEventListener('click', closeSettingsModal);
    }

    // Folder location browse button click listener
    if (btnBrowseFolder) {
        btnBrowseFolder.addEventListener('click', async () => {
            if (window.pywebview && window.pywebview.api) {
                try {
                    const folderPath = await window.pywebview.api.select_folder();
                    if (folderPath) {
                        localPathInput.value = folderPath;
                        localPathInput.dispatchEvent(new Event('input'));
                    }
                } catch (e) {
                    console.error('Error selecting folder:', e);
                }
            } else {
                alert('Folder browsing is only supported in the desktop application.');
            }
        });
    }



    // Export preset toggle
    exportResizePreset.addEventListener('change', (e) => {
        if (e.target.value === 'custom') {
            customDimsContainer.classList.remove('hidden');
        } else {
            customDimsContainer.classList.add('hidden');
        }
    });

    // Export format change listener for quality slider visibility
    if (exportFormat) {
        exportFormat.addEventListener('change', () => {
            updateQualitySliderVisibility();
        });
    }

    // Export quality slider change listener for text indicator updates
    if (exportQualitySlider) {
        exportQualitySlider.addEventListener('input', (e) => {
            const val = parseInt(e.target.value);
            if (exportQualityValue) {
                exportQualityValue.textContent = `${val}%`;
            }
            if (exportQualityPresetDesc) {
                let desc = 'High Quality (95)';
                if (val >= 95) desc = 'High Quality (95)';
                else if (val >= 85) desc = 'Balanced (85)';
                else desc = 'Maximum Compression (75)';
                exportQualityPresetDesc.textContent = desc;
            }
        });
    }

    // Thumbnail Zoom Control
    const zoomSlider = document.getElementById('thumbnail-zoom-slider');
    const zoomOutBtn = document.getElementById('zoom-out-btn');
    const zoomInBtn = document.getElementById('zoom-in-btn');

    if (zoomSlider) {
        document.documentElement.style.setProperty('--thumbnail-size', `${zoomSlider.value}px`);

        zoomSlider.addEventListener('input', (e) => {
            document.documentElement.style.setProperty('--thumbnail-size', `${e.target.value}px`);
        });

        if (zoomOutBtn) {
            zoomOutBtn.addEventListener('click', () => {
                const newVal = Math.max(parseInt(zoomSlider.min), parseInt(zoomSlider.value) - 20);
                zoomSlider.value = newVal;
                document.documentElement.style.setProperty('--thumbnail-size', `${newVal}px`);
            });
        }

        if (zoomInBtn) {
            zoomInBtn.addEventListener('click', () => {
                const newVal = Math.min(parseInt(zoomSlider.max), parseInt(zoomSlider.value) + 20);
                zoomSlider.value = newVal;
                document.documentElement.style.setProperty('--thumbnail-size', `${newVal}px`);
            });
        }
    }

    // Sticky Toolbar Scroll Shadow Detection
    window.addEventListener('scroll', () => {
        const toolbar = document.getElementById('culling-toolbar');
        if (toolbar) {
            if (window.scrollY > 10) {
                toolbar.classList.add('scrolled');
            } else {
                toolbar.classList.remove('scrolled');
            }
        }
    });

    // Wire up Cancel Job Button
    if (btnCancelJob) {
        btnCancelJob.addEventListener('click', () => {
            if (activeJobId && window.pywebview && window.pywebview.api) {
                btnCancelJob.disabled = true;
                btnCancelJob.textContent = 'Cancelling...';
                window.pywebview.api.cancel_job(activeJobId)
                    .catch(err => {
                        console.error('Failed to cancel job:', err);
                        btnCancelJob.disabled = false;
                        btnCancelJob.textContent = 'Cancel Operation';
                    });
            }
        });
    }

    // Wire up Export Support Logs Button
    const btnExportDiagnostics = document.getElementById('btn-export-diagnostics');
    if (btnExportDiagnostics) {
        btnExportDiagnostics.addEventListener('click', () => {
            if (!window.pywebview || !window.pywebview.api) {
                alert('Diagnostics export is only supported in the desktop application.');
                return;
            }
            btnExportDiagnostics.disabled = true;
            const originalHTML = btnExportDiagnostics.innerHTML;
            btnExportDiagnostics.innerHTML = `Exporting...`;
            window.pywebview.api.export_diagnostics()
                .then(res => {
                    btnExportDiagnostics.disabled = false;
                    btnExportDiagnostics.innerHTML = originalHTML;
                    if (res && res.success) {
                        alert(`Support logs successfully exported to:\n${res.path}`);
                    } else {
                        alert(`Failed to export diagnostics: ${res.error || 'Unknown error'}`);
                    }
                })
                .catch(err => {
                    btnExportDiagnostics.disabled = false;
                    btnExportDiagnostics.innerHTML = originalHTML;
                    alert(`Error exporting diagnostics: ${err.message}`);
                });
        });
    }

    // Initialize backend communication on readiness
    const initAppApis = () => {
        if (window.pywebview && window.pywebview.api) {
            console.log(Object.keys(window.pywebview.api));
        }
        initSettings();
        checkModelDownloadProgress();
        checkRecoveryCheckpoint();
        initLicensing();
        setupLicensingUI();
        setupFeedbackUI();
        setupFeatureRequestUI();
        checkAndPromptCrashReport();
        checkForUpdates();
    };

    if (window.pywebview) {
        initAppApis();
    } else {
        window.addEventListener('pywebviewready', initAppApis);
    }
});



// Review mode toggling
function switchReviewMode(mode) {
    if (mode === reviewMode) return;
    reviewMode = mode;
    if (mode === 'wizard') {
        btnModeWizard.classList.add('active');
        btnModeFeed.classList.remove('active');
    } else {
        btnModeWizard.classList.remove('active');
        btnModeFeed.classList.add('active');
    }
    renderDuplicateGroups();
}

// Navigation for wizard queue
function navigateWizard(direction) {
    const dupGroups = duplicateGroups.filter(g => g.is_duplicate_group);
    const newIndex = currentWizardIndex + direction;
    if (newIndex >= 0 && newIndex < dupGroups.length) {
        currentWizardIndex = newIndex;
        renderDuplicateGroups();
    }
}

/*
function handleFolderSelect(e) {
    const files = e.target.files;
    uploadFiles(files);
}

// Multi-file Upload Handler
function uploadFiles(files) {
    if (files.length === 0) return;

    uploadProgressContainer.classList.remove('hidden');
    progressBar.style.width = '0%';
    progressPercent.textContent = '0%';
    progressText.textContent = `Preparing upload for ${files.length} images...`;

    const formData = new FormData();
    for (let i = 0; i < files.length; i++) {
        formData.append('photos', files[i]);
    }

    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/upload', true);

    xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) {
            const percent = Math.round((e.loaded / e.total) * 100);
            progressBar.style.width = `${percent}%`;
            progressPercent.textContent = `${percent}%`;
            progressText.textContent = `Uploading photo gallery...`;
        }
    };

    xhr.onload = () => {
        if (xhr.status === 200) {
            const response = JSON.parse(xhr.responseText);
            if (response.success && response.files.length > 0) {
                uploadedFiles = [...uploadedFiles, ...response.files];
                updateUploadPreviews();
                btnAnalyze.disabled = false;
                btnClearAll.classList.remove('hidden');
            }
        } else {
            alert('Upload failed. Please try again.');
        }
        uploadProgressContainer.classList.add('hidden');
    };

    xhr.onerror = () => {
        alert('An error occurred during file upload.');
        uploadProgressContainer.classList.add('hidden');
    };

    xhr.send(formData);
}

// Refresh previews in left panel
function updateUploadPreviews() {
    if (!previewGrid || !filesPreviewCount || !filesPreviewContainer) return;
    previewGrid.innerHTML = '';
    filesPreviewCount.textContent = uploadedFiles.length;
    statTotalPhotosVal.textContent = uploadedFiles.length;

    if (uploadedFiles.length > 0) {
        filesPreviewContainer.classList.remove('hidden');
        uploadedFiles.forEach(file => {
            const item = document.createElement('div');
            item.className = 'preview-item';
            
            const img = document.createElement('img');
            img.src = file.url;
            img.alt = file.original_name;
            
            item.appendChild(img);
            previewGrid.appendChild(item);
        });
    } else {
        filesPreviewContainer.classList.add('hidden');
    }
}
*/

// Reset Uploads / Gallery State
function resetAllUploads() {
    if (confirm('Are you sure you want to clear your current selection and analysis results?')) {
        // Close settings modal and restore layout
        closeSettingsModal();
        const appMain = document.querySelector('.app-main');
        if (appMain) {
            appMain.classList.remove('has-results');
            document.body.classList.remove('has-results');
        }

        uploadedFiles = [];
        duplicateGroups = [];
        discardedFiles.clear();
        keptFiles.clear();
        
        renderDuplicateGroups();
        updateStatsAndExportBar();
        
        resultsPlaceholder.classList.remove('hidden');
        resultsContainer.classList.add('hidden');
        
        const pathInput = document.getElementById('local-path-input');
        btnAnalyze.disabled = pathInput ? pathInput.value.trim().length === 0 : true;
        btnClearAll.classList.add('hidden');
        
        if (statTotalPhotosVal) statTotalPhotosVal.textContent = '0';
        if (statDuplicateGroupsVal) statDuplicateGroupsVal.textContent = '0';
        if (statSpaceSavedVal) statSpaceSavedVal.textContent = '0 KB';

        if (toolbarStatTotalVal) toolbarStatTotalVal.textContent = '0';
        if (toolbarStatGroupsVal) toolbarStatGroupsVal.textContent = '0';
        if (toolbarStatSpaceVal) toolbarStatSpaceVal.textContent = '0 KB';
    }
}

// Run CV analysis (Supports Upload vs Local scanning)
function runAnalysis(resume = false) {
    if (!isLicenseActive) {
        showLicensingOverlay();
        return;
    }
    loadingOverlay.classList.remove('hidden');
    btnAnalyze.disabled = true;
    if (wizardNavPanel) wizardNavPanel.classList.add('hidden');

    // Close settings modal if open
    closeSettingsModal();
    
    loadingStatus.textContent = resume ? "⚡ Resuming AI Analysis..." : "⚡ Initializing AI Analysis...";
    loadingSubstatus.textContent = "Eliminating exact duplicates and preparing files...";
    updateGauge(5);

    const topPercentSelect = document.getElementById('top-percent-select');
    const topPercent = topPercentSelect ? topPercentSelect.value : '';
    const threshold = parseInt(thresholdSlider.value);
    const path = localPathInput.value;

    const cullModeRadio = document.querySelector('input[name="cull-mode"]:checked');
    const cullMode = cullModeRadio ? cullModeRadio.value : 'smart_cull';
    currentCullMode = cullMode;

    if (window.pywebview && window.pywebview.api) {
        window.pywebview.api.scan_local(path, threshold, topPercent ? parseInt(topPercent) : null, cullMode, resume)
        .then(jobId => {
            if (!jobId) {
                throw new Error("Failed to start analysis job.");
            }
            activeJobId = jobId; // Store active job ID
            pollScanJob(jobId);
        })
        .catch(err => handleScanError(err));
    } else {
        alert('API is not available. Ensure you are running in the Desktop application.');
        loadingOverlay.classList.add('hidden');
        btnAnalyze.disabled = false;
    }

    function pollScanJob(jobId) {
        const pollInterval = setInterval(async () => {
            try {
                const jobState = await window.pywebview.api.get_job_status(jobId);
                if (!jobState) {
                    clearInterval(pollInterval);
                    handleScanError(new Error("Analysis job state could not be retrieved."));
                    return;
                }

                if (jobState.status === 'running') {
                    // Update progress UI
                    const progress = jobState.progress || 0;
                    const total = jobState.total || 0;
                    const msg = jobState.message || "Running computer vision models...";
                    if (total > 0) {
                        const pct = Math.round((progress / total) * 100);
                        loadingStatus.textContent = `Analyzing ${progress} of ${total}`;
                        loadingSubstatus.textContent = `AI Analysis is running in the background... (${pct}%)`;
                        updateGauge(pct);
                    } else {
                        loadingStatus.textContent = msg;
                        loadingSubstatus.textContent = "Analyzing directory files...";
                    }
                } else if (jobState.status === 'completed') {
                    clearInterval(pollInterval);
                    handleScanResponse(jobState.result);
                    if (jobState.background_ai) {
                        pollBackgroundAI(jobId);
                    }
                } else if (jobState.status === 'failed') {
                    clearInterval(pollInterval);
                    handleScanError(new Error(jobState.error || "Analysis job failed."));
                }
            } catch (err) {
                clearInterval(pollInterval);
                handleScanError(err);
            }
        }, 500);
    }

    function handleScanError(err) {
        activeJobId = null;
        if (btnCancelJob) {
            btnCancelJob.disabled = false;
            btnCancelJob.textContent = 'Cancel Operation';
        }
        loadingOverlay.classList.add('hidden');
        btnAnalyze.disabled = false;
        alert('An error occurred during analysis: ' + err.message);
        console.error(err);
    }

    function handleScanResponse(response) {
        activeJobId = null;
        if (btnCancelJob) {
            btnCancelJob.disabled = false;
            btnCancelJob.textContent = 'Cancel Operation';
        }
        loadingOverlay.classList.add('hidden');
        btnAnalyze.disabled = false;
        
        if (response.success) {
            duplicateGroups = response.groups;
            scannedDir = response.scanned_dir || '';
            currentWizardIndex = 0;
            
            if (exportDirInput && scannedDir) {
                exportDirInput.value = scannedDir + '_optimized';
            }
            
            discardedFiles.clear();
            keptFiles.clear();
            
            let totalPhotoCount = 0;
            let autoDiscardCount = 0;
            duplicateGroups.forEach(group => {
                totalPhotoCount += group.photos.length;
                group.photos.forEach(photo => {
                    const decision = (photo.metrics && photo.metrics.editorial_decision) ? photo.metrics.editorial_decision : "REJECT";
                    if (decision === "HERO" || decision === "KEEP") {
                        keptFiles.add(photo.filename);
                        discardedFiles.delete(photo.filename);
                    } else {
                        discardedFiles.add(photo.filename);
                        keptFiles.delete(photo.filename);
                    }
                    if (photo.auto_discard) {
                        autoDiscardCount++;
                    }
                });
            });

            if (totalPhotoCount === 0) {
                alert("No photos were found in the directory:\n" + scannedDir + "\n\nPlease check the path and try again.");
                resultsPlaceholder.classList.remove('hidden');
                resultsContainer.classList.add('hidden');
                return;
            }

            // Update stats panel
            animateCounter(statTotalPhotosVal, totalPhotoCount);
            animateCounter(toolbarStatTotalVal, totalPhotoCount);

            // Reset gauge to 100% briefly then hide
            updateGauge(100);

            try {
                renderDuplicateGroups();
                updateStatsAndExportBar();
                window.scrollTo({ top: 0, behavior: 'instant' });
            } catch (renderError) {
                alert('JS Rendering Error: ' + renderError.message + '\nStack:\n' + renderError.stack);
                console.error(renderError);
            }
            
            resultsPlaceholder.classList.add('hidden');
            resultsContainer.classList.remove('hidden');
            
            // Trigger feedback popup if cumulative images processed >= 1000 and not already prompted
            if (window.pywebview && window.pywebview.api) {
                window.pywebview.api.check_license()
                    .then(lic => {
                        const totalProcessed = (lic.metrics && lic.metrics.images_processed) ? lic.metrics.images_processed : 0;
                        const alreadyPrompted = localStorage.getItem('feedback_prompted');
                        if (totalProcessed >= 1000 && !alreadyPrompted) {
                            const feedbackModal = document.getElementById('feedback-modal');
                            if (feedbackModal) {
                                feedbackModal.classList.remove('hidden');
                                localStorage.setItem('feedback_prompted', 'true');
                            }
                        }
                    })
                    .catch(err => console.error('Failed to check license metrics on completion:', err));
            }

        } else {
            alert('Analysis failed: ' + (response.error || response.message));
        }
    }
}

// Render duplicate sets in Workspace (Grid feed vs Step-by-Step Wizard)
function renderDuplicateGroups() {
    groupsFeed.innerHTML = '';
    
    const dupGroups = duplicateGroups.filter(g => g.is_duplicate_group);
    const uniqueGroups = duplicateGroups.filter(g => !g.is_duplicate_group);
    
    animateCounter(duplicateSetsCount, dupGroups.length);
    if (uniqueSetsCount) uniqueSetsCount.textContent = keptFiles.size;
    animateCounter(statDuplicateGroupsVal, dupGroups.length);
    animateCounter(toolbarStatGroupsVal, dupGroups.length);
    
    const totalGroupsCount = document.getElementById('total-groups-count');
    animateCounter(totalGroupsCount, dupGroups.length);

    if (dupGroups.length === 0 && uniqueGroups.length === 0) {
        resultsPlaceholder.classList.remove('hidden');
        resultsContainer.classList.add('hidden');
        if (wizardNavPanel) wizardNavPanel.classList.add('hidden');
        return;
    }

    // Toggle wizard nav bar visibility
    if (reviewMode === 'wizard' && dupGroups.length > 0) {
        wizardNavPanel.classList.remove('hidden');
        wizardIndex.textContent = currentWizardIndex + 1;
        wizardTotal.textContent = dupGroups.length;
        
        btnWizardPrev.disabled = (currentWizardIndex === 0);
        btnWizardNext.disabled = (currentWizardIndex === dupGroups.length - 1);
    } else {
        wizardNavPanel.classList.add('hidden');
    }

    // Determine groups to render
    let groupsToRender = [];
    if (reviewMode === 'wizard') {
        if (dupGroups.length > 0) {
            groupsToRender = [dupGroups[currentWizardIndex]];
        }
    } else {
        groupsToRender = dupGroups;
    }

    if (dupGroups.length === 0) {
        const noDupsCard = document.createElement('div');
        noDupsCard.className = 'glass-panel';
        noDupsCard.style.cssText = 'padding: 3.5rem 2rem; text-align: center; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 1.25rem; border-radius: 20px; box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.2); border: 1px solid rgba(255, 255, 255, 0.05); margin-top: 1rem;';
        
        noDupsCard.innerHTML = `
            <div style="width: 64px; height: 64px; border-radius: 50%; background: rgba(50, 215, 75, 0.1); display: flex; align-items: center; justify-content: center; color: var(--green); margin-bottom: 0.5rem; margin-left: auto; margin-right: auto;">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="width: 32px; height: 32px;">
                    <polyline points="20 6 9 17 4 12"></polyline>
                </svg>
            </div>
            <h3 style="font-size: 1.35rem; font-weight: 700; background: linear-gradient(90deg, #fff 50%, var(--green) 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 0.5rem;">No Duplicates Found!</h3>
            <p style="color: var(--text-secondary); font-size: 0.9rem; max-width: 440px; line-height: 1.6; margin: 0 auto 1rem;">
                Great news! We scanned your folder and found that all <strong style="color: var(--cyan);">${uniqueGroups.length}</strong> photos are unique and represent distinct shots.
            </p>
            <div style="display: flex; gap: 1rem; justify-content: center; width: 100%;">
                <button class="btn btn-secondary" onclick="switchReviewMode('feed')" style="padding: 0.6rem 1.25rem; font-size: 0.8rem;">View All Unique Photos</button>
            </div>
        `;
        groupsFeed.appendChild(noDupsCard);
    }

    // Render Groups
    groupsToRender.forEach(group => {
        const bestPhoto = group.photos.find(p => p.is_best) || group.photos[0];
        
        const groupCard = document.createElement('div');
        groupCard.className = 'duplicate-group-card';
        groupCard.id = `group-${group.group_id}`;
        
        // Header with session badge (Lightroom style metadata)
        const header = document.createElement('div');
        header.className = 'group-card-header';
        const sessionBadge = group.is_session_group 
            ? '<span class="group-session-tag">⏱ SAME SESSION</span>' 
            : '';
        header.innerHTML = `
            <div class="group-header-left">
                <span class="group-title-text">SET ${group.group_id}</span>
                <span class="group-meta-divider">•</span>
                <span class="group-count-text">${group.photos.length} PHOTOS</span>
                ${sessionBadge}
            </div>
            <button class="btn-text-action" onclick="keepOnlyBest(${group.group_id})" title="Auto-select recommended best photo and discard others in this set">
                Keep Recommended Only
            </button>
        `;
        groupCard.appendChild(header);
        
        // Combined Grid
        const grid = document.createElement('div');
        grid.className = 'group-grid';
        
        const rowList = document.createElement('div');
        rowList.className = 'duplicates-row-list';
        
        // Render all photos in the group sorted by quality score
        group.photos.forEach(photo => {
            const isDiscarded = discardedFiles.has(photo.filename);
            const isKept = !isDiscarded;
            
            const dupCard = document.createElement('div');
            dupCard.className = `duplicate-sub-card ${isKept ? 'is-kept' : ''} ${photo.is_best ? 'is-ai-pick' : ''}`;
            dupCard.setAttribute('data-path', photo.filename);
            
            // Selection checkbox (checkmark overlay)
            const checkboxClass = isKept ? 'card-select-checkbox selected' : 'card-select-checkbox';
            const checkIconStyle = isKept ? 'display:block;' : 'display:none;';
            
            // Compare target logic
            const compareTarget = photo.filename === bestPhoto.filename 
                ? (group.photos[1] ? group.photos[1].filename : '') 
                : bestPhoto.filename;
                
            // Compare Button Overlay
            const compareBtnHtml = compareTarget 
                ? `<button class="img-overlay-btn btn-compare" onclick="event.stopPropagation(); comparePhotos('${escapeString(compareTarget)}', '${escapeString(photo.filename)}')" title="Compare detailed metrics">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="width:12px; height:12px; display:block;">
                        <path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/>
                    </svg>
                   </button>`
                : '';
                
            // Best pick tag - Only shown if it is AI pick AND kept by the user
            const bestTagHtml = (photo.is_best && isKept) 
                ? `<span class="overlay-best-badge">★ AI PICK</span>` 
                : '';
            
            // Quality warning badges
            let warningsHtml = '';
            if (photo.metrics) {
                if (photo.metrics.is_blurry) {
                    warningsHtml += `<span class="card-warning-badge blur-warning">⚠ Blur</span>`;
                }
                const notes = photo.metrics.analysis_notes || [];
                const isOverexposed = notes.some(note => note.includes("Over-exposed"));
                const isUnderexposed = notes.some(note => note.includes("Under-exposed"));
                if (isOverexposed) {
                    warningsHtml += `<span class="card-warning-badge over-warning">☀ Overexposed</span>`;
                } else if (isUnderexposed) {
                    warningsHtml += `<span class="card-warning-badge under-warning">🌑 Underexposed</span>`;
                }
            }

            // Eye Blink Fix Action
            const sourcePhoto = group.photos.find(p => !p.metrics.has_blink) || group.photos.find(p => p.filename !== photo.filename);
            const fixBlinkBtnHtml = (photo.metrics.has_blink && sourcePhoto && photo.path !== sourcePhoto.path)
                ? `<button class="btn-fix-blink-overlay" onclick="event.stopPropagation(); fixBlink(${group.group_id}, '${escapeString(photo.path)}', '${escapeString(sourcePhoto.path)}')">👁 FIX BLINK</button>`
                : '';

            const isRaw = isRawFile(photo.filename);
            const rawBadgeHtml = isRaw ? `<span class="card-raw-badge" style="position: absolute; top: 10px; left: 10px; background: rgba(0,0,0,0.65); color: #fff; padding: 2px 6px; font-size: 0.62rem; font-weight: 700; border-radius: 4px; backdrop-filter: blur(4px); z-index: 5; border: 1px solid rgba(255,255,255,0.1); letter-spacing: 0.5px;">RAW</span>` : '';
            
            let xmpBadgesHtml = '';
            const r = photo.metrics.xmp_rating || 0;
            const lbl = photo.metrics.xmp_label || "";
            if (r > 0) {
                xmpBadgesHtml += `<span style="background: rgba(212, 175, 55, 0.15); color: var(--gold); border: 1px solid rgba(212, 175, 55, 0.25); padding: 1px 4px; font-size: 0.6rem; font-weight: 700; border-radius: 3px; display: inline-flex; align-items: center; gap: 2px;">★${r}</span>`;
            }
            if (lbl) {
                const colorHexes = { "red": "#ff453a", "orange": "#ff9f0a", "yellow": "#ffd60a", "green": "#30d158", "blue": "#0a84ff", "purple": "#bf5af2", "grey": "#8e8e93", "gray": "#8e8e93" };
                const dotColor = colorHexes[lbl.toLowerCase()] || 'rgba(255,255,255,0.3)';
                xmpBadgesHtml += `<span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:${dotColor}; margin-left:4px; vertical-align:middle; box-shadow:0 0 4px ${dotColor};"></span>`;
            }

            dupCard.innerHTML = `
                <div class="card-image-wrap">
                    <!-- RAW Format Badge Overlay -->
                    ${rawBadgeHtml}
                    
                    <!-- Keep/Discard Selection Checkbox -->
                    <div class="${checkboxClass}">
                        <svg class="check-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3.5" style="${checkIconStyle}">
                            <polyline points="20 6 9 17 4 12"></polyline>
                        </svg>
                    </div>
                    
                    <!-- Compare Button Overlay -->
                    ${compareBtnHtml}
                    
                    <img src="${photo.url}&maxWidth=400" alt="Photo">
                    
                    <!-- Fix Blink Overlay if blink detected -->
                    ${fixBlinkBtnHtml}
                    
                    <!-- Bottom Info Overlay -->
                    <div class="img-bottom-overlay">
                        ${warningsHtml ? `<div class="overlay-warnings-row" style="margin-bottom:4px; display:flex; flex-wrap:wrap; gap:4px;">${warningsHtml}</div>` : ''}
                        <div class="overlay-meta-row">
                            <span class="overlay-filename" title="${photo.filename}">${photo.display_name || photo.filename}</span>
                            <span class="overlay-score" style="display:flex; align-items:center; gap:4px;">${photo.metrics.overall_score}% ${bestTagHtml} ${xmpBadgesHtml}</span>
                        </div>
                    </div>
                </div>
            `;
            
            // Click toggles discard state (Card click)
            dupCard.addEventListener('click', (e) => {
                if (e.target.closest('.img-overlay-btn') || e.target.closest('.btn-fix-blink-overlay')) {
                    return;
                }
                toggleDiscard(photo.filename, !isDiscarded);
            });
            
            rowList.appendChild(dupCard);
        });
        
        grid.appendChild(rowList);
        groupCard.appendChild(grid);
        groupsFeed.appendChild(groupCard);
    });

    // 2. Render Unique Photos Accordion (only in Feed mode to make wizard queue focused)
    if (reviewMode === 'feed' && uniqueGroups.length > 0) {
        const uniqueWrapper = document.createElement('div');
        uniqueWrapper.className = 'duplicate-group-card borderless';
        uniqueWrapper.innerHTML = `
            <div class="group-card-header" style="border-bottom:none; cursor:pointer; padding: 0.5rem 0;" onclick="toggleUniqueAccordion(this)">
                <div class="group-header-left" style="display:flex; align-items:center; gap:0.5rem;">
                    <svg id="accordion-arrow" style="width:10px; height:10px; transition:transform 0.2s; color: var(--text-secondary);" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
                        <polyline points="9 18 15 12 9 6"></polyline>
                    </svg>
                    <span class="group-title-text">UNIQUE PHOTOS</span>
                    <span class="group-meta-divider">•</span>
                    <span class="group-count-text">${uniqueGroups.length} PHOTOS FOUND</span>
                </div>
                <span class="badge-unique-tag">SAFE KEEP</span>
            </div>
            <div class="unique-grid hidden" id="unique-accordion-body" style="padding-top:1rem; border-top:1px solid rgba(255,255,255,0.04);">
                <div class="duplicates-row-list">
                    ${uniqueGroups.map(g => {
                        const p = g.photos[0];
                        let uniqueWarningsHtml = '';
                        if (p.metrics) {
                            if (p.metrics.is_blurry) {
                                uniqueWarningsHtml += `<span class="card-warning-badge blur-warning">⚠ Blur</span>`;
                            }
                            const notes = p.metrics.analysis_notes || [];
                            const isOver = notes.some(note => note.includes("Over-exposed"));
                            const isUnder = notes.some(note => note.includes("Under-exposed"));
                            if (isOver) {
                                uniqueWarningsHtml += `<span class="card-warning-badge over-warning">☀ Overexposed</span>`;
                            } else if (isUnder) {
                                uniqueWarningsHtml += `<span class="card-warning-badge under-warning">🌑 Underexposed</span>`;
                            }
                        }
                        return `
                            <div class="duplicate-sub-card is-kept">
                                <div class="card-image-wrap">
                                    <img src="${p.url}" alt="Unique Photo">
                                    <div class="img-bottom-overlay">
                                        ${uniqueWarningsHtml ? `<div class="overlay-warnings-row" style="margin-bottom:4px; display:flex; flex-wrap:wrap; gap:4px;">${uniqueWarningsHtml}</div>` : ''}
                                        <div class="overlay-meta-row">
                                            <span class="overlay-filename" title="${p.filename}">${p.display_name || p.filename}</span>
                                            <span class="overlay-score">${p.metrics.overall_score}%</span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        `;
                    }).join('')}
                </div>
            </div>
        `;
        groupsFeed.appendChild(uniqueWrapper);
    }

    if (activeJobId) {
        setupViewportPriorityTracking(activeJobId);
    }
}

let viewportObserver = null;
let visiblePathsSet = new Set();
let viewportUpdateTimeout = null;

function setupViewportPriorityTracking(jobId) {
    if (viewportObserver) {
        viewportObserver.disconnect();
    }
    visiblePathsSet.clear();
    
    viewportObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            const card = entry.target;
            const path = card.getAttribute('data-path');
            if (!path) return;
            
            if (entry.isIntersecting) {
                visiblePathsSet.add(path);
            } else {
                visiblePathsSet.delete(path);
            }
        });
        
        clearTimeout(viewportUpdateTimeout);
        viewportUpdateTimeout = setTimeout(() => {
            const visiblePaths = Array.from(visiblePathsSet);
            const nearbyPaths = [];
            
            if (window.pywebview && window.pywebview.api && jobId) {
                window.pywebview.api.update_viewport_priority(jobId, visiblePaths, nearbyPaths);
            }
        }, 300);
    }, {
        root: null,
        threshold: 0.1
    });
    
    document.querySelectorAll('.duplicate-sub-card').forEach(card => {
        viewportObserver.observe(card);
    });
}

function pollBackgroundAI(jobId) {
    const bgAiBadge = document.getElementById('bg-ai-badge');
    const bgAiBadgeText = document.getElementById('bg-ai-badge-text');
    if (!bgAiBadge) return;
    
    bgAiBadge.classList.remove('hidden');
    
    const bgInterval = setInterval(async () => {
        try {
            const jobState = await window.pywebview.api.get_job_status(jobId);
            if (!jobState || !jobState.background_ai) {
                clearInterval(bgInterval);
                bgAiBadge.classList.add('hidden');
                return;
            }
            
            const bg = jobState.background_ai;
            bgAiBadgeText.textContent = `Indexing Faces: ${bg.progress}/${bg.total}`;
            
            if (bg.status === 'completed') {
                clearInterval(bgInterval);
                bgAiBadgeText.textContent = "Faces Indexed";
                setTimeout(() => {
                    bgAiBadge.classList.add('hidden');
                }, 3000);
            }
        } catch (err) {
            console.error("Error polling background AI:", err);
            clearInterval(bgInterval);
            bgAiBadge.classList.add('hidden');
        }
    }, 1000);
}

// Helper to escape slashes/quotes in JS string arguments inside onclick handlers
function escapeString(str) {
    return str.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
}

function renderMetricBar(label, value, colorClass = '') {
    return `
        <div class="metric-bar-item">
            <div class="metric-bar-header">
                <span>${label}</span>
                <span class="metric-bar-val">${value}%</span>
            </div>
            <div class="metric-bar-bg">
                <div class="metric-bar-fill ${colorClass}" style="width: ${value}%;"></div>
            </div>
        </div>
    `;
}

function toggleUniqueAccordion(header) {
    const arrow = header.querySelector('#accordion-arrow');
    const body = document.getElementById('unique-accordion-body');
    if (body.classList.contains('hidden')) {
        body.classList.remove('hidden');
        arrow.style.transform = 'rotate(90deg)';
    } else {
        body.classList.add('hidden');
        arrow.style.transform = 'rotate(0deg)';
    }
}

// Discard/Keep toggle
function toggleDiscard(filename, shouldDiscard) {
    if (shouldDiscard) {
        discardedFiles.add(filename);
        keptFiles.delete(filename);
    } else {
        discardedFiles.delete(filename);
        keptFiles.add(filename);
    }
    renderDuplicateGroups();
    updateStatsAndExportBar();
}

// Batch keep only best pick in a cluster
function keepOnlyBest(groupId) {
    const group = duplicateGroups.find(g => g.group_id === groupId);
    if (!group) return;
    
    group.photos.forEach(photo => {
        if (photo.is_best) {
            keptFiles.add(photo.filename);
            discardedFiles.delete(photo.filename);
        } else {
            discardedFiles.add(photo.filename);
            keptFiles.delete(photo.filename);
        }
    });
    
    renderDuplicateGroups();
    updateStatsAndExportBar();
}

// Batch discard all non-best duplicates across all groups
function discardAllDuplicates() {
    const dupGroups = duplicateGroups.filter(g => g.is_duplicate_group);
    if (dupGroups.length === 0) return;
    
    let count = 0;
    dupGroups.forEach(group => {
        group.photos.forEach(photo => {
            if (photo.is_best) {
                keptFiles.add(photo.filename);
                discardedFiles.delete(photo.filename);
            } else {
                discardedFiles.add(photo.filename);
                keptFiles.delete(photo.filename);
                count++;
            }
        });
    });
    
    renderDuplicateGroups();
    updateStatsAndExportBar();
}

// Swap Recommendation Choice manually
function swapBestPick(groupId, newBestFilename) {
    const group = duplicateGroups.find(g => g.group_id === groupId);
    if (!group) return;
    
    group.photos.forEach(photo => {
        if (photo.filename === newBestFilename) {
            photo.is_best = true;
            keptFiles.add(photo.filename);
            discardedFiles.delete(photo.filename);
        } else {
            photo.is_best = false;
            discardedFiles.add(photo.filename);
            keptFiles.delete(photo.filename);
        }
    });
    
    const bestPhoto = group.photos.find(p => p.is_best);
    group.best_pick = bestPhoto.url;
    
    renderDuplicateGroups();
    updateStatsAndExportBar();
}

// Stats & Export Panel state synchronizer
function updateStatsAndExportBar() {
    const totalFiles = keptFiles.size + discardedFiles.size;
    
    // Space calculation
    let reclaimableKb = 0;
    duplicateGroups.forEach(group => {
        group.photos.forEach(photo => {
            if (discardedFiles.has(photo.filename)) {
                reclaimableKb += photo.file_size_kb;
            }
        });
    });
    
    animateSpaceCounter(statSpaceSavedVal, reclaimableKb);
    animateSpaceCounter(toolbarStatSpaceVal, reclaimableKb);
    
    // Display export controls
    const appMain = document.querySelector('.app-main');
    if (totalFiles > 0 && duplicateGroups.length > 0) {
        if (appMain) {
            appMain.classList.add('has-results');
            document.body.classList.add('has-results');
        }
        animateCounter(exportPhotoCount, keptFiles.size);
        animateCounter(exportDuplicateCount, discardedFiles.size);
        
        // Update Discard All button text count
        const btnDiscardAll = document.getElementById('btn-discard-all');
        if (btnDiscardAll) {
            btnDiscardAll.title = "Clean up duplicates by moving them to the duplicates_backup folder";
            btnDiscardAll.innerHTML = `
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:12px; height:12px; margin-right: 3px; display: inline-block; vertical-align: middle;">
                    <polyline points="3 6 5 6 21 6"></polyline>
                    <path d="M19 6l-2 14H7L5 6"></path>
                    <path d="M10 11v6"></path>
                    <path d="M14 11v6"></path>
                </svg>
                Discard All (${discardedFiles.size})
            `;
        }
        
        btnDownloadZip.classList.remove('hidden');
        btnDownloadZip.disabled = keptFiles.size === 0;
        btnDeleteDiscarded.classList.add('hidden');
        btnBackupLocal.classList.remove('hidden');
        btnBackupCount.textContent = discardedFiles.size;
        btnBackupLocal.disabled = discardedFiles.size === 0;
        

    } else {
        closeExportModal();
        if (appMain) {
            appMain.classList.remove('has-results');
            document.body.classList.remove('has-results');
        }
    }
}

// Delete Selected uploads (Used in permanent deletion mode)
function deleteDiscardedPhotos() {
    if (!isLicenseActive) {
        showLicensingOverlay();
        return;
    }
    if (discardedFiles.size === 0) return;
    
    const count = discardedFiles.size;
    showDestructiveConfirm(
        'Delete Duplicate Photos',
        `You are about to permanently delete the ${count} discarded duplicate photos from your disk storage. This will free up file system space.`,
        `This will irreversibly delete ${count} image files from their local directory locations. To proceed, authorize below.`,
        () => {
            const filesArray = Array.from(discardedFiles);
            
            // Snapshot of states for transactional rollback
            const snapshotDiscarded = new Set(discardedFiles);
            const snapshotKept = new Set(keptFiles);
            const snapshotGroups = JSON.parse(JSON.stringify(duplicateGroups));
            
            if (window.pywebview && window.pywebview.api) {
                window.pywebview.api.delete_photos(filesArray)
                .then(success => {
                    if (success) {
                        uploadedFiles = uploadedFiles.filter(file => !discardedFiles.has(file.filename));
                        
                        duplicateGroups.forEach(group => {
                            group.photos = group.photos.filter(p => !discardedFiles.has(p.filename));
                        });
                        
                        duplicateGroups = duplicateGroups.filter(group => group.photos.length > 0);
                        duplicateGroups.forEach(group => {
                            group.is_duplicate_group = group.photos.length > 1;
                            const hasBest = group.photos.some(p => p.is_best);
                            if (!hasBest && group.photos.length > 0) {
                                group.photos[0].is_best = true;
                                keptFiles.add(group.photos[0].filename);
                            }
                        });
                        
                        // Adjust wizard paging constraints
                        const dupGroups = duplicateGroups.filter(g => g.is_duplicate_group);
                        if (currentWizardIndex >= dupGroups.length) {
                            currentWizardIndex = Math.max(0, dupGroups.length - 1);
                        }
                        
                        discardedFiles.clear();
                        renderDuplicateGroups();
                        updateStatsAndExportBar();
                        
                        alert(`Successfully permanently deleted ${filesArray.length} duplicates!`);
                    } else {
                        // Rollback state in case of failure
                        discardedFiles = snapshotDiscarded;
                        keptFiles = snapshotKept;
                        duplicateGroups = snapshotGroups;
                        renderDuplicateGroups();
                        updateStatsAndExportBar();
                        alert('Failed to delete photos. Filesystem changes rolled back.');
                    }
                }).catch(err => {
                    // Rollback state in case of error
                    discardedFiles = snapshotDiscarded;
                    keptFiles = snapshotKept;
                    duplicateGroups = snapshotGroups;
                    renderDuplicateGroups();
                    updateStatsAndExportBar();
                    alert('Error deleting photos: ' + err + '. State rolled back.');
                });
            }
        }
    );
}

// In-place local move (Used in local folder mode)
function backupLocalDuplicates() {
    if (!isLicenseActive) {
        showLicensingOverlay();
        return;
    }
    if (discardedFiles.size === 0) return;
    
    const count = discardedFiles.size;
    showDestructiveConfirm(
        'Archive Local Duplicates',
        `You are about to archive the ${count} duplicates by moving them into a 'duplicates_backup/' folder inside your scanned directory on your computer.`,
        `This will move ${count} duplicates into 'duplicates_backup/'. If a filesystem issue happens mid-transaction, files are automatically restored to their starting points.`,
        () => {
            const filesArray = Array.from(discardedFiles);
            
            // Snapshot of states for transactional rollback
            const snapshotDiscarded = new Set(discardedFiles);
            const snapshotKept = new Set(keptFiles);
            const snapshotGroups = JSON.parse(JSON.stringify(duplicateGroups));
            
            if (window.pywebview && window.pywebview.api) {
                window.pywebview.api.clean_local(scannedDir, filesArray)
                .then(movedCount => {
                    if (movedCount >= 0) {
                        // Update local states: remove duplicates from list
                        duplicateGroups.forEach(group => {
                            group.photos = group.photos.filter(p => !discardedFiles.has(p.filename));
                        });
                        
                        duplicateGroups = duplicateGroups.filter(group => group.photos.length > 0);
                        duplicateGroups.forEach(group => {
                            group.is_duplicate_group = group.photos.length > 1;
                            const hasBest = group.photos.some(p => p.is_best);
                            if (!hasBest && group.photos.length > 0) {
                                group.photos[0].is_best = true;
                                keptFiles.add(group.photos[0].filename);
                            }
                        });
                        
                        const dupGroups = duplicateGroups.filter(g => g.is_duplicate_group);
                        if (currentWizardIndex >= dupGroups.length) {
                            currentWizardIndex = Math.max(0, dupGroups.length - 1);
                        }
                        
                        discardedFiles.clear();
                        renderDuplicateGroups();
                        updateStatsAndExportBar();
                        closeExportModal();
                        
                        alert(`Successfully archived ${movedCount} duplicates into backup!`);
                    } else {
                        // Rollback state in case of failure
                        discardedFiles = snapshotDiscarded;
                        keptFiles = snapshotKept;
                        duplicateGroups = snapshotGroups;
                        renderDuplicateGroups();
                        updateStatsAndExportBar();
                        alert('Failed to clean local directory. State rolled back.');
                    }
                }).catch(err => {
                    // Rollback state in case of error
                    discardedFiles = snapshotDiscarded;
                    keptFiles = snapshotKept;
                    duplicateGroups = snapshotGroups;
                    renderDuplicateGroups();
                    updateStatsAndExportBar();
                    alert('Error archiving duplicates: ' + err + '. State rolled back.');
                });
            }
        }
    );
}

// Side-by-Side Comparison details Modal
function comparePhotos(filenameA, filenameB) {
    let photoA = null;
    let photoB = null;
    
    duplicateGroups.forEach(group => {
        const pA = group.photos.find(p => p.filename === filenameA);
        const pB = group.photos.find(p => p.filename === filenameB);
        if (pA) photoA = pA;
        if (pB) photoB = pB;
    });
    
    if (!photoA || !photoB) return;
    
    // Trigger background preloading of adjacent images
    if (window.pywebview && window.pywebview.api) {
        const allPaths = [];
        duplicateGroups.forEach(g => {
            g.photos.forEach(p => {
                allPaths.push(p.path);
            });
        });
        window.pywebview.api.preload_images(photoA.path, allPaths);
        window.pywebview.api.preload_images(photoB.path, allPaths);
    }
    
    leftImg.src = `${photoA.url}&maxWidth=1200`;
    rightImg.src = `${photoB.url}&maxWidth=1200`;
    
    leftBadge.textContent = photoA.is_best ? "Best Pick" : "Duplicate";
    leftBadge.className = `compare-badge badge-${photoA.is_best ? 'gold' : 'purple'}`;
    rightBadge.textContent = photoB.is_best ? "Best Pick" : "Duplicate";
    rightBadge.className = `compare-badge badge-${photoB.is_best ? 'gold' : 'purple'}`;
    
    leftScore.textContent = `Quality: ${photoA.metrics.overall_score}%`;
    rightScore.textContent = `Quality: ${photoB.metrics.overall_score}%`;
    
    renderFaceBoxes(photoA, leftFaceOverlay);
    renderFaceBoxes(photoB, rightFaceOverlay);
    
    renderCompareMetrics(photoA, leftMetrics);
    renderCompareMetrics(photoB, rightMetrics);
    
    toggleModalOpen('compare-modal', true);
}

function renderFaceBoxes(photo, overlayEl) {
    overlayEl.innerHTML = '';
    if (photo.metrics.faces_detected === 0) return;
    
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', `0 0 ${photo.width} ${photo.height}`);
    svg.style.position = 'absolute';
    svg.style.top = '0';
    svg.style.left = '0';
    svg.style.width = '100%';
    svg.style.height = '100%';
    
    // Respect current state of the toggle checkbox
    const toggleFocusHeatmap = document.getElementById('toggle-focus-heatmap');
    if (toggleFocusHeatmap && !toggleFocusHeatmap.checked) {
        svg.style.display = 'none';
    }

    const devMode = document.getElementById('toggle-developer-mode');
    const isDevMode = devMode && devMode.checked;
    const fontSize = Math.max(12, photo.height / 35);
    const smallFontSize = Math.max(10, photo.height / 50);
    const strokeW = Math.max(2, photo.width / 400);
    
    photo.metrics.faces.forEach((face, idx) => {
        // Face box rect (Standard brand Electric Blue #5B4BFF)
        const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        rect.setAttribute('x', face.x);
        rect.setAttribute('y', face.y);
        rect.setAttribute('width', face.w);
        rect.setAttribute('height', face.h);
        rect.setAttribute('fill', 'none');
        rect.setAttribute('stroke', '#5B4BFF');
        rect.setAttribute('stroke-width', strokeW.toFixed(0));
        rect.setAttribute('filter', 'drop-shadow(0px 0px 4px rgba(91, 75, 255, 0.4))');
        
        // Text tag
        const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        text.setAttribute('x', face.x);
        text.setAttribute('y', face.y - (photo.height / 100));
        text.setAttribute('fill', '#FFFFFF');
        text.setAttribute('font-size', fontSize.toFixed(0));
        text.setAttribute('font-family', "'Outfit', sans-serif");
        text.setAttribute('font-weight', 'bold');
        text.textContent = `Face #${idx + 1} (${face.sharpness}% sharp)`;
        
        svg.appendChild(rect);
        svg.appendChild(text);

        // Developer Mode: extra info panel
        if (isDevMode) {
            const conf = face.confidence !== undefined ? (face.confidence * 100).toFixed(1) : '—';
            const orient = face.orientation || {};
            const roll = orient.roll !== undefined ? orient.roll.toFixed(1) : '—';
            const pitch = orient.pitch !== undefined ? orient.pitch.toFixed(1) : '—';
            const yaw = orient.yaw !== undefined ? orient.yaw.toFixed(1) : '—';
            const hasEmb = face.embedding && face.embedding.length > 0 ? '✓' : '✗';
            const qSharp = face.quality ? face.quality.sharpness : face.sharpness;
            const qExpos = face.quality ? face.quality.exposure : (face.face_exposure || '—');
            
            const clusterId = face.cluster_id !== undefined && face.cluster_id !== null ? face.cluster_id : 'None';
            const matchScore = face.matching_score !== undefined && face.matching_score !== null ? (face.matching_score * 100).toFixed(1) : '—';
            const clusterSize = face.cluster_size !== undefined && face.cluster_size !== null ? face.cluster_size : 0;
            const identityState = face.identity_state || 'unclustered';
            const personId = face.person_id !== undefined && face.person_id !== null ? face.person_id : 'None';
            const personName = face.person_name || 'Unresolved';
            
            const smileVal = face.smile_confidence !== undefined ? face.smile_confidence.toFixed(1) : '—';
            const occlVal = face.occlusion_score !== undefined ? face.occlusion_score.toFixed(1) : '—';
            const lightVal = face.lighting_quality !== undefined ? face.lighting_quality.toFixed(1) : '—';
            const exprVal = face.expression_score !== undefined ? face.expression_score.toFixed(1) : '—';
            const poseQVal = face.head_pose_score !== undefined ? face.head_pose_score.toFixed(1) : '—';
            const faceQVal = face.face_quality_score !== undefined ? face.face_quality_score.toFixed(1) : '—';
            const lookCam = face.looking_at_camera ? 'Yes' : 'No';

            // Semi-translucent background box
            const bgRect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
            bgRect.setAttribute('x', face.x);
            bgRect.setAttribute('y', face.y + face.h + 2);
            bgRect.setAttribute('width', face.w);
            bgRect.setAttribute('height', smallFontSize * 14.5);
            bgRect.setAttribute('fill', 'rgba(0,0,0,0.78)');
            bgRect.setAttribute('rx', '4');
            svg.appendChild(bgRect);

            const lines = [
                `Conf: ${conf}%  Emb: ${hasEmb}`,
                `Roll: ${roll}° Pitch: ${pitch}°`,
                `Yaw: ${yaw}°`,
                `Sharp: ${qSharp}  Exp: ${qExpos}`,
                `Cluster ID: ${clusterId}`,
                `Match: ${matchScore}%  Size: ${clusterSize}`,
                `State: ${identityState}`,
                `Person: ${personName} (#${personId})`,
                `Smile: ${smileVal}%  Occl: ${occlVal}%`,
                `Lighting: ${lightVal}%`,
                `Expr: ${exprVal}%  PoseQ: ${poseQVal}%`,
                `Look Cam: ${lookCam}`,
                `Face Quality: ${faceQVal}%`
            ];
            lines.forEach((line, li) => {
                const t = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                t.setAttribute('x', face.x + 4);
                t.setAttribute('y', face.y + face.h + 4 + smallFontSize * (li + 1));
                t.setAttribute('fill', '#00E5FF');
                t.setAttribute('font-size', smallFontSize.toFixed(0));
                t.setAttribute('font-family', "'Outfit', monospace");
                t.textContent = line;
                svg.appendChild(t);
            });
        }

        // Draw left eye polygon overlay (Focal Heatmap)
        if (face.left_eye_landmarks && face.left_eye_landmarks.length > 0) {
            const leftPoly = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
            const leftPointsStr = face.left_eye_landmarks.map(pt => `${pt[0]},${pt[1]}`).join(' ');
            leftPoly.setAttribute('points', leftPointsStr);
            const isOpen = face.eye_openness >= 50;
            const leftColor = isOpen ? 'rgba(34, 197, 94, 0.35)' : 'rgba(239, 68, 68, 0.45)';
            const leftStroke = isOpen ? 'rgba(34, 197, 94, 0.75)' : 'rgba(239, 68, 68, 0.85)';
            leftPoly.setAttribute('fill', leftColor);
            leftPoly.setAttribute('stroke', leftStroke);
            leftPoly.setAttribute('stroke-width', Math.max(1, photo.width / 800).toFixed(0));
            svg.appendChild(leftPoly);
        }

        // Draw right eye polygon overlay (Focal Heatmap)
        if (face.right_eye_landmarks && face.right_eye_landmarks.length > 0) {
            const rightPoly = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
            const rightPointsStr = face.right_eye_landmarks.map(pt => `${pt[0]},${pt[1]}`).join(' ');
            rightPoly.setAttribute('points', rightPointsStr);
            const isOpen = face.eye_openness >= 50;
            const rightColor = isOpen ? 'rgba(34, 197, 94, 0.35)' : 'rgba(239, 68, 68, 0.45)';
            const rightStroke = isOpen ? 'rgba(34, 197, 94, 0.75)' : 'rgba(239, 68, 68, 0.85)';
            rightPoly.setAttribute('fill', rightColor);
            rightPoly.setAttribute('stroke', rightStroke);
            rightPoly.setAttribute('stroke-width', Math.max(1, photo.width / 800).toFixed(0));
            svg.appendChild(rightPoly);
        }
    });
    
    overlayEl.appendChild(svg);
}

function isRawFile(filename) {
    const ext = filename.split('.').pop().toLowerCase();
    return ['cr2', 'cr3', 'nef', 'nrw', 'arw', 'orf', 'raf', 'rw2', 'dng', 'pef', 'x3f'].includes(ext);
}

window.setXmpRating = function(imagePath, rating) {
    updateXmp(imagePath, rating, null, null);
};

window.setXmpLabel = function(imagePath, label) {
    updateXmp(imagePath, null, label, null);
};

window.toggleXmpReject = function(imagePath, rejected) {
    updateXmp(imagePath, null, null, rejected);
};

async function updateXmp(imagePath, newRating, newLabel, newRejected) {
    if (!window.pywebview || !window.pywebview.api) return;
    
    let targetPhoto = null;
    duplicateGroups.forEach(group => {
        const found = group.photos.find(p => p.path === imagePath);
        if (found) targetPhoto = found;
    });
    
    if (!targetPhoto) return;
    
    const rating = newRating !== null ? newRating : (targetPhoto.metrics.xmp_rating || 0);
    const label = newLabel !== null ? newLabel : (targetPhoto.metrics.xmp_label || "");
    const rejected = newRejected !== null ? newRejected : (targetPhoto.metrics.xmp_rejected || false);
    
    const success = await window.pywebview.api.write_xmp_metadata(imagePath, rating, label, rejected);
    if (success) {
        targetPhoto.metrics.xmp_rating = rating;
        targetPhoto.metrics.xmp_label = label;
        targetPhoto.metrics.xmp_rejected = rejected;
        
        if (rejected) {
            discardedFiles.add(targetPhoto.filename);
            keptFiles.delete(targetPhoto.filename);
        } else {
            if (rating >= 3) {
                discardedFiles.delete(targetPhoto.filename);
                keptFiles.add(targetPhoto.filename);
            }
        }
        
        const leftImgEl = document.getElementById('left-img');
        const rightImgEl = document.getElementById('right-img');
        
        if (leftImgEl && leftImgEl.src.includes(encodeURIComponent(imagePath))) {
            const leftMetricsContainer = document.getElementById('left-metrics');
            renderCompareMetrics(targetPhoto, leftMetricsContainer);
        }
        if (rightImgEl && rightImgEl.src.includes(encodeURIComponent(imagePath))) {
            const rightMetricsContainer = document.getElementById('right-metrics');
            renderCompareMetrics(targetPhoto, rightMetricsContainer);
        }
        
        renderDuplicateGroups();
    } else {
        alert("Failed to write metadata changes to XMP sidecar.");
    }
}

function renderCompareMetrics(photo, metricsContainer) {
    const camera = photo.metrics.camera_model || "Unknown";
    const lens = photo.metrics.lens || "Unknown";
    const iso = photo.metrics.iso || "N/A";
    const shutter = photo.metrics.shutter_speed || "N/A";
    const aperture = photo.metrics.aperture ? `f/${photo.metrics.aperture}` : "N/A";
    
    const xmpRating = photo.metrics.xmp_rating || 0;
    const xmpLabel = photo.metrics.xmp_label || "";
    const xmpRejected = photo.metrics.xmp_rejected || false;
    
    let starsHtml = '';
    for (let s = 1; s <= 5; s++) {
        const starColor = s <= xmpRating ? 'var(--gold)' : 'rgba(255,255,255,0.2)';
        starsHtml += `<span class="star-clickable" onclick="setXmpRating('${escapeString(photo.path)}', ${s})" style="cursor:pointer; font-size:1.15rem; color:${starColor}; margin-right:4px; transition:color 0.1s;">★</span>`;
    }
    starsHtml += `<span onclick="setXmpRating('${escapeString(photo.path)}', 0)" style="cursor:pointer; font-size:0.75rem; color:var(--text-muted); margin-left:6px; text-decoration:underline; vertical-align:middle;">clear</span>`;

    const colors = ["Red", "Orange", "Yellow", "Green", "Blue", "Purple", "Grey"];
    const colorHexes = {
        "Red": "#ff453a",
        "Orange": "#ff9f0a",
        "Yellow": "#ffd60a",
        "Green": "#30d158",
        "Blue": "#0a84ff",
        "Purple": "#bf5af2",
        "Grey": "#8e8e93"
    };
    let colorsHtml = '';
    colors.forEach(c => {
        const activeOutline = xmpLabel.toLowerCase() === c.toLowerCase() ? 'outline: 2px solid #fff; outline-offset: 1px; transform: scale(1.15); opacity: 1;' : 'opacity: 0.55;';
        colorsHtml += `<span onclick="setXmpLabel('${escapeString(photo.path)}', '${c}')" style="cursor:pointer; display:inline-block; width:13px; height:13px; border-radius:50%; background:${colorHexes[c]}; margin-right:8px; ${activeOutline} transition:all 0.1s;"></span>`;
    });
    colorsHtml += `<span onclick="setXmpLabel('${escapeString(photo.path)}', '')" style="cursor:pointer; font-size:0.75rem; color:var(--text-muted); text-decoration:underline; margin-left:4px; vertical-align:middle;">clear</span>`;

    const rejectChecked = xmpRejected ? 'checked' : '';
    const rejectCheckboxHtml = `<label style="cursor:pointer; color:${xmpRejected ? 'var(--red)' : 'var(--text-secondary)'}; font-weight:600; display:flex; align-items:center; gap:6px; user-select:none; margin:0;">
        <input type="checkbox" ${rejectChecked} onchange="toggleXmpReject('${escapeString(photo.path)}', this.checked)" style="cursor:pointer; accent-color:var(--red); width:14px; height:14px;">
        REJECT
    </label>`;

    metricsContainer.innerHTML = `
        <div class="metric-stat-row">
            <span class="metric-stat-label">File Dimensions</span>
            <span class="metric-stat-value">${photo.width} × ${photo.height}</span>
        </div>
        <div class="metric-stat-row">
            <span class="metric-stat-label">DPI Density</span>
            <span class="metric-stat-value">${photo.dpi || 72} DPI</span>
        </div>
        <div class="metric-stat-row">
            <span class="metric-stat-label">File Size</span>
            <span class="metric-stat-value">${photo.file_size_kb} KB</span>
        </div>
        <div class="metric-stat-row">
            <span class="metric-stat-label">Camera</span>
            <span class="metric-stat-value" title="${camera}">${camera}</span>
        </div>
        <div class="metric-stat-row">
            <span class="metric-stat-label">Lens</span>
            <span class="metric-stat-value" title="${lens}">${lens}</span>
        </div>
        <div class="metric-stat-row">
            <span class="metric-stat-label">Exposure Settings</span>
            <span class="metric-stat-value">ISO ${iso} • ${shutter} • ${aperture}</span>
        </div>
        <div class="metric-stat-row" style="border-top: 1px solid rgba(255,255,255,0.06); padding-top:8px; margin-top:4px;">
            <span class="metric-stat-label" style="font-weight:600;">XMP Rating</span>
            <span class="metric-stat-value" style="display:flex; align-items:center;">${starsHtml}</span>
        </div>
        <div class="metric-stat-row">
            <span class="metric-stat-label" style="font-weight:600;">Color Label</span>
            <span class="metric-stat-value" style="display:flex; align-items:center;">${colorsHtml}</span>
        </div>
        <div class="metric-stat-row">
            <span class="metric-stat-label" style="font-weight:600;">Reject status</span>
            <span class="metric-stat-value">${rejectCheckboxHtml}</span>
        </div>
        <div class="metric-stat-row" style="border-top: 1px solid rgba(255,255,255,0.06); padding-top:8px; margin-top:4px;">
            <span class="metric-stat-label">Sharpness Score</span>
            <span class="metric-stat-value">${photo.metrics.sharpness}% (var: ${photo.metrics.laplacian_variance})</span>
        </div>
        <div class="metric-stat-row">
            <span class="metric-stat-label">Exposure Score</span>
            <span class="metric-stat-value">${photo.metrics.brightness}%</span>
        </div>
        <div class="metric-stat-row">
            <span class="metric-stat-label">Contrast Score</span>
            <span class="metric-stat-value">${photo.metrics.contrast}%</span>
        </div>
        <div class="metric-stat-row">
            <span class="metric-stat-label">Saturation Score</span>
            <span class="metric-stat-value">${photo.metrics.saturation}%</span>
        </div>
        <div class="metric-stat-row">
            <span class="metric-stat-label">Composition Framing</span>
            <span class="metric-stat-value">${photo.metrics.composition}%</span>
        </div>
        ${photo.metrics.faces_detected > 0 ? `
        <div class="metric-stat-row">
            <span class="metric-stat-label">Camera Facing</span>
            <span class="metric-stat-value">${photo.metrics.camera_facing}%</span>
        </div>
        ` : ''}
        <div class="metric-stat-row">
            <span class="metric-stat-label">Detected Faces</span>
            <span class="metric-stat-value">${photo.metrics.faces_detected}</span>
        </div>
    `;
}

function closeCompareModal() {
    toggleModalOpen('compare-modal', false);
    leftImg.src = '';
    rightImg.src = '';
}

// Perform blink correction (seamless eye swap) via API
function fixBlink(groupId, targetPath, sourcePath) {
    if (!isLicenseActive) {
        showLicensingOverlay();
        return;
    }
    loadingOverlay.classList.remove('hidden');
    loadingStatus.textContent = "👁 Correcting blink (seamless eye swap)...";
    loadingSubstatus.textContent = "Aligning landmarks and blending eyes.";
    
    if (window.pywebview && window.pywebview.api) {
        window.pywebview.api.fix_blink(targetPath, sourcePath)
        .then(response => {
            loadingOverlay.classList.add('hidden');
            if (response && response.success && response.photo) {
                const group = duplicateGroups.find(g => g.group_id === groupId);
                if (group) {
                    // Ensure the new photo is marked as kept
                    keptFiles.add(response.photo.filename);
                    discardedFiles.delete(response.photo.filename);
                    
                    // Add the new photo to the group's photos
                    group.photos.push(response.photo);
                    
                    // Sort photos in group by quality score descending
                    group.photos.sort((a, b) => b.metrics.overall_score - a.metrics.overall_score);
                    
                    // Recalculate is_best
                    group.photos.forEach((p, idx) => {
                        p.is_best = (idx === 0);
                    });
                
                    // Update best_pick url
                    const bestPhoto = group.photos.find(p => p.is_best);
                    if (bestPhoto) {
                        group.best_pick = bestPhoto.url;
                    }
                    
                    // Re-render and refresh stats
                    renderDuplicateGroups();
                    updateStatsAndExportBar();
                    
                    alert("Blink corrected successfully! The new photo has been added to the group.");
                }
            } else {
                alert('Blink correction failed: ' + (response.error || 'unknown server error'));
            }
        })
        .catch(err => {
            loadingOverlay.classList.add('hidden');
            alert('An error occurred during blink correction: ' + err.message);
            console.error(err);
        });
    }
}

// Open and render Selected Photos keeping gallery
function openSelectedPhotosModal() {
    const modal = document.getElementById('selected-photos-modal');
    const grid = document.getElementById('selected-photos-grid');
    const countEl = document.getElementById('modal-selected-count');
    
    if (!modal || !grid) return;
    
    grid.innerHTML = '';
    countEl.textContent = keptFiles.size;
    
    const selectedPhotos = [];
    duplicateGroups.forEach(group => {
        group.photos.forEach(photo => {
            if (keptFiles.has(photo.filename)) {
                selectedPhotos.push(photo);
            }
        });
    });
    
    if (selectedPhotos.length === 0) {
        grid.innerHTML = '<div style="grid-column: 1/-1; text-align: center; color: var(--text-secondary); padding: 2rem;">No photos selected yet. Mark photos to "Keep" to add them.</div>';
    } else {
        selectedPhotos.forEach(photo => {
            const card = document.createElement('div');
            card.className = 'selected-photo-thumbnail-card';
            card.style.cssText = 'background: rgba(255,255,255,0.02); border: 1px solid var(--border-color); border-radius: 8px; overflow: hidden; display: flex; flex-direction: column;';
            
            card.innerHTML = `
                <div style="aspect-ratio: 4/3; background: #000; overflow: hidden; position: relative;">
                    <img src="${photo.url}&maxWidth=400" style="width: 100%; height: 100%; object-fit: contain;">
                    <span style="position: absolute; bottom: 4px; right: 4px; background: rgba(0,0,0,0.7); color: var(--cyan); font-size: 0.6rem; padding: 1px 4px; border-radius: 2px;">${photo.metrics.overall_score}%</span>
                </div>
                <div style="padding: 0.5rem; display: flex; flex-direction: column; gap: 2px;">
                    <span style="font-size: 0.65rem; color: var(--text-primary); text-overflow: ellipsis; overflow: hidden; white-space: nowrap; display: block;" title="${photo.filename}">${photo.display_name}</span>
                    <span style="font-size: 0.6rem; color: var(--text-muted);">${photo.width}x${photo.height}</span>
                </div>
            `;
            grid.appendChild(card);
        });
    }
    
    toggleModalOpen('selected-photos-modal', true);
}

function closeSelectedPhotosModal() {
    toggleModalOpen('selected-photos-modal', false);
}

function openExportModal() {
    if (exportModal) {
        // Reset success state
        const successSec = document.getElementById('export-success-section');
        const settingsPanel = document.getElementById('advanced-export-options');
        const actionsPanel = document.getElementById('export-actions-panel');
        if (successSec) successSec.classList.add('hidden');
        if (settingsPanel) settingsPanel.classList.remove('hidden');
        if (actionsPanel) actionsPanel.classList.remove('hidden');
        
        updateQualitySliderVisibility();
        
        toggleModalOpen('export-modal', true);
    }
}

function closeExportModal() {
    toggleModalOpen('export-modal', false);
}

// Export cleaned photos API Trigger
function exportCleanedPhotos() {
    if (!isLicenseActive) {
        showLicensingOverlay();
        return;
    }
    if (keptFiles.size === 0) {
        alert('No photos selected to export!');
        return;
    }
    
    const filesArray = Array.from(keptFiles);
    
    let scalePercent = null;
    let width = null;
    let height = null;
    
    const preset = exportResizePreset.value;
    if (preset === 'scale-75') scalePercent = 75;
    else if (preset === 'scale-50') scalePercent = 50;
    else if (preset === '1080p') width = 1080;
    else if (preset === '4k') width = 3840;
    else if (preset === 'custom') {
        width = parseInt(customW.value) || null;
        height = parseInt(customH.value) || null;
        if (!width && !height) {
            alert('Please specify a custom width or height dimensions.');
            return;
        }
    }
    
    const ppi = parseInt(exportPpi.value);
    const format = exportFormat.value;
    
    const applyLighting = document.getElementById('export-lighting-correction') ? document.getElementById('export-lighting-correction').checked : false;
    const applyColor = document.getElementById('export-color-adjustment') ? document.getElementById('export-color-adjustment').checked : false;
    const applyDetailSharpening = document.getElementById('export-detail-sharpening') ? document.getElementById('export-detail-sharpening').checked : false;
    const exportDir = exportDirInput ? exportDirInput.value.trim() : '';
    const quality = exportQualitySlider ? parseInt(exportQualitySlider.value) : 95;
    
    const downloadBtnOriginalHTML = btnDownloadZip.innerHTML;
    btnDownloadZip.disabled = true;
    btnDownloadZip.innerHTML = `<svg class="spinner-inline" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="animation: spin 1s linear infinite; width:14px; height:14px;"><circle cx="12" cy="12" r="10" stroke-dasharray="32" stroke-dashoffset="10"></circle></svg> Processing...`;
    
    if (window.pywebview && window.pywebview.api) {
        window.pywebview.api.export_photos(
            filesArray,
            scalePercent,
            width,
            height,
            ppi,
            format,
            applyLighting,
            applyColor,
            applyDetailSharpening,
            exportDir,
            quality,
            currentCullMode
        )
        .then(jobId => {
            if (!jobId) {
                throw new Error("Failed to initiate export job.");
            }
            pollExportJob(jobId);
        })
        .catch(err => {
            btnDownloadZip.disabled = false;
            btnDownloadZip.innerHTML = downloadBtnOriginalHTML;
            alert('An error occurred during photo export: ' + err.message);
            console.error(err);
        });
    }

    function pollExportJob(jobId) {
        const pollInterval = setInterval(async () => {
            try {
                const jobState = await window.pywebview.api.get_job_status(jobId);
                if (!jobState) {
                    clearInterval(pollInterval);
                    btnDownloadZip.disabled = false;
                    btnDownloadZip.innerHTML = downloadBtnOriginalHTML;
                    alert('Export job state could not be retrieved.');
                    return;
                }

                if (jobState.status === 'running') {
                    const progress = jobState.progress || 0;
                    const total = jobState.total || 0;
                    btnDownloadZip.innerHTML = `<svg class="spinner-inline" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="animation: spin 1s linear infinite; width:14px; height:14px;"><circle cx="12" cy="12" r="10" stroke-dasharray="32" stroke-dashoffset="10"></circle></svg> ${progress}/${total}...`;
                } else if (jobState.status === 'completed') {
                    clearInterval(pollInterval);
                    btnDownloadZip.disabled = false;
                    btnDownloadZip.innerHTML = downloadBtnOriginalHTML;
                    handleExportResponse(jobState.result);
                } else if (jobState.status === 'failed') {
                    clearInterval(pollInterval);
                    btnDownloadZip.disabled = false;
                    btnDownloadZip.innerHTML = downloadBtnOriginalHTML;
                    alert('Export failed: ' + (jobState.error || 'Unknown error'));
                }
            } catch (err) {
                clearInterval(pollInterval);
                btnDownloadZip.disabled = false;
                btnDownloadZip.innerHTML = downloadBtnOriginalHTML;
                alert('Error polling export job: ' + err.message);
            }
        }, 500);
    }

    function handleExportResponse(response) {
        if (response && response.success) {
            // Direct Local Export Flow
            if (response.export_dir) {
                const successSec = document.getElementById('export-success-section');
                const successMsg = document.getElementById('export-success-msg');
                const settingsPanel = document.getElementById('advanced-export-options');
                const actionsPanel = document.getElementById('export-actions-panel');
                
                if (successMsg) {
                    successMsg.textContent = `${response.processed_count} photos successfully exported and enhanced inside folder:\n${response.export_dir}`;
                }
                if (settingsPanel) settingsPanel.classList.add('hidden');
                if (actionsPanel) actionsPanel.classList.add('hidden');
                if (successSec) successSec.classList.remove('hidden');
                
                const btnOpenExportDir = document.getElementById('btn-open-export-dir');
                if (btnOpenExportDir) {
                    btnOpenExportDir.onclick = () => {
                        window.pywebview.api.open_folder(response.export_dir);
                    };
                }
                return;
            }
        } else {
            alert('Export failed: ' + (response ? response.error : 'Unknown error'));
        }
    }
}

// Odometer layout helper
function renderOdometerHTML(valueStr, unitText, labelText) {
    const charsHTML = String(valueStr).split('').map(char => {
        if (char === '.') {
            return `<span class="odo-sep">.</span>`;
        }
        return `<span class="odo-digit">${char}</span>`;
    }).join('');
    
    const unitHTML = unitText ? `<span class="odo-unit">${unitText}</span>` : '';
    const labelHTML = labelText ? `<span class="odo-label">${labelText}</span>` : '';
    
    return `${charsHTML}${unitHTML}${labelHTML}`;
}

// Technical details toggle handler
function toggleCardDetails(btn) {
    const cardInfo = btn.closest('.best-choice-info');
    const drawer = cardInfo.querySelector('.card-details-drawer');
    btn.classList.toggle('active');
    if (drawer.classList.contains('show')) {
        drawer.classList.remove('show');
        btn.innerHTML = `
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:10px; height:10px;">
                <polyline points="6 9 12 15 18 9"></polyline>
            </svg>
            Technical Details
        `;
    } else {
        drawer.classList.add('show');
        btn.innerHTML = `
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:10px; height:10px;">
                <polyline points="18 15 12 9 6 15"></polyline>
            </svg>
            Hide Details
        `;
    }
}

// ── Settings Modal (panel-left as overlay) ──
function openSettingsModal() {
    document.body.classList.add('settings-modal-open');
    const backdrop = document.getElementById('settings-modal-backdrop');
    if (backdrop) backdrop.classList.remove('hidden');
    const gearBtn = document.getElementById('btn-modify-settings');
    if (gearBtn) gearBtn.classList.add('active');
    const gearBtnHeader = document.getElementById('btn-modify-settings-header');
    if (gearBtnHeader) gearBtnHeader.classList.add('active');
}

function closeSettingsModal() {
    document.body.classList.remove('settings-modal-open');
    const backdrop = document.getElementById('settings-modal-backdrop');
    if (backdrop) backdrop.classList.add('hidden');
    const gearBtn = document.getElementById('btn-modify-settings');
    if (gearBtn) gearBtn.classList.remove('active');
    const gearBtnHeader = document.getElementById('btn-modify-settings-header');
    if (gearBtnHeader) gearBtnHeader.classList.remove('active');
}

// ── Camera Lens Progress Circle Updater ──
function updateGauge(percent) {
    const lensFill = document.getElementById('lens-progress-fill');
    const lensPercentage = document.getElementById('lens-percentage');

    if (!lensFill) return;

    // Circumference of r=40 is 2 * pi * 40 ≈ 251.3px
    const circumference = 251.3;
    const offset = circumference - (circumference * (percent / 100));
    lensFill.setAttribute('stroke-dashoffset', offset);

    if (lensPercentage) {
        lensPercentage.textContent = `${Math.round(percent)}%`;
    }
}

// ── Sentry Settings Synchronization ──
let appSettings = {};
function initSettings() {
    if (!window.pywebview || !window.pywebview.api) return;
    window.pywebview.api.get_settings()
        .then(settings => {
            appSettings = settings;
            const optinCheckbox = document.getElementById('settings-sentry-optin');
            if (optinCheckbox) {
                optinCheckbox.checked = settings.sentry_opt_in;
                optinCheckbox.addEventListener('change', (e) => {
                    appSettings.sentry_opt_in = e.target.checked;
                    window.pywebview.api.save_settings(appSettings)
                        .catch(err => console.error('Failed to save settings:', err));
                });
            }
        })
        .catch(err => console.error('Failed to get settings:', err));
}

// ── Model Downloader Progress Polling ──
function checkModelDownloadProgress() {
    if (!window.pywebview || !window.pywebview.api) return;
    
    const overlay = document.getElementById('model-download-overlay');
    const progressFill = document.getElementById('model-download-progress');
    const percentText = document.getElementById('model-download-percent');
    const substatusText = document.getElementById('model-download-substatus');
    
    window.pywebview.api.get_model_download_status()
        .then(status => {
            if (status.status === 'downloading') {
                if (overlay) overlay.classList.remove('hidden');
                if (progressFill) progressFill.style.width = `${status.progress}%`;
                if (percentText) percentText.textContent = `${status.progress}%`;
                if (substatusText && status.progress > 0) {
                    substatusText.textContent = `Downloading AI models... ${status.progress}% complete.`;
                }
                setTimeout(checkModelDownloadProgress, 1000);
            } else if (status.status === 'failed') {
                if (overlay) overlay.classList.remove('hidden');
                if (substatusText) substatusText.textContent = `Failed to download models: ${status.error || 'Unknown error'}. Please restart the application to retry.`;
                if (percentText) percentText.textContent = 'Error';
                if (progressFill) {
                    progressFill.style.width = '100%';
                    progressFill.style.background = 'var(--red)';
                }
            } else if (status.status === 'completed') {
                if (overlay) overlay.classList.add('hidden');
            } else {
                if (status.progress < 100) {
                    setTimeout(checkModelDownloadProgress, 1000);
                }
            }
        })
        .catch(err => console.error('Failed to check model download status:', err));
}

// ── Crash Recovery Session Checker ──
function checkRecoveryCheckpoint() {
    if (!window.pywebview || !window.pywebview.api) return;
    
    window.pywebview.api.get_recovery_checkpoint()
        .then(checkpoint => {
            if (checkpoint) {
                const modal = document.getElementById('recovery-modal');
                const pathEl = document.getElementById('recovery-path');
                const processedEl = document.getElementById('recovery-processed');
                
                if (modal && pathEl && processedEl) {
                    pathEl.textContent = checkpoint.target_path;
                    processedEl.textContent = checkpoint.processed_count;
                    toggleModalOpen('recovery-modal', true);
                    
                    const resumeBtn = document.getElementById('btn-recovery-resume');
                    const ignoreBtn = document.getElementById('btn-recovery-ignore');
                    const closeBtn = document.getElementById('btn-close-recovery-modal');
                    const recoveryModalBackdrop = document.getElementById('recovery-modal-backdrop');
                    
                    const closeRecovery = () => {
                        toggleModalOpen('recovery-modal', false);
                    };
                    
                    if (closeBtn) closeBtn.onclick = closeRecovery;
                    if (recoveryModalBackdrop) recoveryModalBackdrop.onclick = closeRecovery;
                    
                    if (ignoreBtn) {
                        ignoreBtn.onclick = () => {
                            window.pywebview.api.clear_recovery_checkpoint()
                                .then(() => {
                                    closeRecovery();
                                    alert('Recovery checkpoint cleared.');
                                })
                                .catch(err => console.error(err));
                        };
                    }
                    
                    if (resumeBtn) {
                        resumeBtn.onclick = () => {
                            closeRecovery();
                            if (localPathInput) {
                                localPathInput.value = checkpoint.target_path;
                                localPathInput.dispatchEvent(new Event('input'));
                            }
                            if (thresholdSlider) {
                                thresholdSlider.value = checkpoint.threshold;
                                thresholdSlider.dispatchEvent(new Event('input'));
                            }
                            const topPercentSelect = document.getElementById('top-percent-select');
                            if (topPercentSelect) {
                                topPercentSelect.value = checkpoint.top_percent > 0 ? checkpoint.top_percent : '';
                            }
                            runAnalysis(true);
                        };
                    }
                }
            }
        })
        .catch(err => console.error('Failed to check recovery checkpoint:', err));
}

// ── Licensing & Feedback UI Handlers ──

function initLicensing() {
    if (!window.pywebview || !window.pywebview.api) return;
    
    window.pywebview.api.check_license()
        .then(lic => {
            const trialBadge = document.getElementById('trial-badge');
            const activationOverlay = document.getElementById('activation-overlay');
            const expiredOverlay = document.getElementById('expired-overlay');
            const tamperWarningBar = document.getElementById('tamper-warning-bar');
            const expiredWarningBar = document.getElementById('expired-warning-bar');
            
            // Hide all overlays initially
            if (activationOverlay) activationOverlay.classList.add('hidden');
            if (expiredOverlay) expiredOverlay.classList.add('hidden');
            if (tamperWarningBar) tamperWarningBar.classList.add('hidden');
            if (expiredWarningBar) expiredWarningBar.classList.add('hidden');
            if (trialBadge) trialBadge.classList.add('hidden');
            
            // Handle different states
            licenseStatus = lic.status;
            if (lic.status === 'active') {
                isLicenseActive = true;
                if (trialBadge) {
                    trialBadge.classList.remove('hidden');
                    trialBadge.textContent = `Trial: ${lic.days_remaining} Days Remaining`;
                    trialBadge.style.cursor = 'pointer';
                    trialBadge.title = 'Click to activate another license';
                    trialBadge.addEventListener('click', () => {
                        if (activationOverlay) activationOverlay.classList.remove('hidden');
                    });
                }
            } else if (lic.status === 'unactivated') {
                isLicenseActive = false;
                if (activationOverlay) activationOverlay.classList.remove('hidden');
            } else if (lic.status === 'expired') {
                isLicenseActive = false;
                if (expiredWarningBar) expiredWarningBar.classList.remove('hidden');
                disableAppActions('expired');
            } else if (lic.status === 'tampered') {
                isLicenseActive = false;
                if (tamperWarningBar) tamperWarningBar.classList.remove('hidden');
                
                // Format and display the dates in user's local timezone for clarity
                const curTime = lic.current_time ? new Date(lic.current_time).toLocaleString() : 'Unknown';
                const lastTime = lic.last_run_time ? new Date(lic.last_run_time).toLocaleString() : 'Unknown';
                const reasonEl = document.getElementById('tamper-reason');
                if (reasonEl) {
                    reasonEl.textContent = `System clock mismatch. Current Time: ${curTime} | Last Verified Run: ${lastTime}. Please verify your system clock.`;
                }
                
                disableAppActions('tampered');
            }

            // Close button listener for activation overlay
            const closeActivation = document.getElementById('btn-close-activation');
            if (closeActivation) {
                closeActivation.addEventListener('click', () => {
                    if (activationOverlay) activationOverlay.classList.add('hidden');
                });
            }
        })
        .catch(err => console.error('Failed to validate license:', err));
}

function showLicensingOverlay() {
    if (licenseStatus === 'unactivated') {
        const activationOverlay = document.getElementById('activation-overlay');
        if (activationOverlay) activationOverlay.classList.remove('hidden');
    } else {
        const expiredOverlay = document.getElementById('expired-overlay');
        if (expiredOverlay) expiredOverlay.classList.remove('hidden');
    }
}

function disableAppActions(status) {
    const btnAnalyze = document.getElementById('btn-analyze');
    const btnDownloadZip = document.getElementById('btn-download-zip');
    const btnDeleteDiscarded = document.getElementById('btn-delete-discarded');
    const btnBackupLocal = document.getElementById('btn-backup-local');
    const btnFixBlink = document.getElementById('btn-fix-blink-wizard');
    
    if (status === 'tampered') {
        if (btnAnalyze) { btnAnalyze.disabled = true; btnAnalyze.style.opacity = '0.5'; btnAnalyze.title = 'Blocked: License Verification Failed'; }
        if (btnDownloadZip) { btnDownloadZip.disabled = true; btnDownloadZip.style.opacity = '0.5'; btnDownloadZip.title = 'Blocked: License Verification Failed'; }
        if (btnDeleteDiscarded) { btnDeleteDiscarded.disabled = true; btnDeleteDiscarded.style.opacity = '0.5'; }
        if (btnBackupLocal) { btnBackupLocal.disabled = true; btnBackupLocal.style.opacity = '0.5'; }
        if (btnFixBlink) { btnFixBlink.disabled = true; btnFixBlink.style.opacity = '0.5'; }
    } else if (status === 'expired') {
        if (btnAnalyze) { btnAnalyze.style.border = '1px dashed var(--red)'; btnAnalyze.title = 'Evaluation Period Concluded - Click to Renew'; }
        if (btnDownloadZip) { btnDownloadZip.style.border = '1px dashed var(--red)'; btnDownloadZip.title = 'Evaluation Period Concluded - Click to Renew'; }
        if (btnDeleteDiscarded) { btnDeleteDiscarded.style.border = '1px dashed var(--red)'; btnDeleteDiscarded.title = 'Evaluation Period Concluded - Click to Renew'; }
        if (btnBackupLocal) { btnBackupLocal.style.border = '1px dashed var(--red)'; btnBackupLocal.title = 'Evaluation Period Concluded - Click to Renew'; }
    }
}

function setupLicensingUI() {
    const btnActivateSubmit = document.getElementById('btn-activate-submit');
    const btnReactivateSubmit = document.getElementById('btn-reactivate-submit');
    const lnkReactivate = document.getElementById('lnk-reactivate');
    const btnCloseExpired = document.getElementById('btn-close-expired');
    const expiredOverlay = document.getElementById('expired-overlay');
    
    const btnTamperRetry = document.getElementById('btn-tamper-retry');
    const btnTamperReactivate = document.getElementById('btn-tamper-reactivate');
    const activationOverlay = document.getElementById('activation-overlay');
    
    if (btnTamperRetry) {
        btnTamperRetry.addEventListener('click', () => {
            initLicensing();
        });
    }
    if (btnTamperReactivate && activationOverlay) {
        btnTamperReactivate.addEventListener('click', () => {
            activationOverlay.classList.remove('hidden');
        });
    }
    
    if (lnkReactivate && expiredOverlay) {
        lnkReactivate.addEventListener('click', (e) => {
            e.preventDefault();
            expiredOverlay.classList.remove('hidden');
        });
    }
    if (btnCloseExpired && expiredOverlay) {
        btnCloseExpired.addEventListener('click', () => {
            expiredOverlay.classList.add('hidden');
        });
    }
    
    if (btnActivateSubmit) {
        btnActivateSubmit.addEventListener('click', () => {
            const keyInput = document.getElementById('activation-key-input');
            const nameInput = document.getElementById('activation-name-input');
            const emailInput = document.getElementById('activation-email-input');
            const companyInput = document.getElementById('activation-company-input');
            const countryInput = document.getElementById('activation-country-input');
            const typeSelect = document.getElementById('activation-type-input');
            const serverInput = document.getElementById('activation-server-input');
            const errorMsg = document.getElementById('activation-error-msg');
            
            const licenseKey = keyInput ? keyInput.value.trim() : '';
            const name = nameInput ? nameInput.value.trim() : '';
            const email = emailInput ? emailInput.value.trim() : '';
            const company = companyInput ? companyInput.value.trim() : '';
            const country = countryInput ? countryInput.value.trim() : '';
            const photographyType = typeSelect ? typeSelect.value : 'Corporate';
            const serverUrl = serverInput ? serverInput.value.trim() : 'https://quantilecull.com/api';
            
            if (!licenseKey || !name || !email) {
                alert('Please enter Name, Email, and License Key.');
                return;
            }
            
            btnActivateSubmit.disabled = true;
            btnActivateSubmit.textContent = 'Activating...';
            if (errorMsg) errorMsg.classList.add('hidden');
            
            window.pywebview.api.activate_license(licenseKey, name, email, company, country, photographyType, serverUrl)
                .then(res => {
                    btnActivateSubmit.disabled = false;
                    btnActivateSubmit.textContent = 'Activate Now';
                    if (res.success) {
                        alert('QuantileCull Activated Successfully!');
                        location.reload();
                    } else {
                        if (errorMsg) {
                            errorMsg.textContent = res.error || 'Activation failed.';
                            errorMsg.classList.remove('hidden');
                        }
                    }
                })
                .catch(err => {
                    btnActivateSubmit.disabled = false;
                    btnActivateSubmit.textContent = 'Activate Now';
                    if (errorMsg) {
                        errorMsg.textContent = 'Failed to connect: ' + err.message;
                        errorMsg.classList.remove('hidden');
                    }
                });
        });
    }

    if (btnReactivateSubmit) {
        btnReactivateSubmit.addEventListener('click', () => {
            const keyInput = document.getElementById('expired-key-input');
            const errorMsg = document.getElementById('expired-error-msg');
            const licenseKey = keyInput ? keyInput.value.trim() : '';
            
            const nameInput = document.getElementById('activation-name-input');
            const emailInput = document.getElementById('activation-email-input');
            const companyInput = document.getElementById('activation-company-input');
            const countryInput = document.getElementById('activation-country-input');
            const typeSelect = document.getElementById('activation-type-input');
            const serverInput = document.getElementById('activation-server-input');
            
            const name = nameInput ? nameInput.value.trim() : 'Renewed User';
            const email = emailInput ? emailInput.value.trim() : 'renewed@example.com';
            const company = companyInput ? companyInput.value.trim() : '';
            const country = countryInput ? countryInput.value.trim() : '';
            const photographyType = typeSelect ? typeSelect.value : 'Corporate';
            const serverUrl = serverInput ? serverInput.value.trim() : 'https://quantilecull.com/api';
            
            if (!licenseKey) {
                alert('Please enter a license key.');
                return;
            }
            
            btnReactivateSubmit.disabled = true;
            btnReactivateSubmit.textContent = 'Activating...';
            if (errorMsg) errorMsg.classList.add('hidden');
            
            window.pywebview.api.activate_license(licenseKey, name, email, company, country, photographyType, serverUrl)
                .then(res => {
                    btnReactivateSubmit.disabled = false;
                    btnReactivateSubmit.textContent = 'Re-Activate License';
                    if (res.success) {
                        alert('QuantileCull Re-Activated Successfully!');
                        location.reload();
                    } else {
                        if (errorMsg) {
                            errorMsg.textContent = res.error || 'Re-activation failed.';
                            errorMsg.classList.remove('hidden');
                        }
                    }
                })
                .catch(err => {
                    btnReactivateSubmit.disabled = false;
                    btnReactivateSubmit.textContent = 'Re-Activate License';
                    if (errorMsg) {
                        errorMsg.textContent = 'Failed to connect: ' + err.message;
                        errorMsg.classList.remove('hidden');
                    }
                });
        });
    }
}

function setupFeedbackUI() {
    const btnOpenFeedback = document.getElementById('btn-open-feedback');
    const btnCloseFeedback = document.getElementById('btn-close-feedback');
    const feedbackModal = document.getElementById('feedback-modal');
    const feedbackForm = document.getElementById('feedback-form');
    const feedbackSuccessMsg = document.getElementById('feedback-success-msg');
    const feedbackErrorMsg = document.getElementById('feedback-error-msg');
    
    if (btnOpenFeedback && feedbackModal) {
        btnOpenFeedback.addEventListener('click', () => {
            feedbackModal.classList.remove('hidden');
            if (feedbackSuccessMsg) feedbackSuccessMsg.classList.add('hidden');
            if (feedbackErrorMsg) feedbackErrorMsg.classList.add('hidden');
            feedbackForm.reset();
        });
    }
    
    if (btnCloseFeedback && feedbackModal) {
        btnCloseFeedback.addEventListener('click', () => {
            feedbackModal.classList.add('hidden');
        });
    }
    
    if (feedbackForm) {
        feedbackForm.addEventListener('submit', (e) => {
            e.preventDefault();
            
            const submitBtn = feedbackForm.querySelector('button[type="submit"]');
            const originalHTML = submitBtn.innerHTML;
            submitBtn.disabled = true;
            submitBtn.innerHTML = 'Submitting...';
            
            if (feedbackSuccessMsg) feedbackSuccessMsg.classList.add('hidden');
            if (feedbackErrorMsg) feedbackErrorMsg.classList.add('hidden');
            
            let totalProcessed = 0;
            duplicateGroups.forEach(g => {
                totalProcessed += g.photos.length;
            });
            
            const feedbackData = {
                name: document.getElementById('feedback-name').value.trim(),
                company: document.getElementById('feedback-company').value.trim(),
                event_type: document.getElementById('feedback-event-type').value,
                satisfaction_score: parseInt(document.getElementById('feedback-rating').value),
                comments: document.getElementById('feedback-comments').value.trim(),
                images_processed: totalProcessed
            };
            
            window.pywebview.api.submit_feedback(feedbackData)
                .then(res => {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = originalHTML;
                    if (res.success) {
                        if (feedbackSuccessMsg) feedbackSuccessMsg.classList.remove('hidden');
                        setTimeout(() => {
                            feedbackModal.classList.add('hidden');
                        }, 2000);
                    } else {
                        if (feedbackErrorMsg) {
                            feedbackErrorMsg.textContent = res.error || 'Failed to submit feedback.';
                            feedbackErrorMsg.classList.remove('hidden');
                        }
                    }
                })
                .catch(err => {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = originalHTML;
                    if (feedbackErrorMsg) {
                        feedbackErrorMsg.textContent = 'Error: ' + err.message;
                        feedbackErrorMsg.classList.remove('hidden');
                    }
                });
        });
    }
}

function setupFeatureRequestUI() {
    const btnOpenFeature = document.getElementById('btn-open-feature');
    const btnCloseFeature = document.getElementById('btn-close-feature-modal');
    const featureModal = document.getElementById('feature-request-modal');
    const featureForm = document.getElementById('feature-request-form');
    const featureSuccessMsg = document.getElementById('feature-success-msg');
    const featureErrorMsg = document.getElementById('feature-error-msg');
    
    if (btnOpenFeature && featureModal) {
        btnOpenFeature.addEventListener('click', () => {
            featureModal.classList.remove('hidden');
            if (featureSuccessMsg) featureSuccessMsg.classList.add('hidden');
            if (featureErrorMsg) featureErrorMsg.classList.add('hidden');
            if (featureForm) featureForm.reset();
        });
    }
    
    if (btnCloseFeature && featureModal) {
        btnCloseFeature.addEventListener('click', () => {
            featureModal.classList.add('hidden');
        });
    }
    
    if (featureForm) {
        featureForm.addEventListener('submit', (e) => {
            e.preventDefault();
            
            const submitBtn = featureForm.querySelector('button[type="submit"]');
            const originalHTML = submitBtn ? submitBtn.innerHTML : 'Submit';
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = 'Submitting...';
            }
            
            if (featureSuccessMsg) featureSuccessMsg.classList.add('hidden');
            if (featureErrorMsg) featureErrorMsg.classList.add('hidden');
            
            const featureData = {
                feature: document.getElementById('feature-title').value.trim(),
                priority: document.getElementById('feature-priority').value,
                workflow_impact: document.getElementById('feature-impact').value.trim()
            };
            
            if (window.pywebview && window.pywebview.api) {
                window.pywebview.api.submit_feature_request(featureData)
                    .then(res => {
                        if (submitBtn) {
                            submitBtn.disabled = false;
                            submitBtn.innerHTML = originalHTML;
                        }
                        if (res.success) {
                            if (featureSuccessMsg) featureSuccessMsg.classList.remove('hidden');
                            setTimeout(() => {
                                featureModal.classList.add('hidden');
                            }, 2000);
                        } else {
                            if (featureErrorMsg) {
                                featureErrorMsg.textContent = res.error || 'Failed to submit feature request.';
                                featureErrorMsg.classList.remove('hidden');
                            }
                        }
                    })
                    .catch(err => {
                        if (submitBtn) {
                            submitBtn.disabled = false;
                            submitBtn.innerHTML = originalHTML;
                        }
                        if (featureErrorMsg) {
                            featureErrorMsg.textContent = 'Error: ' + err.message;
                            featureErrorMsg.classList.remove('hidden');
                        }
                    });
            }
        });
    }
}

function checkAndPromptCrashReport() {
    if (!window.pywebview || !window.pywebview.api) return;
    
    window.pywebview.api.check_crash_report()
        .then(res => {
            if (res && res.exists) {
                const crashModal = document.getElementById('crash-modal');
                const crashMsg = document.getElementById('crash-modal-msg');
                if (crashMsg && res.error) {
                    crashMsg.textContent = `QuantileCull encountered a critical error: "${res.error}". Would you like to share the stack trace to help diagnose the issue?`;
                }
                if (crashModal) {
                    crashModal.classList.remove('hidden');
                }
                
                const btnIgnore = document.getElementById('btn-crash-ignore');
                const btnUpload = document.getElementById('btn-crash-upload');
                
                const handleCrashAction = (consent) => {
                    if (btnIgnore) btnIgnore.disabled = true;
                    if (btnUpload) btnUpload.disabled = true;
                    
                    window.pywebview.api.upload_crash_report(consent)
                        .then(uploadRes => {
                            if (crashModal) crashModal.classList.add('hidden');
                            if (btnIgnore) btnIgnore.disabled = false;
                            if (btnUpload) btnUpload.disabled = false;
                            if (uploadRes.success) {
                                console.log(uploadRes.message);
                            } else {
                                console.error(uploadRes.error);
                            }
                        })
                        .catch(err => {
                            if (crashModal) crashModal.classList.add('hidden');
                            if (btnIgnore) btnIgnore.disabled = false;
                            if (btnUpload) btnUpload.disabled = false;
                            console.error('Crash report upload error:', err);
                        });
                };
                
                if (btnIgnore) {
                    btnIgnore.onclick = () => handleCrashAction(false);
                }
                if (btnUpload) {
                    btnUpload.onclick = () => handleCrashAction(true);
                }
            }
        })
        .catch(err => console.error('Failed to check crash report:', err));
}

function checkForUpdates() {
    if (!window.pywebview || !window.pywebview.api) return;
    
    window.pywebview.api.check_for_updates()
        .then(res => {
            if (res && res.update_available) {
                const updateBadge = document.getElementById('update-badge');
                if (updateBadge) {
                    updateBadge.classList.remove('hidden');
                    updateBadge.title = `Version ${res.version} is available. Click to download!`;
                    updateBadge.onclick = () => {
                        window.pywebview.api.open_external_link(res.url)
                            .catch(err => console.error('Failed to open update link:', err));
                    };
                }
            }
        })
        .catch(err => console.error('Failed to check for updates:', err));
}
