// Disable SSR for entire app - this is a client-only application
// CypherTap requires browser APIs (crypto, IndexedDB, WebSocket)
export const ssr = false;

// Enable client-side rendering
export const csr = true;

// Prerender disabled since app requires client-side state
export const prerender = false;
