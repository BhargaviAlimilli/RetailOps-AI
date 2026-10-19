import { StrictMode } from 'react'
import { Provider } from 'react-redux'
import { store } from './store'
import { createRoot } from 'react-dom/client'
import { QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router'
import { App } from './app/App'
import { createQueryClient } from './app/queryClient'
import './styles.css'

const root = document.getElementById('root')
if (!root) throw new Error('Application root is missing')

createRoot(root).render(
  <StrictMode>
    <Provider store={store}>
      <QueryClientProvider client={createQueryClient()}>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </QueryClientProvider>
    </Provider>
  </StrictMode>,
)
