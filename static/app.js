// SimpleChat ES6 Application Logic

document.addEventListener('DOMContentLoaded', () => {
    // --- Application State ---
    let state = {
        activeConversationId: null,
        conversations: [],
        messages: [],
        mcpTools: [],
        settings: {
            base_url: 'https://api.openai.com/v1',
            api_key: '',
            model: 'gpt-4o'
        },
        isStreaming: false
    };

    // --- DOM Elements ---
    const sidebar = document.getElementById('sidebar');
    const sidebarOverlay = document.getElementById('sidebarOverlay');
    const toggleSidebarBtn = document.getElementById('toggleSidebarBtn');
    const closeSidebarBtn = document.getElementById('closeSidebarBtn');
    const newChatBtn = document.getElementById('newChatBtn');
    const conversationsList = document.getElementById('conversationsList');
    const convCount = document.getElementById('convCount');
    const chatTitleInput = document.getElementById('chatTitleInput');
    const modelSelect = document.getElementById('modelSelect');
    const refreshModelsBtn = document.getElementById('refreshModelsBtn');
    const toggleSystemPromptBtn = document.getElementById('toggleSystemPromptBtn');
    const systemPromptPanel = document.getElementById('systemPromptPanel');
    const closeSystemPromptBtn = document.getElementById('closeSystemPromptBtn');
    const systemPromptInput = document.getElementById('systemPromptInput');
    const messagesContainer = document.getElementById('messagesContainer');
    const welcomeScreen = document.getElementById('welcomeScreen');
    const userInput = document.getElementById('userInput');
    const sendBtn = document.getElementById('sendBtn');
    const mcpToggle = document.getElementById('mcpToggle');
    const endpointBadge = document.getElementById('endpointBadge');
    
    // Modals
    const mcpModal = document.getElementById('mcpModal');
    const openMcpModalBtn = document.getElementById('openMcpModalBtn');
    const closeMcpModalBtn = document.getElementById('closeMcpModalBtn');
    const mcpStatusText = document.getElementById('mcpStatusText');
    const mcpIndicator = document.getElementById('mcpIndicator');
    const tabActiveTools = document.getElementById('tabActiveTools');
    const tabJsonConfig = document.getElementById('tabJsonConfig');
    const activeToolsContent = document.getElementById('activeToolsContent');
    const jsonConfigContent = document.getElementById('jsonConfigContent');
    const mcpToolsList = document.getElementById('mcpToolsList');
    const toolsCount = document.getElementById('toolsCount');
    const mcpJsonInput = document.getElementById('mcpJsonInput');
    const saveMcpConfigBtn = document.getElementById('saveMcpConfigBtn');

    const settingsModal = document.getElementById('settingsModal');
    const openSettingsBtn = document.getElementById('openSettingsBtn');
    const closeSettingsModalBtn = document.getElementById('closeSettingsModalBtn');
    const settingBaseUrl = document.getElementById('settingBaseUrl');
    const settingApiKey = document.getElementById('settingApiKey');
    const settingDefaultModel = document.getElementById('settingDefaultModel');
    const saveSettingsBtn = document.getElementById('saveSettingsBtn');

    // --- Configure Marked JS ---
    marked.setOptions({
        highlight: function(code, lang) {
            if (lang && hljs.getLanguage(lang)) {
                return hljs.highlight(code, { language: lang }).value;
            }
            return hljs.highlightAuto(code).value;
        },
        breaks: true
    });

    // --- Init Application ---
    async function init() {
        await loadSettings();
        await loadMcpInfo();
        await loadConversations();
        await loadModels();
        setupEventListeners();
    }

    // --- Event Listeners Setup ---
    function setupEventListeners() {
        // Sidebar Toggles
        toggleSidebarBtn.addEventListener('click', () => {
            sidebar.classList.add('open');
            sidebarOverlay.classList.add('active');
        });
        const closeSidebar = () => {
            sidebar.classList.remove('open');
            sidebarOverlay.classList.remove('active');
        };
        closeSidebarBtn.addEventListener('click', closeSidebar);
        sidebarOverlay.addEventListener('click', closeSidebar);

        // New Chat
        newChatBtn.addEventListener('click', () => {
            createNewConversation();
            closeSidebar();
        });

        // Chat Title Editing
        chatTitleInput.addEventListener('change', async () => {
            if (state.activeConversationId) {
                const newTitle = chatTitleInput.value.trim() || 'Untitled Chat';
                await fetch(`/api/conversations/${state.activeConversationId}`, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ title: newTitle })
                });
                await loadConversations();
            }
        });

        // Model Select & Refresh
        modelSelect.addEventListener('change', () => {
            state.settings.model = modelSelect.value;
            if (state.activeConversationId) {
                fetch(`/api/conversations/${state.activeConversationId}`, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ model: modelSelect.value })
                });
            }
        });
        refreshModelsBtn.addEventListener('click', loadModels);

        // System Prompt Panel
        toggleSystemPromptBtn.addEventListener('click', () => {
            systemPromptPanel.classList.toggle('hidden');
        });
        closeSystemPromptBtn.addEventListener('click', () => {
            systemPromptPanel.classList.add('hidden');
        });
        systemPromptInput.addEventListener('change', () => {
            if (state.activeConversationId) {
                fetch(`/api/conversations/${state.activeConversationId}`, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ system_prompt: systemPromptInput.value })
                });
            }
        });

        // User Input Auto-resize & Sending
        userInput.addEventListener('input', () => {
            userInput.style.height = 'auto';
            userInput.style.height = Math.min(userInput.scrollHeight, 150) + 'px';
        });

        userInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });

        sendBtn.addEventListener('click', sendMessage);

        // Suggestions
        document.querySelectorAll('.suggestion-card').forEach(card => {
            card.addEventListener('click', () => {
                const prompt = card.getAttribute('data-prompt');
                if (prompt) {
                    userInput.value = prompt;
                    sendMessage();
                }
            });
        });

        // MCP Modal & Tabs
        openMcpModalBtn.addEventListener('click', () => {
            mcpModal.classList.remove('hidden');
        });
        closeMcpModalBtn.addEventListener('click', () => {
            mcpModal.classList.add('hidden');
        });

        tabActiveTools.addEventListener('click', () => {
            tabActiveTools.classList.add('active');
            tabJsonConfig.classList.remove('active');
            activeToolsContent.classList.remove('hidden');
            jsonConfigContent.classList.add('hidden');
        });

        tabJsonConfig.addEventListener('click', () => {
            tabJsonConfig.classList.add('active');
            tabActiveTools.classList.remove('active');
            jsonConfigContent.classList.remove('hidden');
            activeToolsContent.classList.add('hidden');
        });

        saveMcpConfigBtn.addEventListener('click', async () => {
            try {
                const parsed = JSON.parse(mcpJsonInput.value);
                const resp = await fetch('/api/mcp/servers', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(parsed)
                });
                if (resp.ok) {
                    alert('MCP configuration saved and servers restarted!');
                    await loadMcpInfo();
                } else {
                    alert('Failed to save MCP configuration.');
                }
            } catch (err) {
                alert('Invalid JSON: ' + err.message);
            }
        });

        // Settings Modal
        openSettingsBtn.addEventListener('click', () => {
            settingBaseUrl.value = state.settings.base_url || 'https://api.openai.com/v1';
            settingApiKey.value = state.settings.api_key || '';
            settingDefaultModel.value = state.settings.model || 'gpt-4o';
            settingsModal.classList.remove('hidden');
        });

        closeSettingsModalBtn.addEventListener('click', () => {
            settingsModal.classList.add('hidden');
        });

        saveSettingsBtn.addEventListener('click', async () => {
            const baseUrl = settingBaseUrl.value.trim();
            const apiKey = settingApiKey.value.trim();
            const defModel = settingDefaultModel.value.trim();

            state.settings.base_url = baseUrl;
            state.settings.api_key = apiKey;
            state.settings.model = defModel;

            await fetch('/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(state.settings)
            });

            updateEndpointBadge();
            settingsModal.classList.add('hidden');
            await loadModels();
        });

        // Copy Code Buttons Event Delegation
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('copy-code-btn')) {
                const codeBlock = e.target.parentElement.querySelector('code');
                if (codeBlock) {
                    navigator.clipboard.writeText(codeBlock.innerText);
                    e.target.innerText = 'Copied!';
                    setTimeout(() => { e.target.innerText = 'Copy'; }, 2000);
                }
            }
        });
    }

    // --- Data Loading Functions ---

    async function loadSettings() {
        try {
            const res = await fetch('/api/settings');
            if (res.ok) {
                const data = await res.json();
                state.settings.base_url = data.base_url || 'https://api.openai.com/v1';
                state.settings.api_key = data.api_key || '';
                state.settings.model = data.model || 'gpt-4o';
            }
        } catch (e) {
            console.error('Error loading settings:', e);
        }
        updateEndpointBadge();
    }

    function updateEndpointBadge() {
        try {
            const url = new URL(state.settings.base_url);
            endpointBadge.innerText = `Endpoint: ${url.hostname}`;
        } catch (e) {
            endpointBadge.innerText = `Endpoint: ${state.settings.base_url}`;
        }
    }

    async function loadMcpInfo() {
        try {
            const res = await fetch('/api/mcp/servers');
            if (res.ok) {
                const data = await res.json();
                state.mcpTools = data.tools || [];
                const activeCount = (data.active_servers || []).length;

                mcpStatusText.innerText = `${activeCount} Server${activeCount !== 1 ? 's' : ''} (${state.mcpTools.length} Tools)`;
                toolsCount.innerText = state.mcpTools.length;

                if (activeCount > 0) {
                    mcpIndicator.className = 'mcp-indicator online';
                } else {
                    mcpIndicator.className = 'mcp-indicator offline';
                }

                // Render Tools List in Modal
                mcpToolsList.innerHTML = '';
                if (state.mcpTools.length === 0) {
                    mcpToolsList.innerHTML = '<div class="modal-description">No active MCP tools registered.</div>';
                } else {
                    state.mcpTools.forEach(t => {
                        const fn = t.function;
                        const card = document.createElement('div');
                        card.className = 'tool-card';
                        card.innerHTML = `
                            <div class="tool-card-name">⚡ ${escapeHtml(fn.name)}</div>
                            <div class="tool-card-desc">${escapeHtml(fn.description)}</div>
                        `;
                        mcpToolsList.appendChild(card);
                    });
                }

                // Render JSON config in modal
                mcpJsonInput.value = JSON.stringify(data.config || {}, null, 2);
            }
        } catch (e) {
            console.error('Error loading MCP info:', e);
        }
    }

    async function loadConversations() {
        try {
            const res = await fetch('/api/conversations');
            if (res.ok) {
                state.conversations = await res.json();
                convCount.innerText = state.conversations.length;
                renderConversationsList();

                if (!state.activeConversationId && state.conversations.length > 0) {
                    selectConversation(state.conversations[0].id);
                } else if (state.conversations.length === 0) {
                    showWelcomeScreen();
                }
            }
        } catch (e) {
            console.error('Error loading conversations:', e);
        }
    }

    function renderConversationsList() {
        conversationsList.innerHTML = '';
        state.conversations.forEach(c => {
            const item = document.createElement('div');
            item.className = `conv-item ${c.id === state.activeConversationId ? 'active' : ''}`;
            item.setAttribute('data-id', c.id);

            item.innerHTML = `
                <span class="conv-title">${escapeHtml(c.title || 'Untitled Chat')}</span>
                <div class="conv-actions">
                    <button class="btn-icon delete-conv-btn" title="Delete conversation">🗑️</button>
                </div>
            `;

            item.addEventListener('click', (e) => {
                if (!e.target.classList.contains('delete-conv-btn')) {
                    selectConversation(c.id);
                }
            });

            const delBtn = item.querySelector('.delete-conv-btn');
            delBtn.addEventListener('click', async (e) => {
                e.stopPropagation();
                if (confirm(`Delete conversation "${c.title}"?`)) {
                    await fetch(`/api/conversations/${c.id}`, { method: 'DELETE' });
                    if (state.activeConversationId === c.id) {
                        state.activeConversationId = null;
                    }
                    await loadConversations();
                }
            });

            conversationsList.appendChild(item);
        });
    }

    async function selectConversation(convId) {
        state.activeConversationId = convId;
        renderConversationsList();

        try {
            const res = await fetch(`/api/conversations/${convId}`);
            if (res.ok) {
                const conv = await res.json();
                chatTitleInput.value = conv.title || 'Untitled Chat';
                systemPromptInput.value = conv.system_prompt || '';
                if (conv.model) {
                    modelSelect.value = conv.model;
                }
                state.messages = conv.messages || [];
                renderMessages();
            }
        } catch (e) {
            console.error('Error selecting conversation:', e);
        }
    }

    async function createNewConversation() {
        try {
            const res = await fetch('/api/conversations', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    title: 'New Chat',
                    model: state.settings.model || 'gpt-4o',
                    system_prompt: systemPromptInput.value
                })
            });
            if (res.ok) {
                const conv = await res.json();
                await loadConversations();
                selectConversation(conv.id);
            }
        } catch (e) {
            console.error('Error creating conversation:', e);
        }
    }

    async function loadModels() {
        try {
            const queryParams = new URLSearchParams({
                base_url: state.settings.base_url || '',
                api_key: state.settings.api_key || ''
            });
            const res = await fetch(`/api/models?${queryParams}`);
            if (res.ok) {
                const models = await res.json();
                if (models.length > 0) {
                    modelSelect.innerHTML = '';
                    models.forEach(m => {
                        const opt = document.createElement('option');
                        opt.value = m.id;
                        opt.innerText = m.id;
                        modelSelect.appendChild(opt);
                    });

                    if (state.settings.model) {
                        modelSelect.value = state.settings.model;
                    }
                }
            }
        } catch (e) {
            console.error('Error loading models:', e);
        }
    }

    // --- Message Rendering & Streaming ---

    function showWelcomeScreen() {
        messagesContainer.innerHTML = '';
        messagesContainer.appendChild(welcomeScreen);
        welcomeScreen.classList.remove('hidden');
    }

    function renderMessages() {
        messagesContainer.innerHTML = '';
        if (state.messages.length === 0) {
            showWelcomeScreen();
            return;
        }

        state.messages.forEach(m => {
            if (m.role === 'system') return;
            const item = createMessageElement(m.role, m.content, m.reasoning_content, m.tool_calls);
            messagesContainer.appendChild(item);
        });

        scrollToBottom();
    }

    function createMessageElement(role, content = '', reasoningContent = '', toolCalls = null) {
        const item = document.createElement('div');
        item.className = `message-item ${role}`;

        const header = document.createElement('div');
        header.className = 'message-header';
        header.innerText = role === 'user' ? 'You' : 'AI Assistant';
        item.appendChild(header);

        const bubble = document.createElement('div');
        bubble.className = 'message-bubble';

        // Add Thought Container if reasoning_content is present
        if (reasoningContent) {
            const thoughtDiv = createThoughtContainer(reasoningContent, false);
            bubble.appendChild(thoughtDiv);
        }

        // Add Tool Call Badges if present
        if (toolCalls && Array.isArray(toolCalls)) {
            toolCalls.forEach(tc => {
                const badge = createToolBadge(tc.name || 'Tool Call', tc.result || tc.arguments);
                bubble.appendChild(badge);
            });
        }

        // Main Text Content
        const contentDiv = document.createElement('div');
        contentDiv.className = 'markdown-body';
        if (content) {
            contentDiv.innerHTML = marked.parse(content);
            enhanceCodeBlocks(contentDiv);
        }
        bubble.appendChild(contentDiv);

        item.appendChild(bubble);
        return item;
    }

    function createThoughtContainer(initialText = '', isThinking = false) {
        const container = document.createElement('div');
        container.className = 'thought-container';

        const header = document.createElement('div');
        header.className = 'thought-header';

        const titleDiv = document.createElement('div');
        titleDiv.className = 'thought-title';
        titleDiv.innerHTML = `
            ${isThinking ? '<span class="thought-spinner"></span>' : ''}
            <span>🧠 Thought Process</span>
        `;

        const icon = document.createElement('span');
        icon.className = 'thought-toggle-icon';
        icon.innerText = '▼';

        header.appendChild(titleDiv);
        header.appendChild(icon);

        const body = document.createElement('div');
        body.className = 'thought-body';
        body.innerText = initialText;

        header.addEventListener('click', () => {
            container.classList.toggle('collapsed');
        });

        container.appendChild(header);
        container.appendChild(body);
        return container;
    }

    function createToolBadge(toolName, details) {
        const badge = document.createElement('div');
        badge.className = 'tool-execution-badge';
        badge.innerHTML = `
            <div class="tool-badge-header">
                <span>🛠️ Tool Called: <code>${escapeHtml(toolName)}</code></span>
                <span>✅ Complete</span>
            </div>
            <div class="tool-badge-body">${escapeHtml(typeof details === 'object' ? JSON.stringify(details, null, 2) : String(details))}</div>
        `;
        return badge;
    }

    function enhanceCodeBlocks(container) {
        container.querySelectorAll('pre').forEach(pre => {
            if (!pre.querySelector('.copy-code-btn')) {
                const copyBtn = document.createElement('button');
                copyBtn.className = 'copy-code-btn';
                copyBtn.innerText = 'Copy';
                pre.appendChild(copyBtn);
            }
        });
    }

    // --- Real-time SSE Chat Streamer ---

    async function sendMessage() {
        const text = userInput.value.trim();
        if (!text || state.isStreaming) return;

        // Clear input field
        userInput.value = '';
        userInput.style.height = 'auto';

        // Remove welcome screen if active
        if (welcomeScreen.parentElement) {
            welcomeScreen.remove();
        }

        // Render User Message immediately
        const userMsg = { role: 'user', content: text };
        state.messages.push(userMsg);
        const userItem = createMessageElement('user', text);
        messagesContainer.appendChild(userItem);
        scrollToBottom();

        state.isStreaming = true;
        sendBtn.disabled = true;

        // Create Assistant Message Placeholder
        const assistantItem = document.createElement('div');
        assistantItem.className = 'message-item assistant';
        
        const header = document.createElement('div');
        header.className = 'message-header';
        header.innerText = 'AI Assistant';
        assistantItem.appendChild(header);

        const bubble = document.createElement('div');
        bubble.className = 'message-bubble';

        // Dynamic Containers inside Bubble
        let thoughtContainer = null;
        let thoughtBody = null;
        let mainContentDiv = document.createElement('div');
        mainContentDiv.className = 'markdown-body';
        bubble.appendChild(mainContentDiv);
        assistantItem.appendChild(bubble);

        messagesContainer.appendChild(assistantItem);
        scrollToBottom();

        let fullReasoningText = '';
        let fullContentText = '';

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    conversation_id: state.activeConversationId,
                    message: text,
                    model: modelSelect.value,
                    base_url: state.settings.base_url,
                    api_key: state.settings.api_key,
                    system_prompt: systemPromptInput.value,
                    enable_mcp: mcpToggle.checked
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP Error ${response.status}`);
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder('utf-8');
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop(); // Keep incomplete line in buffer

                let currentEvent = null;

                for (let line of lines) {
                    line = line.trim();
                    if (!line) continue;

                    if (line.startsWith('event: ')) {
                        currentEvent = line.substring(7);
                    } else if (line.startsWith('data: ')) {
                        const dataJson = line.substring(6);
                        try {
                            const data = JSON.parse(dataJson);

                            if (currentEvent === 'reasoning') {
                                if (!thoughtContainer) {
                                    thoughtContainer = createThoughtContainer('', true);
                                    thoughtBody = thoughtContainer.querySelector('.thought-body');
                                    bubble.insertBefore(thoughtContainer, mainContentDiv);
                                }
                                fullReasoningText += data.delta || '';
                                thoughtBody.innerText = fullReasoningText;
                            } else if (currentEvent === 'content') {
                                fullContentText += data.delta || '';
                                mainContentDiv.innerHTML = marked.parse(fullContentText);
                                enhanceCodeBlocks(mainContentDiv);
                            } else if (currentEvent === 'tool_start' || currentEvent === 'tool_executing') {
                                let badge = bubble.querySelector(`.tool-badge-${data.name}`);
                                if (!badge) {
                                    badge = document.createElement('div');
                                    badge.className = `tool-execution-badge tool-badge-${data.name}`;
                                    badge.innerHTML = `
                                        <div class="tool-badge-header">
                                            <span>🛠️ Executing Tool: <code>${escapeHtml(data.name)}</code></span>
                                            <span><span class="thought-spinner"></span> Running...</span>
                                        </div>
                                    `;
                                    bubble.insertBefore(badge, mainContentDiv);
                                }
                            } else if (currentEvent === 'tool_result') {
                                const badge = bubble.querySelector(`.tool-badge-${data.name}`);
                                if (badge) {
                                    badge.innerHTML = `
                                        <div class="tool-badge-header">
                                            <span>🛠️ Tool Called: <code>${escapeHtml(data.name)}</code></span>
                                            <span>✅ Completed</span>
                                        </div>
                                        <div class="tool-badge-body">${escapeHtml(data.result)}</div>
                                    `;
                                }
                            } else if (currentEvent === 'done') {
                                if (data.conversation_id && data.conversation_id !== state.activeConversationId) {
                                    state.activeConversationId = data.conversation_id;
                                }
                                if (thoughtContainer) {
                                    const spinner = thoughtContainer.querySelector('.thought-spinner');
                                    if (spinner) spinner.remove();
                                }
                                await loadConversations();
                            } else if (currentEvent === 'error') {
                                mainContentDiv.innerHTML += `<div style="color: var(--accent-rose); margin-top: 10px;">⚠️ Error: ${escapeHtml(data.message)}</div>`;
                            }
                        } catch (err) {
                            console.error('SSE JSON parse error:', err);
                        }
                    }
                }
                scrollToBottom();
            }

        } catch (err) {
            mainContentDiv.innerHTML = `<div style="color: var(--accent-rose);">⚠️ Connection error: ${escapeHtml(err.message)}</div>`;
        } finally {
            state.isStreaming = false;
            sendBtn.disabled = false;
        }
    }

    // --- Utility Functions ---

    function scrollToBottom() {
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    // Run Initialization
    init();
});
