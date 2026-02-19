/**
 * eidosSpeech v2 — Toast Notification System
 * type: 'success' | 'error' | 'info' | 'warning'
 * Position: top-right fixed, max 3 visible, auto-dismiss
 */

const ToastColors = {
    success: { bg: 'bg-emerald-500/10', border: 'border-emerald-500/30', text: 'text-emerald-400', icon: '✓' },
    error: { bg: 'bg-red-500/10', border: 'border-red-500/30', text: 'text-red-400', icon: '✕' },
    info: { bg: 'bg-blue-500/10', border: 'border-blue-500/30', text: 'text-blue-400', icon: 'ℹ' },
    warning: { bg: 'bg-amber-500/10', border: 'border-amber-500/30', text: 'text-amber-400', icon: '⚠' },
};

let _toastContainer = null;
let _toastQueue = [];

function _getContainer() {
    if (!_toastContainer) {
        _toastContainer = document.createElement('div');
        _toastContainer.id = 'toast-container';
        _toastContainer.className = 'fixed top-4 right-4 z-[9999] flex flex-col gap-2 pointer-events-none';
        _toastContainer.style.cssText = 'max-width: 380px; width: calc(100vw - 2rem);';
        document.body.appendChild(_toastContainer);
    }
    return _toastContainer;
}

function showToast(message, type = 'info', duration = 5000) {
    const container = _getContainer();
    const colors = ToastColors[type] || ToastColors.info;

    // Max 3 toasts
    if (_toastQueue.length >= 3) {
        const oldest = _toastQueue.shift();
        oldest?.remove();
    }

    const toast = document.createElement('div');
    toast.className = [
        'pointer-events-auto flex items-start gap-3 px-4 py-3',
        'rounded-xl border backdrop-blur-sm',
        'shadow-2xl transition-all duration-300',
        colors.bg, colors.border,
        'translate-x-0 opacity-0',
    ].join(' ');
    toast.style.cssText = 'transform: translateX(100%); opacity: 0; transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);';

    toast.innerHTML = `
    <span class="flex-shrink-0 w-5 h-5 flex items-center justify-center rounded-full text-xs font-bold mt-0.5 ${colors.text}">
      ${colors.icon}
    </span>
    <p class="flex-1 text-sm text-gray-200 leading-snug">${message}</p>
    <button onclick="this.closest('[data-toast]').remove()" 
            class="flex-shrink-0 text-gray-500 hover:text-gray-300 text-lg leading-none mt-0.5 transition-colors">
      ×
    </button>
  `;
    toast.setAttribute('data-toast', 'true');

    container.appendChild(toast);
    _toastQueue.push(toast);

    // Animate in
    requestAnimationFrame(() => {
        requestAnimationFrame(() => {
            toast.style.transform = 'translateX(0)';
            toast.style.opacity = '1';
        });
    });

    // Auto-dismiss
    if (duration > 0) {
        setTimeout(() => {
            toast.style.transform = 'translateX(110%)';
            toast.style.opacity = '0';
            setTimeout(() => {
                toast.remove();
                _toastQueue = _toastQueue.filter(t => t !== toast);
            }, 300);
        }, duration);
    }

    return toast;
}

// Export globally
window.showToast = showToast;
