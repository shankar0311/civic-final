import axios from 'axios';

const configuredBaseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8005';

const resolvedBaseUrl =
    configuredBaseUrl.includes('localhost') && window.location.hostname !== 'localhost'
        ? configuredBaseUrl.replace('localhost', window.location.hostname)
        : configuredBaseUrl;

export const getApiBaseUrl = () => resolvedBaseUrl.replace(/\/$/, '');

const api = axios.create({
    baseURL: getApiBaseUrl(),
});

// Always attach the latest token from localStorage on every request
api.interceptors.request.use((config) => {
    const token = localStorage.getItem('token');
    if (token) {
        config.headers['Authorization'] = `Bearer ${token}`;
    }
    return config;
});

export default api;
