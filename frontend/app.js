/**
 * Main application initializer
 */
window.currentLanguage = 'en-IN'; // Default to Indian English - make it global
let currentLanguage = 'en-IN'; // Keep for backward compatibility
let isMuted = false;
let audioStream = null;

document.addEventListener('DOMContentLoaded', async () => {
    // Initialize Avatar
    const avatarManager = AvatarManager.getInstance();
    avatarManager.init();
    
    // Initialize Chat
    const chatManager = ChatManager.getInstance();
    chatManager.init();
    
    // Initialize Audio
    const audioManager = AudioManager.getInstance();
    await audioManager.init();
    
    // Initialize Settings Panel
    const settingsPanel = SettingsPanel.getInstance();
    await settingsPanel.init();
    
    // Initialize UI controls (includes Rhasspy button)
    initUIControls();
    
    console.log('3D Avatar Chat System initialized - Click "Rhasspy" button to start');
});

function initUIControls() {
    // Language selector (up arrow button)
    const menuBtn = document.getElementById('menu-btn');
    const languageDropdown = document.getElementById('language-dropdown');
    
    if (menuBtn && languageDropdown) {
        // Toggle dropdown on click
        menuBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            languageDropdown.classList.toggle('show');
        });
        
        // Close dropdown when clicking outside
        document.addEventListener('click', (e) => {
            if (!menuBtn.contains(e.target) && !languageDropdown.contains(e.target)) {
                languageDropdown.classList.remove('show');
            }
        });
        
        // Language selection
        const languageOptions = languageDropdown.querySelectorAll('.language-option');
        languageOptions.forEach(option => {
            option.addEventListener('click', () => {
                // Remove selected class from all options
                languageOptions.forEach(opt => opt.classList.remove('selected'));
                // Add selected class to clicked option
                option.classList.add('selected');
                
                // Update current language (both local and global)
                currentLanguage = option.dataset.lang;
                window.currentLanguage = option.dataset.lang;
                
                // Update UI
                console.log(`🌐 Language changed to: ${currentLanguage}`);
                const chatManager = ChatManager.getInstance();
                chatManager.addMessage('system', `Language set to: ${option.textContent}`);
                
                // Close dropdown
                languageDropdown.classList.remove('show');
                
                // Language preference is now automatically sent with each request
            });
        });
        
        // Set initial selected language
        const initialOption = Array.from(languageOptions).find(opt => opt.dataset.lang === currentLanguage);
        if (initialOption) {
            initialOption.classList.add('selected');
        }
    }

    // Mute button
    const muteBtn = document.getElementById('mute-btn');
    if (muteBtn) {
        muteBtn.addEventListener('click', () => {
            isMuted = !isMuted;
            muteBtn.classList.toggle('muted', isMuted);
            
            // Mute/unmute microphone
            const audioManager = AudioManager.getInstance();
            if (isMuted) {
                audioManager.muteMicrophone();
                console.log('🔇 Microphone muted');
            } else {
                audioManager.unmuteMicrophone();
                console.log('🔊 Microphone unmuted');
            }
        });
    }

    // Rhasspy start button (replaces end-call-btn)
    const rhasspyController = RhasspyModeController.getInstance();
    rhasspyController.bind();

    // Settings button
    const settingsBtn = document.getElementById('settings-btn');
    if (settingsBtn) {
        settingsBtn.addEventListener('click', async () => {
            const settingsPanel = SettingsPanel.getInstance();
            await settingsPanel.open();
        });
    }

    // Chat mode button (toggle chat panel)
    const chatModeBtn = document.getElementById('chat-mode-btn');
    if (chatModeBtn) {
        chatModeBtn.addEventListener('click', () => {
            const chatSection = document.querySelector('.chat-section');
            if (chatSection) {
                const isHidden = chatSection.style.display === 'none';
                chatSection.style.display = isHidden ? 'flex' : 'none';
                chatModeBtn.classList.toggle('active', !isHidden);
                console.log(`Chat panel ${isHidden ? 'shown' : 'hidden'}`);
            }
        });
    }

    // Status button (no click action needed - it's just a display)
    // The status is automatically updated by AudioManager via ChatManager.updateStatus()

    // Close chat button
    const closeChatBtn = document.getElementById('close-chat-btn');
    if (closeChatBtn) {
        closeChatBtn.addEventListener('click', () => {
            const chatSection = document.querySelector('.chat-section');
            if (chatSection) {
                chatSection.style.display = 'none';
                // Update chat mode button state
                const chatModeBtn = document.getElementById('chat-mode-btn');
                if (chatModeBtn) {
                    chatModeBtn.classList.remove('active');
                }
            }
        });
    }

    // Time remaining update
    let timeRemaining = 600; // 10 minutes in seconds
    const timeBadge = document.getElementById('time-remaining');
    if (timeBadge) {
        setInterval(() => {
            timeRemaining--;
            const minutes = Math.floor(timeRemaining / 60);
            const seconds = timeRemaining % 60;
            timeBadge.textContent = `Time remaining ${minutes}:${seconds.toString().padStart(2, '0')}`;
            
            if (timeRemaining <= 0) {
                timeBadge.textContent = 'Time remaining 0:00';
            }
        }, 1000);
    }
}

// initRhasspyButton is now integrated into initUIControls above
