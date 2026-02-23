/**
 * eidosSpeech v2.1 — Voice Comparison Tool
 * Compare 2-4 voices side-by-side with same text
 */

class VoiceComparer {
    constructor() {
        this.slots = [];
        this.maxSlots = 4;
        this.currentText = '';
        this.isGenerating = false;
    }

    init() {
        // Will be initialized when compare mode is activated
    }

    addSlot(voiceId) {
        if (this.slots.length >= this.maxSlots) {
            showToast('Maximum 4 voices for comparison', 'warning');
            return false;
        }

        this.slots.push({
            id: this.slots.length,
            voice: voiceId,
            audioUrl: null,
            isPlaying: false,
            duration: 0,
        });

        return true;
    }

    removeSlot(slotId) {
        this.slots = this.slots.filter(s => s.id !== slotId);
    }

    async generateAll(text, rate, pitch, volume) {
        if (this.isGenerating) return;
        if (!this.slots.length) {
            showToast('Add at least one voice to compare', 'warning');
            return;
        }

        this.isGenerating = true;
        this.currentText = text;

        const headers = { 'Content-Type': 'application/json' };
        const token = AuthStore.getToken();
        if (token) headers['Authorization'] = `Bearer ${token}`;
        const apiKey = AuthStore.getApiKey();
        if (apiKey) headers['X-API-Key'] = apiKey;

        const formatVal = (v, suffix) => v >= 0 ? `+${v}${suffix}` : `${v}${suffix}`;

        // Generate all voices in parallel
        const promises = this.slots.map(async (slot) => {
            try {
                const resp = await fetch('/api/v1/tts', {
                    method: 'POST',
                    headers,
                    body: JSON.stringify({
                        text,
                        voice: slot.voice,
                        rate: formatVal(rate, '%'),
                        pitch: formatVal(pitch, 'Hz'),
                        volume: formatVal(volume, '%'),
                    }),
                });

                if (!resp.ok) {
                    const err = await resp.json();
                    throw new Error(err.message || 'Generation failed');
                }

                const blob = await resp.blob();
                slot.audioUrl = URL.createObjectURL(blob);

                // Get duration
                const audio = new Audio(slot.audioUrl);
                await new Promise(resolve => {
                    audio.addEventListener('loadedmetadata', () => {
                        slot.duration = audio.duration;
                        resolve();
                    });
                });

                return { success: true, slot };
            } catch (error) {
                return { success: false, slot, error: error.message };
            }
        });

        const results = await Promise.all(promises);

        const failed = results.filter(r => !r.success);
        if (failed.length > 0) {
            showToast(
                `${failed.length} voice(s) failed to generate`,
                'error'
            );
        }

        const succeeded = results.filter(r => r.success);
        if (succeeded.length > 0) {
            showToast(
                `${succeeded.length} voice(s) generated successfully`,
                'success'
            );
        }

        this.isGenerating = false;
        this.render();
    }

    play(slotId) {
        const slot = this.slots.find(s => s.id === slotId);
        if (!slot || !slot.audioUrl) return;

        // Stop all other slots
        this.slots.forEach(s => {
            if (s.id !== slotId && s.isPlaying) {
                this.stop(s.id);
            }
        });

        const audio = document.getElementById(`compare-audio-${slotId}`);
        if (audio) {
            audio.play();
            slot.isPlaying = true;
            this.render();
        }
    }

    pause(slotId) {
        const slot = this.slots.find(s => s.id === slotId);
        if (!slot) return;

        const audio = document.getElementById(`compare-audio-${slotId}`);
        if (audio) {
            audio.pause();
            slot.isPlaying = false;
            this.render();
        }
    }

    stop(slotId) {
        const slot = this.slots.find(s => s.id === slotId);
        if (!slot) return;

        const audio = document.getElementById(`compare-audio-${slotId}`);
        if (audio) {
            audio.pause();
            audio.currentTime = 0;
            slot.isPlaying = false;
            this.render();
        }
    }

    render() {
        // Render comparison UI
        // This will be called by the main app when compare mode is active
        const event = new CustomEvent('compare-render', {
            detail: { slots: this.slots }
        });
        document.dispatchEvent(event);
    }

    clear() {
        this.slots.forEach(slot => {
            if (slot.audioUrl) {
                URL.revokeObjectURL(slot.audioUrl);
            }
        });
        this.slots = [];
        this.currentText = '';
    }
}

// Global instance
window.voiceComparer = new VoiceComparer();
