/**
 * eidosSpeech v2.1 — Voice Favorites Manager
 * localStorage-based favorites system
 */

class FavoritesManager {
    constructor() {
        this.storageKey = 'eidosspeech_favorites';
        this.favorites = this.load();
    }

    load() {
        try {
            const data = localStorage.getItem(this.storageKey);
            return data ? JSON.parse(data) : [];
        } catch (e) {
            console.error('Failed to load favorites:', e);
            return [];
        }
    }

    save() {
        try {
            localStorage.setItem(this.storageKey, JSON.stringify(this.favorites));
        } catch (e) {
            console.error('Failed to save favorites:', e);
        }
    }

    isFavorite(voiceShortName) {
        return this.favorites.includes(voiceShortName);
    }

    toggle(voiceShortName) {
        const index = this.favorites.indexOf(voiceShortName);
        if (index > -1) {
            this.favorites.splice(index, 1);
        } else {
            this.favorites.push(voiceShortName);
        }
        this.save();
        return this.isFavorite(voiceShortName);
    }

    getAll() {
        return [...this.favorites];
    }

    clear() {
        this.favorites = [];
        this.save();
    }
}

// Global instance
window.favoritesManager = new FavoritesManager();
