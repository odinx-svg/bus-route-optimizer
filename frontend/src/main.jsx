import React from 'react'
import ReactDOM from 'react-dom/client'
import { Toaster } from 'sileo'

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
            offset={{ top: 72, right: 16 }}
            options={{
                fill: '#0f1b2d',
                roundness: 14,
                duration: 4200,
                autopilot: {
                    expand: 1100,
                    collapse: 3200,
                },
            }}
        />
    </React.StrictMode>,
)
