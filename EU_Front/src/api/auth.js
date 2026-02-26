import api from './client';

export const login = async (email, password) => {
    // OAuth2PasswordRequestForm 형식에 맞게 x-www-form-urlencoded 변환하여 전송
    const params = new URLSearchParams();
    params.append('username', email);
    params.append('password', password);

    const response = await api.post('/auth/login', params, {
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
    });
    return response.data;
};

export const register = async (userData) => {
    const response = await api.post('/auth/register', userData);
    return response.data;
};

export const chatWithAI = async (prompt) => {
    const response = await api.post(`/ai/chat?prompt=${encodeURIComponent(prompt)}`);
    return response.data;
};
