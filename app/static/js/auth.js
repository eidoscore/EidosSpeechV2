/**
 * eidosSpeech v2 — Auth State Manager
 * Manages authentication state in localStorage.
 * Contek eidosStack pattern: UNAUTHENTICATED | AUTHENTICATED | SESSION_EXPIRED
 */

const AuthStore = {
    _state: 'UNAUTHENTICATED',
    _token: null,
    _refreshToken: null,
    _user: null,
    _apiKey: null,
    _refreshTimer: null,

    /** Initialize from localStorage on page load */
    async init() {
        const stored = localStorage.getItem('eidosspeech_auth');
        if (stored) {
            try {
                const data = JSON.parse(stored);
                this._state = data._state || 'UNAUTHENTICATED';
                this._token = data._token || null;
                this._refreshToken = data._refreshToken || null;
                this._user = data._user || null;
                this._apiKey = data._apiKey || null;
            } catch (e) {
                this.clearAuth();
                return;
            }
        }

        if (this._state === 'AUTHENTICATED' && this._token) {
            await this._evaluateSession();
        }

        // Start periodic session check (every 60 seconds)
        this._refreshTimer = setInterval(() => this._evaluateSession(), 60000);

        // Update UI based on auth state
        this._notifyListeners();
    },

    setAuth(token, refreshToken, user, apiKey) {
        this._state = 'AUTHENTICATED';
        this._token = token;
        this._refreshToken = refreshToken;
        this._user = user || null;
        this._apiKey = apiKey || null;
        this._persist();
        this._notifyListeners();
    },

    clearAuth() {
        this._state = 'UNAUTHENTICATED';
        this._token = null;
        this._refreshToken = null;
        this._user = null;
        this._apiKey = null;
        localStorage.removeItem('eidosspeech_auth');
        this._notifyListeners();
    },

    getToken() { return this._token; },
    getRefreshToken() { return this._refreshToken; },
    getUser() { return this._user; },
    getApiKey() { return this._apiKey; },
    isAuthenticated() { return this._state === 'AUTHENTICATED' && !!this._token; },

    updateUser(userData) {
        if (userData) {
            this._user = { ...(this._user || {}), ...userData };
            if (userData.api_key) this._apiKey = userData.api_key;
            this._persist();
            this._notifyListeners();
        }
    },

    _persist() {
        localStorage.setItem('eidosspeech_auth', JSON.stringify({
            _state: this._state,
            _token: this._token,
            _refreshToken: this._refreshToken,
            _user: this._user,
            _apiKey: this._apiKey,
        }));
    },

    async _evaluateSession() {
        if (!this._token) return;

        // Check token expiry
        try {
            const parts = this._token.split('.');
            if (parts.length !== 3) { this.clearAuth(); return; }
            const payload = JSON.parse(atob(parts[1]));
            const exp = payload.exp * 1000;
            const now = Date.now();

            // Token expired or expiring in < 60s → try refresh
            if (now >= exp - 60000) {
                const refreshed = await this._doRefresh();
                if (!refreshed) {
                    this._state = 'SESSION_EXPIRED';
                    this._persist();
                    this._notifyListeners();
                }
            }
        } catch (e) {
            this.clearAuth();
        }
    },

    async _doRefresh() {
        if (!this._refreshToken) return false;
        try {
            const resp = await fetch('/api/v1/auth/refresh', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ refresh_token: this._refreshToken }),
            });
            if (!resp.ok) return false;
            const data = await resp.json();
            this._token = data.access_token;
            this._refreshToken = data.refresh_token;
            this._state = 'AUTHENTICATED';
            this._persist();
            return true;
        } catch (e) {
            return false;
        }
    },

    // Listener system for UI updates
    _listeners: [],

    subscribe(fn) {
        this._listeners.push(fn);
        return () => { this._listeners = this._listeners.filter(l => l !== fn); };
    },

    _notifyListeners() {
        this._listeners.forEach(fn => fn(this._state, this._user, this._apiKey));
    },
};

window.AuthStore = AuthStore;
