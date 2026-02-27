import axios from 'axios';

const rawApiUrl = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';
const trimmedRaw = String(rawApiUrl).trim();
const noScheme = trimmedRaw.replace(/^https?:\/\//i, '');
const hostOnly = noScheme.split('/')[0];
const needsRenderDomain = hostOnly && !hostOnly.includes('.') && !hostOnly.includes(':') && hostOnly !== 'localhost';
const normalizedInput = needsRenderDomain
    ? noScheme.replace(hostOnly, `${hostOnly}.onrender.com`)
    : noScheme;
const schemeMatch = trimmedRaw.match(/^(https?):\/\//i);
const scheme = schemeMatch ? schemeMatch[1].toLowerCase() : 'https';
const withScheme = `${scheme}://${normalizedInput}`;
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
