import axios from 'axios';

const rawApiUrl = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';
const withScheme = /^https?:\/\//i.test(String(rawApiUrl).trim())
    ? String(rawApiUrl).trim()
    : `https://${String(rawApiUrl).trim()}`;
const normalizedBase = withScheme.replace(/\/+$/, '');
const API_URL = normalizedBase.endsWith('/api') ? normalizedBase : `${normalizedBase}/api`;

const api = axios.create({
    baseURL: API_URL,
    headers: {
        'Content-Type': 'application/json',
    },
});

api.interceptors.request.use(
    (config) => {
        const token = localStorage.getItem('token');
        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
    },
    (error) => Promise.reject(error)
);

export default api;
