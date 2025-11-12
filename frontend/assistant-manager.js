/**
 * Assistant Manager
 * Handles all OpenAI Assistant API operations from frontend
 */
class AssistantManager {
    static instance = null;
    
    constructor() {
        if (AssistantManager.instance) {
            return AssistantManager.instance;
        }
        
        this.apiUrl = 'http://localhost:5000/api';
        this.logPrefix = '[AssistantManager]';
        // Use sessionStorage instead of localStorage for tab isolation
        // This ensures each tab/window has its own conversation thread
        this.currentAssistantId = sessionStorage.getItem('currentAssistantId');
        this.currentThreadId = sessionStorage.getItem('currentThreadId');
        this.defaultTools = [
            { type: 'file_search' },
            { type: 'code_interpreter' }
        ];
        
        AssistantManager.instance = this;
    }
    
    static getInstance() {
        if (!AssistantManager.instance) {
            AssistantManager.instance = new AssistantManager();
        }
        return AssistantManager.instance;
    }
    
    getToolsForModel(model) {
        // o1 and o3-mini models only support file_search
        if (this.isReasoningModel(model)) {
            return [{ type: 'file_search' }];
        }
        // All other models can use default tools
        return this.defaultTools;
    }

    isReasoningModel(model) {
        return !!model && (model.startsWith('o1') || model.startsWith('o3'));
    }

    normalizeTools(tools, model) {
        let normalized = [];
        if (Array.isArray(tools) && tools.length > 0) {
            normalized = tools.map((tool) => {
                if (typeof tool === 'string') {
                    return { type: tool };
                }
                if (tool && typeof tool === 'object' && tool.type) {
                    return { ...tool };
                }
                return null;
            }).filter(Boolean);
        } else {
            normalized = this.getToolsForModel(model);
        }

        if (this.isReasoningModel(model)) {
            normalized = normalized.filter((tool) => tool.type !== 'code_interpreter');
        }

        // Ensure we don't send duplicate tool types
        const seen = new Set();
        normalized = normalized.filter((tool) => {
            if (seen.has(tool.type)) {
                return false;
            }
            seen.add(tool.type);
            return true;
        });

        return normalized;
    }

    prepareAssistantPayload(basePayload, options = {}) {
        const { fallbackModel = 'gpt-4o-mini', includeModel = true } = options;
        const payload = { ...basePayload };
        const hasExplicitModel = Object.prototype.hasOwnProperty.call(payload, 'model') && typeof payload.model === 'string' && payload.model.length > 0;
        const model = hasExplicitModel ? payload.model : fallbackModel;

        if (includeModel) {
            if (!hasExplicitModel) {
                payload.model = model;
            }
        } else {
            if (hasExplicitModel) {
                delete payload.model;
            }
        }

        payload.tools = this.normalizeTools(payload.tools, model);
        payload.vector_store_ids = Array.isArray(payload.vector_store_ids) ? [...payload.vector_store_ids] : [];

        const hasFileSearch = payload.tools.some((tool) => tool.type === 'file_search');
        if (!hasFileSearch) {
            payload.vector_store_ids = [];
        }

        if (!this.isReasoningModel(model) || !payload.reasoning_effort || payload.reasoning_effort === 'auto') {
            delete payload.reasoning_effort;
        }

        if (payload.metadata && typeof payload.metadata === 'object') {
            const cleaned = {};
            for (const key in payload.metadata) {
                if (payload.metadata.hasOwnProperty(key)) {
                    cleaned[key] = payload.metadata[key];
                }
            }
            payload.metadata = cleaned;
        }

        return payload;
    }
    
    // ============ Assistant Management ============
    
    async createAssistant(nameOrPayload, instructions, model = 'gpt-4o-mini', vectorStoreIds = []) {
        let payload;
        if (typeof nameOrPayload === 'object' && nameOrPayload !== null && !Array.isArray(nameOrPayload)) {
            payload = { ...nameOrPayload };
        } else {
            payload = {
                name: nameOrPayload,
                instructions,
                model,
                vector_store_ids: vectorStoreIds
            };
        }

        if (!payload.name) {
            throw new Error('Assistant name is required');
        }

        const finalPayload = this.prepareAssistantPayload(payload, { fallbackModel: payload.model || model, includeModel: true });
        console.log(`${this.logPrefix} createAssistant payload:`, JSON.stringify(finalPayload, null, 2));

        const response = await fetch(`${this.apiUrl}/assistants`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(finalPayload)
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Failed to create assistant');
        }
        
        const data = await response.json();
        this.setCurrentAssistant(data.id);
        return data;
    }
    
    async getAssistant(assistantId) {
        const response = await fetch(`${this.apiUrl}/assistants/${assistantId}`);
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Failed to get assistant');
        }
        
        return await response.json();
    }
    
    async listAssistants(limit = 20) {
        const response = await fetch(`${this.apiUrl}/assistants?limit=${limit}`);
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Failed to list assistants');
        }
        
        return await response.json();
    }
    
    async updateAssistant(assistantId, updatesOrName, instructions, model, vectorStoreIds, existingModel) {
        console.log(`🔄 ${this.logPrefix} updateAssistant START @ ${new Date().toISOString()}`, { assistantId, updatesOrName, instructions, model, vectorStoreIds });
        
        if (!assistantId) {
            throw new Error('Assistant ID is required');
        }

        let payload;
        if (typeof updatesOrName === 'object' && updatesOrName !== null && !Array.isArray(updatesOrName)) {
            payload = { ...updatesOrName };
            console.log(`${this.logPrefix} updateAssistant - using object payload:`, payload);
        } else {
            payload = {
                name: updatesOrName,
                instructions,
                model,
                vector_store_ids: vectorStoreIds
            };
            console.log(`${this.logPrefix} updateAssistant - built payload:`, payload);
        }

        const includeModel = Object.prototype.hasOwnProperty.call(payload, 'model') && payload.model;
        const fallbackModel = includeModel ? payload.model : (existingModel || undefined);
        const finalPayload = this.prepareAssistantPayload(payload, {
            fallbackModel: fallbackModel || 'gpt-4o-mini',
            includeModel
        });
        Object.keys(finalPayload).forEach((key) => {
            if (finalPayload[key] === undefined) {
                delete finalPayload[key];
            }
        });
        
        console.log(`${this.logPrefix} updateAssistant - final payload:`, JSON.stringify(finalPayload, null, 2));

        const response = await fetch(`${this.apiUrl}/assistants/${assistantId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(finalPayload)
        });
        
        console.log(`${this.logPrefix} updateAssistant - response status:`, response.status);
        
        if (!response.ok) {
            const error = await response.json();
            console.error(`${this.logPrefix} updateAssistant FAILED:`, error);
            throw new Error(error.error || 'Failed to update assistant');
        }
        
        const result = await response.json();
        console.log(`${this.logPrefix} updateAssistant SUCCESS:`, result);
        return result;
    }
    
    async deleteAssistant(assistantId) {
        console.log(`🗑️ ${this.logPrefix} deleteAssistant START @ ${new Date().toISOString()}`, { assistantId });
        
        const response = await fetch(`${this.apiUrl}/assistants/${assistantId}`, {
            method: 'DELETE'
        });
        
        console.log(`${this.logPrefix} deleteAssistant - response status:`, response.status);
        
        if (!response.ok) {
            const error = await response.json();
            console.error(`${this.logPrefix} deleteAssistant FAILED:`, error);
            throw new Error(error.error || 'Failed to delete assistant');
        }
        
        const result = await response.json();
        console.log(`${this.logPrefix} deleteAssistant SUCCESS:`, result);
        return result;
    }
    
    // ============ Vector Store Management ============
    
    async createVectorStore(name) {
        const response = await fetch(`${this.apiUrl}/vector-stores`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Failed to create vector store');
        }
        
        return await response.json();
    }
    
    async getVectorStore(vectorStoreId) {
        const response = await fetch(`${this.apiUrl}/vector-stores/${vectorStoreId}`);
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Failed to get vector store');
        }
        
        return await response.json();
    }
    
    async listVectorStores(limit = 20) {
        // Add cache-busting timestamp to ensure fresh data
        const timestamp = Date.now();
        const response = await fetch(`${this.apiUrl}/vector-stores?limit=${limit}&_t=${timestamp}`, {
            cache: 'no-cache',
            headers: {
                'Cache-Control': 'no-cache'
            }
        });
        
        if (!response.ok) {
            // Handle 404 gracefully - OpenAI sometimes returns 404 when there are no vector stores
            if (response.status === 404) {
                console.warn(`${this.logPrefix} listVectorStores returned 404, returning empty list`);
                return [];
            }
            const error = await response.json();
            throw new Error(error.error || 'Failed to list vector stores');
        }
        
        const data = await response.json();
        console.debug(`${this.logPrefix} listVectorStores returned`, { count: data.length, file_counts: data.map(vs => ({ id: vs.id, name: vs.name, file_counts: vs.file_counts })) });
        return data;
    }
    
    async updateVectorStore(vectorStoreId, name) {
        const response = await fetch(`${this.apiUrl}/vector-stores/${vectorStoreId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Failed to update vector store');
        }
        
        return await response.json();
    }
    
    async deleteVectorStore(vectorStoreId) {
        const response = await fetch(`${this.apiUrl}/vector-stores/${vectorStoreId}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Failed to delete vector store');
        }
        
        return await response.json();
    }
    
    // ============ File Management ============
    
    async uploadFile(file) {
        console.groupCollapsed(`${this.logPrefix} uploadFile`);
        console.debug(`${this.logPrefix} preparing upload`, { filename: file?.name, size: file?.size });
        const formData = new FormData();
        formData.append('file', file);
        
        const response = await fetch(`${this.apiUrl}/files`, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            const error = await response.json();
            console.error(`${this.logPrefix} uploadFile failed`, error);
            throw new Error(error.error || 'Failed to upload file');
        }
        
        const data = await response.json();
        console.debug(`${this.logPrefix} uploadFile success`, data);
        console.groupEnd();
        return data;
    }
    
    async addFileToVectorStore(vectorStoreId, file) {
        console.groupCollapsed(`${this.logPrefix} addFileToVectorStore`);
        console.debug(`${this.logPrefix} adding file to vector store`, {
            vectorStoreId,
            filename: file?.name,
            size: file?.size
        });
        const formData = new FormData();
        formData.append('file', file);
        
        const response = await fetch(`${this.apiUrl}/vector-stores/${vectorStoreId}/files`, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            const error = await response.json();
            console.error(`${this.logPrefix} addFileToVectorStore failed`, error);
            throw new Error(error.error || 'Failed to add file to vector store');
        }
        
        const data = await response.json();
        console.debug(`${this.logPrefix} addFileToVectorStore success`, data);
        console.groupEnd();
        return data;
    }
    
    async listVectorStoreFiles(vectorStoreId, limit = 100) {
        console.debug(`${this.logPrefix} listVectorStoreFiles`, { vectorStoreId, limit });
        const response = await fetch(`${this.apiUrl}/vector-stores/${vectorStoreId}/files?limit=${limit}`);
        
        if (!response.ok) {
            const error = await response.json();
            console.error(`${this.logPrefix} listVectorStoreFiles failed`, error);
            throw new Error(error.error || 'Failed to list files');
        }
        
        return await response.json();
    }
    
    async deleteVectorStoreFile(vectorStoreId, fileId) {
        console.debug(`${this.logPrefix} deleteVectorStoreFile`, { vectorStoreId, fileId });
        const response = await fetch(`${this.apiUrl}/vector-stores/${vectorStoreId}/files/${fileId}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) {
            const error = await response.json();
            console.error(`${this.logPrefix} deleteVectorStoreFile failed`, error);
            throw new Error(error.error || 'Failed to delete file');
        }
        
        return await response.json();
    }
    
    async deleteFile(fileId) {
        console.debug(`${this.logPrefix} deleteFile`, { fileId });
        const response = await fetch(`${this.apiUrl}/files/${fileId}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) {
            const error = await response.json();
            console.error(`${this.logPrefix} deleteFile failed`, error);
            throw new Error(error.error || 'Failed to delete file');
        }
        
        return await response.json();
    }
    
    // ============ Thread Management ============
    
    async createThread() {
        const response = await fetch(`${this.apiUrl}/threads`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Failed to create thread');
        }
        
        const data = await response.json();
        this.setCurrentThread(data.thread_id);
        return data.thread_id;
    }
    
    async getThreadMessages(threadId, limit = 20) {
        const response = await fetch(`${this.apiUrl}/threads/${threadId}/messages?limit=${limit}`);
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Failed to get messages');
        }
        
        return await response.json();
    }
    
    async deleteThread(threadId) {
        const response = await fetch(`${this.apiUrl}/threads/${threadId}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Failed to delete thread');
        }
        
        if (threadId === this.currentThreadId) {
            this.currentThreadId = null;
        }
        
        return await response.json();
    }
    
    // ============ Chat with Assistant ============
    
    async chat(message, threadId = null, assistantId = null) {
        const response = await fetch(`${this.apiUrl}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message,
                thread_id: threadId || this.currentThreadId,
                assistant_id: assistantId || this.currentAssistantId
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Failed to chat with assistant');
        }
        
        const data = await response.json();
        
        // Update current thread if new one was created
        if (!this.currentThreadId && data.thread_id) {
            this.currentThreadId = data.thread_id;
        }
        
        return data;
    }
    
    // ============ Convenience Methods ============
    
    setCurrentAssistant(assistantId) {
        if (assistantId) {
            this.currentAssistantId = assistantId;
            sessionStorage.setItem('currentAssistantId', assistantId);
        } else {
            this.currentAssistantId = null;
            sessionStorage.removeItem('currentAssistantId');
        }
    }
    
    getCurrentAssistant() {
        if (!this.currentAssistantId) {
            this.currentAssistantId = sessionStorage.getItem('currentAssistantId');
        }
        return this.currentAssistantId;
    }
    
    setCurrentThread(threadId) {
        if (threadId) {
            this.currentThreadId = threadId;
            sessionStorage.setItem('currentThreadId', threadId);
        } else {
            this.currentThreadId = null;
            sessionStorage.removeItem('currentThreadId');
        }
    }
    
    getCurrentThread() {
        if (!this.currentThreadId) {
            this.currentThreadId = sessionStorage.getItem('currentThreadId');
        }
        return this.currentThreadId;
    }
    
    async ensureAssistant() {
        let assistantId = this.getCurrentAssistant();
        if (assistantId) {
            console.debug(`${this.logPrefix} ensureAssistant using cached`, { assistantId });
            return assistantId;
        }
        
        try {
            const assistants = await this.listAssistants(50);
            if (Array.isArray(assistants) && assistants.length > 0) {
                assistantId = assistants[0].id;
                this.setCurrentAssistant(assistantId);
                return assistantId;
            }
        } catch (error) {
            console.warn('Unable to list assistants, attempting to create a default assistant.', error);
        }
        
        try {
            const created = await this.createAssistant(
                'Rhasspy Assistant',
                'You are Rhasspy, a helpful AI assistant.',
                'gpt-4o-mini'
            );
            assistantId = created.id;
            this.setCurrentAssistant(assistantId);
            return assistantId;
        } catch (error) {
            console.error('Failed to create default assistant.', error);
            throw error;
        }
    }
    
    async ensureThread() {
        const assistantId = await this.ensureAssistant();
        let threadId = this.getCurrentThread();
        if (threadId) {
            return { assistantId, threadId };
        }
        
        threadId = await this.createThread();
        return { assistantId, threadId };
    }
    
    clearSession() {
        // Only clear thread_id, keep assistant_id for reuse
        this.setCurrentThread(null);
        // Don't clear assistant_id - it should persist across conversations
        // this.setCurrentAssistant(null);
    }
}

