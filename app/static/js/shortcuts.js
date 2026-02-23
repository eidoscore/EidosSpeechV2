/**
 * eidosSpeech v2.1 — Keyboard Shortcuts
 * Global keyboard event handlers
 */

class ShortcutsManager {
    constructor() {
        this.shortcuts = {
            'generate': { key: 'Enter', ctrl: true, description: 'Generate audio' },
            'play': { key: ' ', ctrl: false, description: 'Play/Pause' },
            'download': { key: 's', ctrl: true, description: 'Download MP3' },
            'downloadSrt': { key: 's', ctrl: true, shift: true, description: 'Download SRT' },
            'stop': { key: 'Escape', ctrl: false, description: 'Stop playback' },
        };
        this.enabled = true;
        this.init();
    }

    init() {
        document.addEventListener('keydown', (e) => this.handleKeydown(e));
    }

    handleKeydown(e) {
        if (!this.enabled) return;

        // Don't trigger shortcuts when typing in input/textarea
        const target = e.target;
        const isInput = target.tagName === 'INPUT' || target.tagName === 'TEXTAREA';
        
        // Ctrl+Enter works even in input
        if (e.key === 'Enter' && e.ctrlKey) {
            e.preventDefault();
            this.trigger('generate');
            return;
        }

        // Other shortcuts don't work in input fields
        if (isInput) return;

        // Space for play/pause
        if (e.key === ' ' && !e.ctrlKey && !e.shiftKey) {
            e.preventDefault();
            this.trigger('play');
            return;
        }

        // Ctrl+S for download
        if (e.key === 's' && e.ctrlKey && !e.shiftKey) {
            e.preventDefault();
            this.trigger('download');
            return;
        }

        // Ctrl+Shift+S for SRT download
        if (e.key === 's' && e.ctrlKey && e.shiftKey) {
            e.preventDefault();
            this.trigger('downloadSrt');
            return;
        }

        // Escape to stop
        if (e.key === 'Escape') {
            e.preventDefault();
            this.trigger('stop');
            return;
        }
    }

    trigger(action) {
        const event = new CustomEvent('shortcut', { detail: { action } });
        document.dispatchEvent(event);
    }

    disable() {
        this.enabled = false;
    }

    enable() {
        this.enabled = true;
    }

    getShortcuts() {
        return this.shortcuts;
    }

    formatShortcut(shortcut) {
        let keys = [];
        if (shortcut.ctrl) keys.push('Ctrl');
        if (shortcut.shift) keys.push('Shift');
        keys.push(shortcut.key === ' ' ? 'Space' : shortcut.key);
        return keys.join('+');
    }
}

// Global instance
window.shortcutsManager = new ShortcutsManager();

// Helper to show shortcuts modal
function showShortcutsHelp() {
    const shortcuts = window.shortcutsManager.getShortcuts();
    let html = '<div class="space-y-2">';
    
    for (const [action, shortcut] of Object.entries(shortcuts)) {
        const formatted = window.shortcutsManager.formatShortcut(shortcut);
        html += `
            <div class="flex justify-between items-center py-2 border-b border-gray-700">
                <span class="text-gray-300">${shortcut.description}</span>
                <kbd class="px-2 py-1 bg-gray-700 rounded text-sm font-mono">${formatted}</kbd>
            </div>
        `;
    }
    
    html += '</div>';
    
    // Show in modal (assumes toast.js or similar modal system exists)
    if (window.showModal) {
        window.showModal('Keyboard Shortcuts', html);
    } else {
        alert('Keyboard Shortcuts:\n\n' + 
            Object.entries(shortcuts)
                .map(([_, s]) => `${s.description}: ${window.shortcutsManager.formatShortcut(s)}`)
                .join('\n')
        );
    }
}

window.showShortcutsHelp = showShortcutsHelp;
