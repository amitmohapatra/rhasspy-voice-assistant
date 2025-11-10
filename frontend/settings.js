/**
 * Settings Panel - Modern, Compact, Professional
 * Matching Takeda-inspired assistant design language
 */
class SettingsPanel {
    static instance = null;
    
    constructor() {
        if (SettingsPanel.instance) {
            return SettingsPanel.instance;
        }
        
        this.assistantManager = AssistantManager.getInstance();
        this.isOpen = false;
        this.currentTab = 'assistants';
        this.selectedVectorStore = null;
        this.logPrefix = '[SettingsPanel]';
        
        SettingsPanel.instance = this;
    }
    
    static getInstance() {
        if (!SettingsPanel.instance) {
            SettingsPanel.instance = new SettingsPanel();
        }
        return SettingsPanel.instance;
    }
    
    escapeHtml(value) {
        if (value === undefined || value === null) {
            return '';
        }
        return String(value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }
    
    getActionIcon(name) {
        switch (name) {
            case 'activate':
                return `
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                        <polygon points="6 4 18 12 6 20"></polygon>
                    </svg>
                `;
            case 'deactivate':
                return `
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M12 2v10"></path>
                        <path d="M7.5 4.2a9 9 0 1 0 9 0"></path>
                    </svg>
                `;
            case 'edit':
                return `
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M17 3a2.828 2.828 0 1 1 4 4L7 21l-4 1 1-4L17 3z"></path>
                    </svg>
                `;
            case 'delete':
                return `
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                        <polyline points="3 6 5 6 21 6"></polyline>
                        <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"></path>
                        <path d="M10 11v6"></path>
                        <path d="M14 11v6"></path>
                        <path d="M9 6V4a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2"></path>
                    </svg>
                `;
            case 'files':
                return `
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M3 7a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"></path>
                    </svg>
                `;
            case 'rename':
                return `
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M15 12H9"></path>
                        <path d="M12 15V9"></path>
                        <rect x="4" y="4" width="16" height="16" rx="2"></rect>
                    </svg>
                `;
            default:
                return `
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                        <circle cx="12" cy="12" r="3"></circle>
                    </svg>
                `;
        }
    }
    
    renderActionButton(iconName, label, handler, variant = 'primary') {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = `fab-action ${variant}`;
        button.title = label;
        button.setAttribute('aria-label', label);
        
        const iconWrapper = document.createElement('span');
        iconWrapper.className = 'fab-icon';
        iconWrapper.innerHTML = this.getActionIcon(iconName);
        
        const labelSpan = document.createElement('span');
        labelSpan.className = 'fab-label';
        labelSpan.textContent = label;
        
        button.append(iconWrapper, labelSpan);
        button.addEventListener('click', (event) => {
            event.preventDefault();
            event.stopPropagation();
            handler(event);
        });
        
        return button;
    }
    
    async init() {
        try {
            await this.createSettingsPanel();
            this.createModals();
            this.attachEventListeners();
        } catch (error) {
            console.error('Error initializing Settings Panel:', error);
        }
    }
    
    createModals() {
        // Simple confirmation modal
        const confirmModalHTML = `
            <div id="confirm-modal" class="modal-overlay" style="display: none;">
                <div class="modal-box modal-sm">
                    <div class="modal-content">
                        <h3 id="confirm-title"></h3>
                        <p id="confirm-message"></p>
                    </div>
                    <div class="modal-actions">
                        <button class="btn btn-ghost" onclick="settingsPanel.hideConfirmModal()">Cancel</button>
                        <button class="btn btn-primary" id="confirm-yes">Confirm</button>
                    </div>
                </div>
            </div>
        `;
        
        // Input modal
        const inputModalHTML = `
            <div id="input-modal" class="modal-overlay" style="display: none;">
                <div class="modal-box modal-sm">
                    <div class="modal-content">
                        <h3 id="input-title"></h3>
                        <input type="text" id="input-field" class="input" placeholder="Enter value..." />
                    </div>
                    <div class="modal-actions">
                        <button class="btn btn-ghost" onclick="settingsPanel.hideInputModal()">Cancel</button>
                        <button class="btn btn-primary" id="input-ok">OK</button>
                    </div>
                </div>
            </div>
        `;
        
        // Assistant form modal
        const assistantModalHTML = `
            <div id="assistant-modal" class="modal-overlay" style="display: none;">
                <div class="modal-box modal-md">
                    <div class="modal-header">
                        <h3 id="assistant-modal-title">Create Assistant</h3>
                        <button class="btn-icon-circle ghost medium close-btn" onclick="settingsPanel.hideAssistantModal()" aria-label="Close">
                            <svg class="icon-close" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <line x1="18" y1="6" x2="6" y2="18"></line>
                                <line x1="6" y1="6" x2="18" y2="18"></line>
                            </svg>
                        </button>
                    </div>
                    <div class="modal-content">
                        <input type="hidden" id="modal-assistant-id" />
                        
                        <div class="form-field">
                            <label for="modal-assistant-name">Name</label>
                            <input type="text" id="modal-assistant-name" class="input" placeholder="My Assistant" />
                        </div>
                        
                        <div class="form-field">
                            <label for="modal-assistant-instructions">Instructions</label>
                            <textarea id="modal-assistant-instructions" class="input" rows="3" placeholder="You are a helpful assistant..."></textarea>
                        </div>
                        
                        <div class="form-field">
                            <label for="modal-assistant-model">Model</label>
                            <select id="modal-assistant-model" class="input">
                                <option value="gpt-4.1">gpt-4.1</option>
                                <option value="gpt-4.1-mini">gpt-4.1-mini</option>
                                <option value="gpt-4o">gpt-4o</option>
                                <option value="gpt-4o-mini">gpt-4o-mini</option>
                                <option value="o1">o1</option>
                                <option value="o3-mini">o3-mini</option>
                            </select>
                        </div>
                        
                        <div class="form-field">
                            <label>Knowledge Bases</label>
                            <div id="modal-vector-stores" class="checkbox-group" role="group" aria-label="Knowledge Bases"></div>
                        </div>
                    </div>
                    <div class="modal-actions">
                        <button class="btn btn-ghost" onclick="settingsPanel.hideAssistantModal()">Cancel</button>
                        <button class="btn btn-primary" onclick="settingsPanel.saveAssistantFromModal()">Save</button>
                    </div>
                </div>
            </div>
        `;
        
        // Toast notification
        const toastHTML = `
            <div id="toast" class="toast" style="display: none;">
                <span id="toast-message"></span>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', confirmModalHTML);
        document.body.insertAdjacentHTML('beforeend', inputModalHTML);
        document.body.insertAdjacentHTML('beforeend', assistantModalHTML);
        document.body.insertAdjacentHTML('beforeend', toastHTML);
    }
    
    // Modal helpers
    async confirm(title, message) {
        return new Promise((resolve) => {
            document.getElementById('confirm-title').textContent = title;
            document.getElementById('confirm-message').textContent = message;
            document.getElementById('confirm-modal').style.display = 'flex';
            
            const yesBtn = document.getElementById('confirm-yes');
            const handler = () => {
                this.hideConfirmModal();
                yesBtn.removeEventListener('click', handler);
                resolve(true);
            };
            yesBtn.addEventListener('click', handler);
            
            this.confirmResolve = () => {
                yesBtn.removeEventListener('click', handler);
                resolve(false);
            };
        });
    }
    
    hideConfirmModal() {
        document.getElementById('confirm-modal').style.display = 'none';
        if (this.confirmResolve) {
            this.confirmResolve();
            this.confirmResolve = null;
        }
    }
    
    async prompt(title, defaultValue = '') {
        return new Promise((resolve) => {
            document.getElementById('input-title').textContent = title;
            document.getElementById('input-field').value = defaultValue;
            document.getElementById('input-modal').style.display = 'flex';
            
            const okBtn = document.getElementById('input-ok');
            const handler = () => {
                const value = document.getElementById('input-field').value;
                this.hideInputModal();
                okBtn.removeEventListener('click', handler);
                resolve(value);
            };
            okBtn.addEventListener('click', handler);
            
            this.inputResolve = () => {
                okBtn.removeEventListener('click', handler);
                resolve('');
            };
            
            setTimeout(() => document.getElementById('input-field').focus(), 100);
        });
    }
    
    hideInputModal() {
        document.getElementById('input-modal').style.display = 'none';
        if (this.inputResolve) {
            this.inputResolve();
            this.inputResolve = null;
        }
    }
    
    showToast(message, type = 'success') {
        const toast = document.getElementById('toast');
        toast.className = `toast ${type}`;
        document.getElementById('toast-message').textContent = message;
        toast.style.display = 'block';
        setTimeout(() => {
            toast.style.display = 'none';
        }, 3000);
    }
    
    async showAssistantModal(assistant = null) {
        const modal = document.getElementById('assistant-modal');
        const title = document.getElementById('assistant-modal-title');
        
        if (assistant) {
            title.textContent = 'Edit Assistant';
            document.getElementById('modal-assistant-id').value = assistant.id;
            document.getElementById('modal-assistant-name').value = assistant.name || '';
            document.getElementById('modal-assistant-instructions').value = assistant.instructions || '';
            document.getElementById('modal-assistant-model').value = assistant.model || 'gpt-4o-mini';
        } else {
            title.textContent = 'Create Assistant';
            document.getElementById('modal-assistant-id').value = '';
            document.getElementById('modal-assistant-name').value = '';
            document.getElementById('modal-assistant-instructions').value = 'You are Rhasspy, a helpful AI assistant.';
            document.getElementById('modal-assistant-model').value = 'gpt-4o-mini';
        }
        
        await this.loadVectorStoresForModal(assistant);
        modal.style.display = 'flex';
        setTimeout(() => document.getElementById('modal-assistant-name').focus(), 100);
    }
    
    hideAssistantModal() {
        document.getElementById('assistant-modal').style.display = 'none';
    }
    
    async loadVectorStoresForModal(assistant = null) {
        const container = document.getElementById('modal-vector-stores');
        container.innerHTML = '<div class="text-muted">Loading...</div>';
        
        try {
            const vectorStores = await this.assistantManager.listVectorStores();
            const attachedIds = assistant?.tool_resources?.file_search?.vector_store_ids || [];
            
            if (vectorStores.length === 0) {
                container.innerHTML = '<div class="text-muted">No knowledge bases available</div>';
                return;
            }
            
            container.innerHTML = vectorStores.map(vs => {
                const fileCount = vs.file_counts?.total || vs.file_counts?.completed || 0;
                return `
                    <label class="checkbox-label">
                        <input type="checkbox" value="${vs.id}" ${attachedIds.includes(vs.id) ? 'checked' : ''} />
                        <span>${vs.name || 'Unnamed'} (${fileCount} files)</span>
                    </label>
                `;
            }).join('');
        } catch (error) {
            container.innerHTML = '<div class="text-error">Failed to load</div>';
        }
    }
    
    async saveAssistantFromModal() {
        const id = document.getElementById('modal-assistant-id').value;
        const name = document.getElementById('modal-assistant-name').value.trim();
        const instructions = document.getElementById('modal-assistant-instructions').value.trim();
        const model = document.getElementById('modal-assistant-model').value;
        
        const vectorStoreIds = Array.from(
            document.querySelectorAll('#modal-vector-stores input[type="checkbox"]:checked')
        ).map(cb => cb.value);
        
        if (!name) {
            this.showToast('Please enter a name', 'error');
            return;
        }
        
        try {
            const payload = {
                name,
                instructions,
                model,
                vector_store_ids: vectorStoreIds
            };

            if (id) {
                await this.assistantManager.updateAssistant(id, payload);
                this.showToast('Assistant updated');
            } else {
                await this.assistantManager.createAssistant(name, instructions, model, vectorStoreIds);
                this.showToast('Assistant created');
            }
            
            this.hideAssistantModal();
            await this.loadAssistants();
        } catch (error) {
            this.showToast('Failed: ' + error.message, 'error');
        }
    }
    
    async createSettingsPanel() {
        const panelHTML = `
            <div id="settings-panel" class="settings-overlay" style="display: none;">
                <div class="settings-sidebar">
                    <div class="settings-header">
                        <div class="settings-copy">
                            <h2 class="settings-title">Assistant Workspace</h2>
                            <p class="settings-subtitle">Curate assistants, knowledge bases, and files</p>
                        </div>
                        <button class="btn-icon-circle ghost medium close-btn" id="close-settings" aria-label="Close settings">
                            <svg class="icon-close" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <line x1="18" y1="6" x2="6" y2="18"></line>
                                <line x1="6" y1="6" x2="18" y2="18"></line>
                            </svg>
                        </button>
                    </div>
                    
                    <div class="tabs">
                        <button class="tab active" data-tab="assistants">
                            <span>🤖</span> Assistants
                        </button>
                        <button class="tab" data-tab="vectorstores">
                            <span>📚</span> Knowledge
                        </button>
                        <button class="tab" data-tab="files">
                            <span>📄</span> Files
                        </button>
                    </div>
                    
                    <div class="tab-content">
                        <!-- Assistants Tab -->
                        <div id="assistants-tab" class="tab-pane active">
                            <div class="pane-header">
                                <p class="pane-desc">Manage AI assistants</p>
                                <div class="btn-group">
                                    <button class="btn btn-primary btn-sm" id="create-assistant-btn">+ New</button>
                                    <button class="btn-icon-circle ghost medium" id="refresh-assistants" title="Refresh" aria-label="Refresh assistants">
                                        <svg class="icon-refresh" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                            <polyline points="23 4 23 10 17 10"></polyline>
                                            <polyline points="1 20 1 14 7 14"></polyline>
                                            <path d="M3.51 9a9 9 0 0 1 14.13-3.36L23 10"></path>
                                            <path d="M20.49 15a9 9 0 0 1-14.13 3.36L1 14"></path>
                                        </svg>
                                    </button>
                                </div>
                            </div>
                            <div id="assistants-list" class="items-list"></div>
                        </div>
                        
                        <!-- Vector Stores Tab -->
                        <div id="vectorstores-tab" class="tab-pane">
                            <div class="pane-header">
                                <p class="pane-desc">Manage Knowledge Base</p>
                                <div class="btn-group">
                                    <button class="btn btn-primary btn-sm" id="create-vectorstore-btn">+ New</button>
                                    <button class="btn-icon-circle ghost medium" id="refresh-vectorstores" title="Refresh" aria-label="Refresh vector stores">
                                        <svg class="icon-refresh" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                            <polyline points="23 4 23 10 17 10"></polyline>
                                            <polyline points="1 20 1 14 7 14"></polyline>
                                            <path d="M3.51 9a9 9 0 0 1 14.13-3.36L23 10"></path>
                                            <path d="M20.49 15a9 9 0 0 1-14.13 3.36L1 14"></path>
                                        </svg>
                                    </button>
                                </div>
                            </div>
                            <div id="vectorstores-list" class="items-list"></div>
                        </div>
                        
                        <!-- Files Tab -->
                        <div id="files-tab" class="tab-pane">
                            <div class="pane-header">
                                <p class="pane-desc">Manage files in knowledge bases</p>
                            </div>
                            <div class="files-controls">
                                <select id="files-vectorstore-select" class="select-sm">
                                    <option value="">Select...</option>
                                </select>
                                <div class="files-actions">
                                    <button class="btn btn-primary btn-sm" id="upload-file-btn" disabled>Upload</button>
                                    <button class="btn-icon-circle ghost medium" id="refresh-files" disabled title="Refresh" aria-label="Refresh files">
                                        <svg class="icon-refresh" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                            <polyline points="23 4 23 10 17 10"></polyline>
                                            <polyline points="1 20 1 14 7 14"></polyline>
                                            <path d="M3.51 9a9 9 0 0 1 14.13-3.36L23 10"></path>
                                            <path d="M20.49 15a9 9 0 0 1-14.13 3.36L1 14"></path>
                                        </svg>
                                    </button>
                                </div>
                            </div>
                            <input type="file" id="file-input" style="display: none;" accept=".pdf,.txt,.md,.csv,.jsonl,.html" />
                            <div id="files-list" class="items-list"></div>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', panelHTML);
        await this.injectStyles();
    }
    
    async injectStyles() {
        const styles = `
            <style>
                /* Settings Panel - Modern & Compact */
                .settings-overlay {
                    position: fixed;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    background: rgba(0, 0, 0, 0.4);
                    z-index: 10000;
                    animation: fadeIn 0.2s;
                }
                
                @keyframes fadeIn {
                    from { opacity: 0; }
                    to { opacity: 1; }
                }
                
                .settings-sidebar {
                    position: absolute;
                    right: 0;
                    top: 0;
                    width: 420px;
                    height: 100%;
                    background: #ffffff;
                    box-shadow: -2px 0 16px rgba(0, 0, 0, 0.1);
                    display: flex;
                    flex-direction: column;
                    animation: slideIn 0.3s ease;
                }
                
                @keyframes slideIn {
                    from { transform: translateX(100%); }
                    to { transform: translateX(0); }
                }
                
                .settings-header {
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    padding: 20px 24px;
                    border-bottom: 1px solid #e5e7eb;
                    gap: 16px;
                }
                
                .settings-copy {
                    display: flex;
                    flex-direction: column;
                    gap: 4px;
                    min-width: 0;
                }
                
                .settings-title {
                    margin: 0;
                    font-size: 20px;
                    font-weight: 600;
                    color: #1f2937;
                }
                
                .settings-subtitle {
                    margin: 0;
                    font-size: 12px;
                    color: #6b7280;
                    letter-spacing: 0.3px;
                }
                
                .btn-icon-circle {
                    width: 42px;
                    height: 42px;
                    border-radius: 999px;
                    border: none;
                    background: rgba(15, 23, 42, 0.06);
                    display: inline-flex;
                    align-items: center;
                    justify-content: center;
                    cursor: pointer;
                    transition: all 0.2s ease;
                    color: #111827;
                }
                
                .btn-icon-circle.ghost {
                    background: transparent;
                    border: 1px solid rgba(15, 23, 42, 0.1);
                }
                
                .btn-icon-circle.small,
                .btn-icon-circle.medium {
                    width: 40px;
                    height: 40px;
                }
                
                .btn-icon-circle svg {
                    width: 18px;
                    height: 18px;
                    pointer-events: none;
                    stroke: var(--primary-dark);
                }
                
                .btn-icon-circle.medium svg {
                    width: 20px;
                    height: 20px;
                }
                
                .btn-icon-circle.ghost:hover,
                .btn-icon-circle:hover {
                    background: rgba(212, 85, 122, 0.1);
                    border-color: rgba(212, 85, 122, 0.3);
                    transform: translateY(-1px);
                }
                
                .settings-header h2 {
                    font-size: 20px;
                    font-weight: 700;
                    margin: 0;
                    background: linear-gradient(135deg, var(--primary-dark) 0%, var(--primary-color) 100%);
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                    background-clip: text;
                }
                
                .tabs {
                    display: flex;
                    padding: 12px 16px 0;
                    gap: 4px;
                    border-bottom: 1px solid #e5e7eb;
                    background: #f9fafb;
                }
                
                .tab {
                    flex: 1;
                    padding: 10px 12px;
                    border: none;
                    background: transparent;
                    color: #6b7280;
                    font-size: 13px;
                    font-weight: 500;
                    cursor: pointer;
                    border-radius: 6px 6px 0 0;
                    transition: all 0.2s;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    gap: 6px;
                    border-bottom: 2px solid transparent;
                }
                
                .tab:hover {
                    background: rgba(212, 85, 122, 0.12);
                    color: var(--primary-color);
                }
                
                .tab.active {
                    background: #ffffff;
                    color: var(--primary-dark);
                    font-weight: 600;
                    border-bottom-color: var(--primary-color);
                }
                
                .tab span {
                    font-size: 16px;
                }
                
                .tab-content {
                    flex: 1;
                    overflow-y: auto;
                    background: #f9fafb;
                }
                
                .tab-content::-webkit-scrollbar {
                    width: 6px;
                }
                
                .tab-content::-webkit-scrollbar-thumb {
                    background: #d1d5db;
                    border-radius: 3px;
                }
                
                .tab-pane {
                    display: none;
                    padding: 16px;
                }
                
                .tab-pane.active {
                    display: block;
                }
                
                .pane-header {
                    margin-bottom: 16px;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    gap: 12px;
                }
                
                .pane-desc {
                    font-size: 13px;
                    color: #6b7280;
                    margin: 0;
                    flex: 1 1 auto;
                    font-weight: 500;
                    letter-spacing: 0.2px;
                }
                
                .pane-header .btn,
                .pane-header .btn-icon-circle,
                .pane-header .btn-icon-circle.medium,
                .pane-header .btn-icon-circle.small {
                    min-height: 34px;
                    height: 34px;
                    border-radius: 999px;
                    background: rgba(230, 0, 38, 0.12);
                    color: var(--primary-dark);
                    font-weight: 600;
                    font-size: 12px;
                    letter-spacing: 0.3px;
                    border: 1px solid rgba(230, 0, 38, 0.16);
                    box-shadow: 0 6px 16px rgba(230, 0, 38, 0.18);
                }
                
                .pane-header .btn {
                    padding: 6px 14px;
                }
                
                .pane-header .btn-icon-circle,
                .pane-header .btn-icon-circle.medium,
                .pane-header .btn-icon-circle.small {
                    width: 34px;
                    padding: 0;
                }
                
                .pane-header .btn:hover,
                .pane-header .btn:focus-visible,
                .pane-header .btn-icon-circle:hover,
                .pane-header .btn-icon-circle:focus-visible {
                    outline: none;
                    background: linear-gradient(135deg, #f84031 0%, #b1120d 100%);
                    color: #ffffff;
                    border-color: transparent;
                    box-shadow: 0 12px 28px rgba(189, 18, 10, 0.32);
                }
                
                .select-sm {
                    flex: 1 1 230px;
                    min-width: 220px;
                    max-width: 100%;
                    padding: 8px 16px;
                    border: 1.5px solid rgba(189, 18, 10, 0.2);
                    border-radius: 999px;
                    font-size: 13px;
                    background: rgba(189, 18, 10, 0.04);
                    color: #374151;
                    cursor: pointer;
                    transition: border-color 0.2s ease, box-shadow 0.2s ease, background 0.2s ease;
                }
                
                .select-sm:hover {
                    border-color: rgba(189, 18, 10, 0.4);
                    background: rgba(189, 18, 10, 0.08);
                }
                
                .select-sm:focus {
                    outline: none;
                    border-color: var(--primary-dark);
                    background: rgba(189, 18, 10, 0.12);
                    box-shadow: 0 0 0 3px rgba(189, 18, 10, 0.15);
                }
                
                .items-list {
                    display: flex;
                    flex-direction: column;
                    gap: 8px;
                }
                
                .files-controls {
                    display: flex;
                    flex-direction: row;
                    gap: 12px;
                    margin-bottom: 16px;
                    align-items: center;
                    flex-wrap: wrap;
                }
                
                .files-actions {
                    display: flex;
                    gap: 10px;
                    align-items: center;
                    flex: 0 0 auto;
                }
                
                .files-actions .btn {
                    padding: 6px 14px;
                    min-height: 34px;
                    border-radius: 999px;
                    background: rgba(230, 0, 38, 0.12);
                    color: var(--primary-dark);
                    font-weight: 600;
                    font-size: 12px;
                    letter-spacing: 0.3px;
                    border: 1px solid rgba(230, 0, 38, 0.16);
                    box-shadow: 0 6px 16px rgba(230, 0, 38, 0.18);
                    transition: all 0.2s ease;
                }
                
                .files-actions .btn:hover,
                .files-actions .btn:focus-visible {
                    outline: none;
                    background: linear-gradient(135deg, #f84031 0%, #b1120d 100%);
                    color: #ffffff;
                    border-color: transparent;
                    box-shadow: 0 12px 28px rgba(189, 18, 10, 0.32);
                }
                
                .files-actions .btn-icon-circle {
                    width: 34px;
                    height: 34px;
                    padding: 0;
                    border-radius: 999px;
                    background: rgba(230, 0, 38, 0.12);
                    color: var(--primary-dark);
                    border: 1px solid rgba(230, 0, 38, 0.16);
                    box-shadow: 0 6px 16px rgba(230, 0, 38, 0.18);
                    transition: all 0.2s ease;
                }
                
                .files-actions .btn-icon-circle:hover,
                .files-actions .btn-icon-circle:focus-visible {
                    outline: none;
                    background: linear-gradient(135deg, #f84031 0%, #b1120d 100%);
                    color: #ffffff;
                    border-color: transparent;
                    box-shadow: 0 12px 28px rgba(189, 18, 10, 0.32);
                }
                
                .card-main {
                    display: flex;
                    flex-direction: column;
                    gap: 6px;
                }
                
                .card-header {
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    gap: 8px;
                    min-width: 0;
                }
                
                .card-title {
                    font-size: 12.5px;
                    font-weight: 600;
                    color: #1f2937;
                    display: flex;
                    align-items: center;
                    gap: 6px;
                    min-width: 0;
                }
                
                .item-name {
                    display: inline-block;
                    min-width: 0;
                    max-width: 100%;
                    overflow: hidden;
                    text-overflow: ellipsis;
                    white-space: nowrap;
                }
                
                .item-subtitle {
                    font-size: 11px;
                    color: #6b7280;
                    letter-spacing: 0.2px;
                }
                
                .card-badges {
                    display: flex;
                    flex-wrap: wrap;
                    gap: 4px;
                    justify-content: flex-end;
                }
                
                .card-badge {
                    display: inline-flex;
                    align-items: center;
                    gap: 4px;
                    padding: 4px 8px;
                    border-radius: 999px;
                    background: rgba(189, 18, 10, 0.12);
                    color: var(--primary-dark);
                    font-weight: 650;
                    font-size: 11px;
                    letter-spacing: 0.45px;
                    text-transform: uppercase;
                }
                
                .card-badge.neutral {
                    background: rgba(15, 23, 42, 0.08);
                    color: #1f2937;
                }
                
                .card-badge.success {
                    background: rgba(13, 148, 136, 0.18);
                    color: #0f766e;
                }
                
                .card-badge.accent {
                    background: rgba(189, 18, 10, 0.18);
                    color: var(--primary-dark);
                }
                
                .meta-row {
                    display: flex;
                    flex-wrap: wrap;
                    gap: 6px;
                    align-items: center;
                }
                
                .pill {
                    display: inline-flex;
                    align-items: center;
                    gap: 4px;
                    padding: 4px 10px;
                    border-radius: 999px;
                    background: rgba(15, 23, 42, 0.06);
                    color: #1f2937;
                    font-weight: 500;
                    font-size: 11px;
                }
                
                .pill.accent {
                    background: rgba(189, 18, 10, 0.12);
                    color: var(--primary-dark);
                }
                
                .pill.muted {
                    background: rgba(15, 23, 42, 0.04);
                    color: #6b7280;
                }
                
                .card-actions {
                    display: flex;
                    justify-content: flex-end;
                    gap: 6px;
                    flex-wrap: wrap;
                }
                
                .fab-action {
                    position: relative;
                    display: inline-flex;
                    align-items: center;
                    justify-content: center;
                    gap: 6px;
                    border: none;
                    border-radius: 999px;
                    min-width: 28px;
                    height: 28px;
                    padding: 0;
                    background: linear-gradient(135deg, #f84031 0%, #b1120d 100%);
                    color: #ffffff;
                    font-weight: 600;
                    cursor: pointer;
                    box-shadow: 0 8px 22px rgba(189, 18, 10, 0.28);
                    overflow: hidden;
                    transition: padding 0.2s ease, box-shadow 0.2s ease;
                }
                
                .fab-action .fab-icon svg {
                    width: 14px;
                    height: 14px;
                }
                
                .fab-label {
                    opacity: 0;
                    white-space: nowrap;
                    font-size: 11px;
                    transform: translateX(8px);
                    max-width: 0;
                    overflow: hidden;
                    transition: opacity 0.2s ease, transform 0.2s ease, max-width 0.2s ease;
                }
                
                .fab-action:hover,
                .fab-action:focus-visible {
                    padding: 0 8px 0 6px;
                    outline: none;
                    box-shadow: 0 10px 24px rgba(189, 18, 10, 0.32);
                }
                
                .fab-action:hover .fab-label,
                .fab-action:focus-visible .fab-label {
                    opacity: 1;
                    transform: translateX(0);
                    max-width: 80px;
                }
                
                .fab-action.neutral {
                    background: rgba(30, 41, 59, 0.92);
                    box-shadow: 0 8px 18px rgba(30, 41, 59, 0.28);
                }
                
                .fab-action.danger {
                    background: linear-gradient(135deg, #ef4444 0%, #991b1b 100%);
                }
                
                .fab-action.outline {
                    background: rgba(230, 0, 38, 0.1);
                    color: var(--primary-dark);
                    box-shadow: none;
                }
                
                .fab-action.outline .fab-icon svg {
                    color: var(--primary-dark);
                }
                
                /* Fine-tuning for compact badges/buttons */
                .item-card {
                    font-size: 12px;
                }
                
                .card-title {
                    font-size: 12px;
                }
                
                .card-badges {
                    gap: 4px;
                }
                
                .card-badge {
                    padding: 3px 8px;
                    font-size: 10px;
                }
                
                .pill {
                    font-size: 10px;
                }
                
                .card-actions {
                    gap: 4px;
                }
                
                .card-actions-inline {
                    display: flex;
                    align-items: center;
                    gap: 4px;
                    margin-top: -2px;
                }
                
                .card-footer {
                    display: flex;
                    justify-content: flex-end;
                    margin-top: 6px;
                }
                
                .card-badge.muted {
                    background: rgba(148, 163, 184, 0.18);
                    color: #475569;
                }
                
                .fab-action {
                    min-width: 22px;
                    height: 22px;
                    padding: 0;
                    gap: 3px;
                    align-items: center;
                    justify-content: center;
                }
                
                .fab-action .fab-icon svg {
                    width: 10px;
                    height: 10px;
                }
                
                .fab-action:hover,
                .fab-action:focus-visible {
                    padding: 0 8px 0 7px;
                }
                
                .text-muted {
                    text-align: center;
                    padding: 32px;
                    color: #9ca3af;
                    font-size: 13px;
                }
                
                .text-error {
                    text-align: center;
                    padding: 32px;
                    color: #ef4444;
                    font-size: 13px;
                }
                
                /* Modals */
                .modal-overlay {
                    position: fixed;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    background: rgba(0, 0, 0, 0.5);
                    z-index: 11000;
                    display: none;
                    align-items: center;
                    justify-content: center;
                    animation: fadeIn 0.2s;
                }
                
                .modal-box {
                    background: white;
                    border-radius: 12px;
                    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
                    animation: slideUp 0.3s ease;
                    overflow: hidden;
                }
                
                @keyframes slideUp {
                    from {
                        opacity: 0;
                        transform: translateY(20px);
                    }
                    to {
                        opacity: 1;
                        transform: translateY(0);
                    }
                }
                
                .modal-sm {
                    width: 90%;
                    max-width: 400px;
                }
                
                .modal-md {
                    width: 90%;
                    max-width: 500px;
                    max-height: 80vh;
                    display: flex;
                    flex-direction: column;
                }
                
                .modal-header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding: 20px 24px;
                    border-bottom: 1px solid #e5e7eb;
                }
                
                .modal-header h3 {
                    font-size: 18px;
                    font-weight: 600;
                    margin: 0;
                    color: var(--primary-dark);
                }
                
                .modal-content {
                    padding: 24px;
                    overflow-y: auto;
                }
                
                .modal-md .modal-content {
                    flex: 1;
                }
                
                .modal-content h3 {
                    font-size: 18px;
                    font-weight: 600;
                    color: #1f2937;
                    margin: 0 0 16px 0;
                }
                
                .modal-content p {
                    margin: 0 0 16px 0;
                    color: #6b7280;
                    line-height: 1.6;
                    font-size: 14px;
                }
                
                .modal-actions {
                    padding: 16px 24px;
                    border-top: 1px solid #e5e7eb;
                    display: flex;
                    justify-content: flex-end;
                    gap: 12px;
                }
                
                .form-field {
                    margin-bottom: 16px;
                }
                
                .form-field label {
                    display: block;
                    margin-bottom: 6px;
                    font-size: 13px;
                    font-weight: 500;
                    color: #374151;
                }
                
                .input {
                    width: 100%;
                    padding: 8px 12px;
                    border: 1px solid rgba(189, 18, 10, 0.2);
                    border-radius: 8px;
                    font-size: 14px;
                    transition: all 0.2s;
                    background: rgba(189, 18, 10, 0.02);
                }
                
                .input:focus {
                    outline: none;
                    border-color: var(--primary-dark);
                    box-shadow: 0 0 0 3px rgba(189, 18, 10, 0.12);
                    background: rgba(189, 18, 10, 0.06);
                }
                
                textarea.input {
                    resize: vertical;
                    font-family: inherit;
                }
                
                .checkbox-group {
                    display: flex;
                    flex-direction: column;
                    gap: 8px;
                    max-height: 160px;
                    overflow-y: auto;
                    padding: 8px;
                    background: rgba(189, 18, 10, 0.04);
                    border-radius: 8px;
                }
                
                .checkbox-label {
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    padding: 10px 12px;
                    background: white;
                    border: 1px solid rgba(189, 18, 10, 0.18);
                    border-radius: 8px;
                    cursor: pointer;
                    transition: all 0.2s;
                    font-size: 13px;
                }
                
                .checkbox-label:hover {
                    border-color: var(--primary-color);
                    box-shadow: 0 4px 12px rgba(189, 18, 10, 0.12);
                }
                
                .checkbox-label input:checked + span,
                .checkbox-label input:checked ~ span {
                    color: var(--primary-dark);
                    font-weight: 600;
                }
                
                .checkbox-label input {
                    cursor: pointer;
                }
                
                /* Toast */
                .toast {
                    position: fixed;
                    top: 20px;
                    right: 20px;
                    z-index: 12000;
                    padding: 12px 20px;
                    background: #1f2937;
                    color: white;
                    border-radius: 8px;
                    font-size: 14px;
                    font-weight: 500;
                    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
                    animation: slideInRight 0.3s ease;
                }
                
                @keyframes slideInRight {
                    from {
                        opacity: 0;
                        transform: translateX(100%);
                    }
                    to {
                        opacity: 1;
                        transform: translateX(0);
                    }
                }
                
                .toast.error {
                    background: #ef4444;
                }
                
                .toast.success {
                    background: #10b981;
                }
            </style>
        `;
        
        document.head.insertAdjacentHTML('beforeend', styles);
    }
    
    attachEventListeners() {
        document.getElementById('close-settings').addEventListener('click', () => this.close());
        document.querySelector('.settings-overlay').addEventListener('click', (e) => {
            if (e.target === e.currentTarget) this.close();
        });
        
        document.querySelectorAll('.tab').forEach(btn => {
            btn.addEventListener('click', () => this.switchTab(btn.dataset.tab));
        });
        
        document.getElementById('create-assistant-btn').addEventListener('click', () => this.showAssistantModal());
        document.getElementById('refresh-assistants').addEventListener('click', () => this.loadAssistants());
        
        document.getElementById('create-vectorstore-btn').addEventListener('click', () => this.createVectorStore());
        document.getElementById('refresh-vectorstores').addEventListener('click', () => this.loadVectorStores());
        
        document.getElementById('files-vectorstore-select').addEventListener('change', (e) => {
            this.selectVectorStoreForFiles(e.target.value);
        });
        document.getElementById('upload-file-btn').addEventListener('click', () => document.getElementById('file-input').click());
        document.getElementById('file-input').addEventListener('change', (e) => {
            if (e.target.files[0]) this.uploadFile(e.target.files[0]);
        });
        document.getElementById('refresh-files').addEventListener('click', () => this.loadFiles());
    }
    
    async open() {
        try {
            console.groupCollapsed(`${this.logPrefix} open`);
            this.isOpen = true;
            document.getElementById('settings-panel').style.display = 'block';
            await Promise.all([
                this.loadAssistants(),
                this.loadVectorStores(),
                this.populateVectorStoreSelect()
            ]);
            console.groupEnd();
        } catch (error) {
            console.error('Error opening settings:', error);
            this.showToast('Failed to open settings', 'error');
        }
    }
    
    close() {
        this.isOpen = false;
        document.getElementById('settings-panel').style.display = 'none';
    }
    
    switchTab(tabName) {
        this.currentTab = tabName;
        
        document.querySelectorAll('.tab').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.tab === tabName);
        });
        
        document.querySelectorAll('.tab-pane').forEach(pane => {
            pane.classList.toggle('active', pane.id === `${tabName}-tab`);
        });
    }
    
    // Assistants
    async loadAssistants() {
        const container = document.getElementById('assistants-list');
        container.innerHTML = '<div class="text-muted">Loading...</div>';
        
        try {
            console.groupCollapsed(`${this.logPrefix} loadAssistants`);
            const assistants = await this.assistantManager.listAssistants();
            const currentId = this.assistantManager.getCurrentAssistant();
            
            // Get vector stores to show attachments with file counts
            const vectorStores = await this.assistantManager.listVectorStores();
            const vsMap = {};
            const vsFileCountMap = {};
            vectorStores.forEach(vs => {
                vsMap[vs.id] = vs.name || 'Unnamed';
                vsFileCountMap[vs.id] = vs.file_counts?.completed || vs.file_counts?.total || 0;
            });
            
            if (assistants.length === 0) {
                container.innerHTML = '<div class="text-muted">No assistants yet</div>';
                return;
            }
            
            const assistantDetails = await Promise.all(
                assistants.map(async (assistant) => {
                    try {
                        return await this.assistantManager.getAssistant(assistant.id);
                    } catch (error) {
                        console.warn('Failed to get assistant details', assistant.id, error);
                        return null;
                    }
                })
            );

            container.innerHTML = '';
            assistants.forEach((assistant, index) => {
                const detail = assistantDetails[index] || {};
                const attachedVS = detail?.tool_resources?.file_search?.vector_store_ids || [];
                const isActive = assistant.id === currentId;
                const card = document.createElement('div');
                card.className = `item-card compact ${isActive ? 'active' : ''}`;
                const displayName = assistant.name || 'Unnamed';
                const safeDisplayName = this.escapeHtml(displayName);
                const safeModel = this.escapeHtml(assistant.model || 'N/A');
                const knowledgeInfo = attachedVS.map(id => {
                    const name = vsMap[id] || 'Knowledge base';
                    const fileCount = vsFileCountMap[id] || 0;
                    return `${name} (${fileCount} files)`;
                });
                const totalFiles = attachedVS.reduce((sum, id) => sum + (vsFileCountMap[id] || 0), 0);
                const knowledgeLabel = knowledgeInfo.length
                    ? `KNOWLEDGE: ${knowledgeInfo.join(', ')}`
                    : '';
                const safeKnowledgeLabel = knowledgeLabel ? this.escapeHtml(knowledgeLabel) : '';
                
                const badgeSegments = [
                    `<span class="card-badge accent">${safeModel}</span>`
                ];
                if (knowledgeLabel) {
                    badgeSegments.push(`<span class="card-badge neutral">${safeKnowledgeLabel}</span>`);
                }
                if (isActive) {
                    badgeSegments.push('<span class="card-badge success">Active</span>');
                }
                
                card.innerHTML = `
                    <div class="card-main">
                        <div class="card-header">
                            <div class="card-title">
                                <span class="item-name" title="${safeDisplayName}">${safeDisplayName}</span>
                            </div>
                            <div class="card-actions-inline"></div>
                        </div>
                        <div class="card-footer">
                            <div class="card-badges">
                                ${badgeSegments.join('')}
                            </div>
                        </div>
                    </div>
                `;
                
                const actions = [];
                if (isActive) {
                    actions.push(this.renderActionButton('deactivate', 'Deactivate', () => this.deactivateAssistant(assistant.id), 'danger'));
                } else {
                    actions.push(this.renderActionButton('activate', 'Activate', () => this.useAssistant(assistant.id)));
                }
                actions.push(this.renderActionButton('edit', 'Edit', () => this.editAssistant(assistant.id), 'neutral'));
                actions.push(this.renderActionButton('delete', 'Delete', () => this.deleteAssistant(assistant.id), 'danger'));
                
                const actionsContainer = card.querySelector('.card-actions-inline');
                actions.forEach(btn => actionsContainer.appendChild(btn));
                container.appendChild(card);
            });
            console.debug(`${this.logPrefix} loadAssistants rendered`, {
                assistantCount: assistants.length,
                activeAssistantId: currentId
            });
            console.groupEnd();
        } catch (error) {
            console.error(`${this.logPrefix} loadAssistants failed`, error);
            try { console.groupEnd(); } catch (_) {}
            container.innerHTML = '<div class="text-error">Failed to load</div>';
        }
    }
    
    async editAssistant(assistantId) {
        try {
            const assistant = await this.assistantManager.getAssistant(assistantId);
            await this.showAssistantModal(assistant);
        } catch (error) {
            this.showToast('Failed to load', 'error');
        }
    }
    
    async deleteAssistant(assistantId) {
        const confirmed = await this.confirm('Delete Assistant', 'Are you sure? This cannot be undone.');
        if (!confirmed) return;
        
        try {
            await this.assistantManager.deleteAssistant(assistantId);
            this.showToast('Deleted');
            await this.loadAssistants();
        } catch (error) {
            this.showToast('Failed to delete', 'error');
        }
    }
    
    useAssistant(assistantId) {
        this.assistantManager.setCurrentAssistant(assistantId);
        this.assistantManager.setCurrentThread(null);
        this.showToast('Assistant activated');
        this.loadAssistants();
    }
    
    deactivateAssistant(assistantId) {
        const currentId = this.assistantManager.getCurrentAssistant();
        if (currentId !== assistantId) {
            this.showToast('Assistant is not active');
            return;
        }
        this.assistantManager.setCurrentAssistant(null);
        this.assistantManager.setCurrentThread(null);
        this.showToast('Assistant deactivated');
        this.loadAssistants();
    }
    
    // Vector Stores
    async loadVectorStores() {
        const container = document.getElementById('vectorstores-list');
        container.innerHTML = '<div class="text-muted">Loading...</div>';
        
        try {
            console.groupCollapsed(`${this.logPrefix} loadVectorStores`);
            const stores = await this.assistantManager.listVectorStores();
            
            if (stores.length === 0) {
                container.innerHTML = '<div class="text-muted">No knowledge bases yet</div>';
                console.debug(`${this.logPrefix} loadVectorStores -> empty`);
                console.groupEnd();
                return;
            }
            
            container.innerHTML = '';
            stores.forEach(vs => {
                const fileCount = vs.file_counts?.total || vs.file_counts?.completed || 0;
                const name = vs.name || 'Unnamed';
                const safeName = this.escapeHtml(name);
                const safeStatus = this.escapeHtml(vs.status || 'pending');
                
                const card = document.createElement('div');
                card.className = 'item-card compact';
                card.innerHTML = `
                    <div class="card-main">
                        <div class="card-header">
                            <div class="card-title">
                                <span class="item-name" title="${safeName}">${safeName}</span>
                            </div>
                            <div class="card-actions-inline"></div>
                        </div>
                        <div class="card-footer">
                            <div class="card-badges">
                                <span class="card-badge neutral">${safeStatus}</span>
                                <span class="card-badge accent">Files: ${fileCount}</span>
                            </div>
                        </div>
                    </div>
                `;
                
                const actions = [
                    this.renderActionButton('files', 'Open files', () => this.viewFiles(vs.id)),
                    this.renderActionButton('rename', 'Rename', () => this.renameVectorStore(vs.id, name), 'neutral'),
                    this.renderActionButton('delete', 'Delete', () => this.deleteVectorStore(vs.id), 'danger')
                ];
                
                const actionsContainer = card.querySelector('.card-actions-inline');
                actions.forEach(btn => actionsContainer.appendChild(btn));
                container.appendChild(card);
            });
            console.debug(`${this.logPrefix} loadVectorStores rendered`, { vectorStoreCount: stores.length });
            console.groupEnd();
        } catch (error) {
            console.error('Failed to load knowledge bases', error);
            try { console.groupEnd(); } catch (_) {}
            container.innerHTML = '<div class="text-error">Failed to load</div>';
        }
    }
    
    async createVectorStore() {
        const name = await this.prompt('Create Knowledge Base', 'My Knowledge Base');
        if (!name) return;
        
        try {
            await this.assistantManager.createVectorStore(name);
            this.showToast('Created');
            await this.loadVectorStores();
            await this.populateVectorStoreSelect();
        } catch (error) {
            this.showToast('Failed to create', 'error');
        }
    }
    
    async renameVectorStore(id, currentName) {
        const newName = await this.prompt('Rename Knowledge Base', currentName);
        if (!newName || newName === currentName) return;
        
        try {
            await this.assistantManager.updateVectorStore(id, newName);
            this.showToast('Renamed');
            await this.loadVectorStores();
            await this.populateVectorStoreSelect();
        } catch (error) {
            this.showToast('Failed to rename', 'error');
        }
    }
    
    async deleteVectorStore(id) {
        const confirmed = await this.confirm('Delete Knowledge Base', 'All files will be removed. Continue?');
        if (!confirmed) return;
        
        try {
            await this.assistantManager.deleteVectorStore(id);
            this.showToast('Deleted');
            await this.loadVectorStores();
            await this.populateVectorStoreSelect();
        } catch (error) {
            this.showToast('Failed to delete', 'error');
        }
    }
    
    viewFiles(vsId) {
        this.selectedVectorStore = vsId;
        document.getElementById('files-vectorstore-select').value = vsId;
        this.selectVectorStoreForFiles(vsId);
        this.switchTab('files');
    }
    
    // Files
    async populateVectorStoreSelect() {
        const select = document.getElementById('files-vectorstore-select');
        
        try {
            const stores = await this.assistantManager.listVectorStores();
            select.innerHTML = '<option value="">Select...</option>' +
                stores.map(vs => {
                    const fileCount = vs.file_counts?.total || vs.file_counts?.completed || 0;
                    return `<option value="${vs.id}">${vs.name || 'Unnamed'} (${fileCount})</option>`;
                }).join('');
        } catch (error) {
            console.error('Error populating select:', error);
        }
    }
    
    selectVectorStoreForFiles(vsId) {
        this.selectedVectorStore = vsId;
        document.getElementById('upload-file-btn').disabled = !vsId;
        document.getElementById('refresh-files').disabled = !vsId;
        
        if (vsId) {
            this.loadFiles();
        } else {
            document.getElementById('files-list').innerHTML = '<div class="text-muted">Select a knowledge base</div>';
        }
    }
    
    async loadFiles() {
        if (!this.selectedVectorStore) return;
        
        const container = document.getElementById('files-list');
        container.innerHTML = '<div class="text-muted">Loading...</div>';
        
        try {
            console.groupCollapsed(`${this.logPrefix} loadFiles`);
            console.debug(`${this.logPrefix} loadFiles for`, this.selectedVectorStore);
            const files = await this.assistantManager.listVectorStoreFiles(this.selectedVectorStore);
            
            if (files.length === 0) {
                container.innerHTML = '<div class="text-muted">No files yet</div>';
                console.debug(`${this.logPrefix} loadFiles -> empty`);
                console.groupEnd();
                return;
            }
            
            container.innerHTML = '';
            files.forEach(f => {
                const sizeKb = f.bytes ? (f.bytes / 1024).toFixed(2) : 'N/A';
                const createdAt = f.created_at ? new Date(f.created_at * 1000).toLocaleString() : 'Uploaded';
                const fileLabel = f.filename || f.id;
                const safeFileLabel = this.escapeHtml(fileLabel);
                const safeStatus = this.escapeHtml(f.status || 'processing');
                
                const card = document.createElement('div');
                card.className = 'item-card compact';
                card.innerHTML = `
                    <div class="card-main">
                        <div class="card-header">
                            <div class="card-title">
                                <span class="item-name" title="${safeFileLabel}">${safeFileLabel}</span>
                            </div>
                            <div class="card-actions-inline"></div>
                        </div>
                        <div class="card-footer">
                            <div class="card-badges">
                                <span class="card-badge neutral">${safeStatus}</span>
                                <span class="card-badge accent">Size: ${sizeKb} KB</span>
                                <span class="card-badge muted">${createdAt}</span>
                            </div>
                        </div>
                    </div>
                `;
                
                const actionsContainer = card.querySelector('.card-actions-inline');
                actionsContainer.appendChild(
                    this.renderActionButton('delete', 'Remove', () => this.deleteFile(f.id), 'danger')
                );
                container.appendChild(card);
            });
            console.debug(`${this.logPrefix} loadFiles rendered`, { fileCount: files.length });
            console.groupEnd();
        } catch (error) {
            console.error(`${this.logPrefix} loadFiles failed`, error);
            try { console.groupEnd(); } catch (_) {}
            container.innerHTML = '<div class="text-error">Failed to load</div>';
        }
    }
    
    async uploadFile(file) {
        if (!file || !this.selectedVectorStore) return;
        
        this.showToast(`Uploading ${file.name}...`);
        
        try {
            console.groupCollapsed(`${this.logPrefix} uploadFile`);
            console.debug(`${this.logPrefix} uploading`, {
                filename: file.name,
                size: file.size,
                vectorStoreId: this.selectedVectorStore,
                type: file.type
            });
            const allowedExtensions = ['pdf', 'txt', 'md', 'csv', 'jsonl', 'html'];
            const ext = (file.name.split('.').pop() || '').toLowerCase();
            if (!allowedExtensions.includes(ext)) {
                const message = `File type .${ext || 'unknown'} not supported. Please upload one of: ${allowedExtensions.join(', ')}.`;
                console.warn(`${this.logPrefix} blocked unsupported file type`, { filename: file.name, ext });
                this.showToast(message, 'error');
                console.groupEnd();
                return;
            }
            console.debug(`${this.logPrefix} form payload`, {
                field: 'file',
                filename: file.name,
                size: file.size,
                type: file.type
            });
            await this.assistantManager.addFileToVectorStore(this.selectedVectorStore, file);
            this.showToast('Uploaded');
            await Promise.all([
                this.loadFiles(),
                this.loadVectorStores(),
                this.populateVectorStoreSelect()
            ]);
            console.groupEnd();
        } catch (error) {
            console.error(`${this.logPrefix} uploadFile failed`, error);
            this.showToast(`Upload failed: ${error.message || 'Unknown error'}`, 'error');
            try { console.groupEnd(); } catch (_) {}
        } finally {
            document.getElementById('file-input').value = '';
        }
    }
    
    async deleteFile(fileId) {
        const confirmed = await this.confirm('Delete File', 'Remove from knowledge base?');
        if (!confirmed) return;
        
        try {
            await this.assistantManager.deleteVectorStoreFile(this.selectedVectorStore, fileId);
            this.showToast('Deleted');
            await this.loadFiles();
            await this.loadVectorStores();
            await this.populateVectorStoreSelect();
        } catch (error) {
            this.showToast('Failed to delete', 'error');
        }
    }
}

// Create global instance
const settingsPanel = SettingsPanel.getInstance();

