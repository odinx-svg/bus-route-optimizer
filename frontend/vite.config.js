import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
    plugins: [react()],
    resolve: {
        alias: {
            '@': path.resolve(__dirname, './src'),
        },
    },
    build: {
        rollupOptions: {
            output: {
                manualChunks(id) {
                    if (!id.includes('node_modules')) return undefined

                    if (id.includes('/react/') || id.includes('/react-dom/')) {
                        return 'react-vendor'
                    }
                    if (id.includes('/leaflet/') || id.includes('/react-leaflet/')) {
                        return 'maps-vendor'
                    }
                    if (id.includes('/@dnd-kit/')) {
                        return 'dnd-vendor'
                    }
                    if (
                        id.includes('/three/')
                        || id.includes('/@react-three/')
                        || id.includes('/react-globe.gl/')
                    ) {
                        return 'three-vendor'
                    }
                    if (id.includes('/recharts/')) {
                        return 'charts-vendor'
                    }
                    if (id.includes('/framer-motion/') || id.includes('/lucide-react/')) {
                        return 'ui-vendor'
                    }
                    if (id.includes('/zustand/') || id.includes('/immer/') || id.includes('/uuid/')) {
                        return 'state-vendor'
                    }

                    return 'vendor'
                },
            },
        },
    },
})
