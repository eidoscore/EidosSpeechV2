/**
 * eidosSpeech v2 — API Client
 * HTTP client with auto-attach auth header + auto-refresh on 401.
 * Contek eidosStack ApiClient pattern.
 */

const ApiClient = {
    async request(method, path, body = null, options = {}) {
        const headers = { 'Content-Type': 'application/json' };

        // Attach auth header if authenticated
        const token = AuthStore.getToken();
        if (token) headers['Authorization'] = `Bearer ${token}`;

        // Attach API key if available (for X-API-Key usage)
        const apiKey = AuthStore.getApiKey();
        if (apiKey && options.useApiKey) headers['X-API-Key'] = apiKey;

        const fetchOpts = {
            method,
            headers,
            body: body ? JSON.stringify(body) : null,
        };

        let response = await fetch(`/api/v1${path}`, fetchOpts);

        // Auto-refresh on 401 (not for auth endpoints themselves)
        if (response.status === 401 && token && !path.startsWith('/auth/')) {
            // Try to refresh token
            const refreshToken = AuthStore.getRefreshToken();
            if (refreshToken) {
                try {
                    const refreshResp = await fetch('/api/v1/auth/refresh', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ refresh_token: refreshToken }),
                    });

                    if (refreshResp.ok) {
                        const data = await refreshResp.json();
                        AuthStore.setAuth(
                            data.access_token,
                            data.refresh_token,
                            AuthStore.getUser(),
                            AuthStore.getApiKey(),
                        );
                        // Retry original request with new token
                        headers['Authorization'] = `Bearer ${data.access_token}`;
                        response = await fetch(`/api/v1${path}`, { ...fetchOpts, headers });
                    } else {
                        // Refresh failed — clear auth
                        AuthStore.clearAuth();
                        if (typeof showToast === 'function') {
                            showToast('Session expired. Please log in again.', 'error');
                        }
                        setTimeout(() => { window.location.hash = '#login'; }, 1000);
                    }
                } catch (e) {
                    AuthStore.clearAuth();
                }
            }
        }

        return response;
    },

    // Convenience methods
    get: (path, opts = {}) => ApiClient.request('GET', path, null, opts),
    post: (path, body, opts = {}) => ApiClient.request('POST', path, body, opts),

    // Parse JSON response + handle errors
    async json(method, path, body = null) {
        const resp = await ApiClient.request(method, path, body);
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({ message: resp.statusText }));
            throw { status: resp.status, ...err };
        }
        return resp.json();
    },

    getJson: (path) => ApiClient.json('GET', path),
    postJson: (path, body) => ApiClient.json('POST', path, body),

    // Auth-specific methods
    auth: {
        async register(email, password, fullName, tosAccepted, turnstileToken) {
            return ApiClient.postJson('/auth/register', {
                email,
                password,
                full_name: fullName,
                tos_accepted: tosAccepted,
                turnstile_token: turnstileToken || undefined
            });
        },
        async login(email, password, turnstileToken) {
            const data = await ApiClient.postJson('/auth/login', { email, password, turnstile_token: turnstileToken || undefined });
            if (data.access_token) {
                AuthStore.setAuth(data.access_token, data.refresh_token, data.user, data.user?.api_key);
            }
            return data;
        },
        async logout() {
            try {
                await ApiClient.post('/auth/logout');
            } finally {
                AuthStore.clearAuth();
            }
        },
        async me() {
            const data = await ApiClient.getJson('/auth/me');
            if (data.user) AuthStore.updateUser(data.user);
            return data;
        },
        async verifyEmail(token) {
            const data = await ApiClient.postJson('/auth/verify-email', { token });
            if (data.access_token) {
                AuthStore.setAuth(data.access_token, data.refresh_token, data.user, data.user?.api_key);
            }
            return data;
        },
        async forgotPassword(email) {
            return ApiClient.postJson('/auth/forgot-password', { email });
        },
        async resetPassword(token, newPassword) {
            return ApiClient.postJson('/auth/reset-password', { token, new_password: newPassword });
        },
        async resendVerification(email) {
            return ApiClient.postJson('/auth/resend-verification', { email });
        },
        async regenKey() {
            return ApiClient.postJson('/auth/regen-key', {});
        },
    },
};

window.ApiClient = ApiClient;
