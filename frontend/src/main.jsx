import React from 'react'
import ReactDOM from 'react-dom/client'
import { Toaster } from 'sonner'

import '@fontsource/inter/400.css'
import '@fontsource/inter/500.css'
import '@fontsource/inter/600.css'
import '@fontsource/inter/700.css'

import App from './App.jsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
    <React.StrictMode>
        <App />
        <Toaster 
            position="top-right"
            toastOptions={{
                style: {
                    background: '#1c1c1f',
                    border: '1px solid rgba(255,255,255,0.06)',
                    color: '#fff',
                },
            }}
            richColors
            closeButton
        />
    </React.StrictMode>,
)
