import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
    plugins: [react()],
    base: './',
    server: {
        port: 5173,
    },
    optimizeDeps: {
        include: ['react', 'react-dom', 'socket.io-client'],
        exclude: ['@mediapipe/tasks-vision']
    },
    build: {
        sourcemap: false,
        rollupOptions: {
            output: {
                manualChunks: {
                    'react-vendor': ['react', 'react-dom'],
                    'mediapipe': ['@mediapipe/tasks-vision']
                }
            }
        }
    },
    // Fixed customLogger with all required functions
    customLogger: {
        info: (msg) => {
            if (msg && msg.includes('.map')) return;
            console.log(msg);
        },
        warn: (msg) => {
            if (msg && msg.includes('.map')) return;
            console.warn(msg);
        },
        error: (msg) => {
            if (msg && msg.includes('.map')) return;
            console.error(msg);
        }
    }
})