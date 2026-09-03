import axios from 'axios';

const api = axios.create({
    baseURL: import.meta.env.VITE_API_URL,
    headers: {
        'Content-Type': 'application/json',
    },
});

// Перехватчик запросов: добавляем токен
api.interceptors.request.use((config) => {
    const token = localStorage.getItem('accessToken');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

// Перехватчик ответов: если 401 — пытаемся обновить токен
api.interceptors.response.use(
    (response) => response,
    async (error) => {
        const originalRequest = error.config;
        
        // Если ошибка 401 и это не повторный запрос
        if (error.response?.status === 401 && !originalRequest._retry) {
            originalRequest._retry = true;
            
            const refreshToken = localStorage.getItem('refreshToken');
            if (refreshToken) {
                try {
                    // Пытаемся получить новый access token
                    const response = await axios.post(
                        `${import.meta.env.VITE_API_URL}/api/token/refresh/`,
                        { refresh: refreshToken }
                    );
                    
                    const newAccessToken = response.data.access;
                    localStorage.setItem('accessToken', newAccessToken);
                    
                    // Повторяем оригинальный запрос с новым токеном
                    originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
                    return api(originalRequest);
                } catch (refreshError) {
                    // Если refresh не удался — выходим из системы
                    localStorage.removeItem('accessToken');
                    localStorage.removeItem('refreshToken');
                    localStorage.removeItem('userData');
                    window.location.href = '/login';
                    return Promise.reject(refreshError);
                }
            }
        }
        
        return Promise.reject(error);
    }
);

export default api;