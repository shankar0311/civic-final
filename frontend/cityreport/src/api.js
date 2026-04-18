import axios from 'axios';

const configuredBaseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8005';

// If user opens the UI via a LAN IP (not localhost), and VITE_API_URL uses localhost,
// transparently swap it to the current hostname.
const resolvedBaseUrl =
    configuredBaseUrl.includes('localhost') && window.location.hostname !== 'localhost'
        ? configuredBaseUrl.replace('localhost', window.location.hostname)
        : configuredBaseUrl;

export const getApiBaseUrl = () => resolvedBaseUrl.replace(/\/$/, '');

const api = axios.create({
    baseURL: getApiBaseUrl(),
});

export default api;
