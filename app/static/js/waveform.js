/**
 * eidosSpeech v2.1 — Audio Waveform Visualizer
 * Web Audio API canvas-based waveform with progress overlay
 */

class WaveformVisualizer {
    constructor(canvasId, audioElement) {
        this.canvas = document.getElementById(canvasId);
        this.audio = audioElement;
        this.ctx = this.canvas.getContext('2d');
        this.audioContext = null;
        this.audioBuffer = null;
        this.animationId = null;
        this.isPlaying = false;
        
        // Colors
        this.playedColor = '#10b981'; // emerald-500
        this.unplayedColor = '#1f2937'; // gray-800
        this.backgroundColor = '#050a06';
        
        this.init();
    }

    init() {
        // Set canvas size
        this.resizeCanvas();
        window.addEventListener('resize', () => this.resizeCanvas());
        
        // Audio event listeners
        this.audio.addEventListener('play', () => {
            this.isPlaying = true;
            this.startAnimation();
        });
        
        this.audio.addEventListener('pause', () => {
            this.isPlaying = false;
            this.stopAnimation();
        });
        
        this.audio.addEventListener('ended', () => {
            this.isPlaying = false;
            this.stopAnimation();
            this.draw();
        });
        
        // Click to seek
        this.canvas.addEventListener('click', (e) => this.handleClick(e));
    }

    resizeCanvas() {
        const rect = this.canvas.getBoundingClientRect();
        this.canvas.width = rect.width * window.devicePixelRatio;
        this.canvas.height = rect.height * window.devicePixelRatio;
        this.ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
        this.draw();
    }

    async loadAudio(audioUrl) {
        try {
            // Initialize AudioContext on first use
            if (!this.audioContext) {
                this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            }

            // Fetch and decode audio
            const response = await fetch(audioUrl);
            const arrayBuffer = await response.arrayBuffer();
            this.audioBuffer = await this.audioContext.decodeAudioData(arrayBuffer);
            
            this.draw();
        } catch (error) {
            console.error('Failed to load audio for waveform:', error);
            this.drawFallback();
        }
    }

    draw() {
        if (!this.audioBuffer) {
            this.drawFallback();
            return;
        }

        const width = this.canvas.width / window.devicePixelRatio;
        const height = this.canvas.height / window.devicePixelRatio;
        
        // Clear canvas
        this.ctx.fillStyle = this.backgroundColor;
        this.ctx.fillRect(0, 0, width, height);

        // Get audio data
        const data = this.audioBuffer.getChannelData(0);
        const step = Math.ceil(data.length / width);
        const amp = height / 2;
        
        // Calculate progress
        const progress = this.audio.duration > 0 ? this.audio.currentTime / this.audio.duration : 0;
        const progressX = width * progress;

        // Draw waveform bars
        const barWidth = Math.max(1, width / 100);
        const barGap = 1;
        
        for (let i = 0; i < width; i += barWidth + barGap) {
            let min = 1.0;
            let max = -1.0;
            
            for (let j = 0; j < step; j++) {
                const datum = data[(i * step) + j];
                if (datum < min) min = datum;
                if (datum > max) max = datum;
            }
            
            const barHeight = Math.max(2, (max - min) * amp);
            const x = i;
            const y = (height - barHeight) / 2;
            
            // Color based on progress
            this.ctx.fillStyle = x < progressX ? this.playedColor : this.unplayedColor;
            this.ctx.fillRect(x, y, barWidth, barHeight);
        }
    }

    drawFallback() {
        // Simple progress bar fallback
        const width = this.canvas.width / window.devicePixelRatio;
        const height = this.canvas.height / window.devicePixelRatio;
        
        this.ctx.fillStyle = this.backgroundColor;
        this.ctx.fillRect(0, 0, width, height);
        
        const progress = this.audio.duration > 0 ? this.audio.currentTime / this.audio.duration : 0;
        const progressWidth = width * progress;
        
        // Draw progress bar
        this.ctx.fillStyle = this.unplayedColor;
        this.ctx.fillRect(0, height / 2 - 2, width, 4);
        
        this.ctx.fillStyle = this.playedColor;
        this.ctx.fillRect(0, height / 2 - 2, progressWidth, 4);
    }

    startAnimation() {
        const animate = () => {
            this.draw();
            if (this.isPlaying) {
                this.animationId = requestAnimationFrame(animate);
            }
        };
        animate();
    }

    stopAnimation() {
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
            this.animationId = null;
        }
    }

    handleClick(e) {
        if (!this.audio.duration) return;
        
        const rect = this.canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const progress = x / rect.width;
        
        this.audio.currentTime = progress * this.audio.duration;
        this.draw();
    }

    clear() {
        this.audioBuffer = null;
        this.stopAnimation();
        
        const width = this.canvas.width / window.devicePixelRatio;
        const height = this.canvas.height / window.devicePixelRatio;
        
        this.ctx.fillStyle = this.backgroundColor;
        this.ctx.fillRect(0, 0, width, height);
    }

    destroy() {
        this.stopAnimation();
        if (this.audioContext) {
            this.audioContext.close();
        }
    }
}

// Export for global use
window.WaveformVisualizer = WaveformVisualizer;
