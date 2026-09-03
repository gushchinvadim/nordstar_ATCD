import { createContext, useState, useEffect } from 'react';
import api from '../api/config';

export const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        // При загрузке проверяем, есть ли сохраненный пользователь и токен
        const token = localStorage.getItem('accessToken');
        const savedUser = localStorage.getItem('userData');
        
        if (token && savedUser) {
            setUser(JSON.parse(savedUser));
        }
        setLoading(false);
    }, []);

    const login = async (username, password) => {
        try {
            // 1. Получаем токены
            const res = await api.post('/api/token/', { username, password });
            localStorage.setItem('accessToken', res.data.access);
            localStorage.setItem('refreshToken', res.data.refresh);
            
            // 2. Запрашиваем данные пользователя по новому эндпоинту
            const userRes = await api.get('/docs/api/me/');
            const userData = userRes.data;
            
            // 3. Сохраняем данные пользователя в localStorage и стейт
            localStorage.setItem('userData', JSON.stringify(userData));
            setUser(userData);
            
            return true;
        } catch (err) {
            console.error('Ошибка входа:', err);
            return false;
        }
    };

    const logout = () => {
        localStorage.removeItem('accessToken');
        localStorage.removeItem('refreshToken');
        localStorage.removeItem('userData'); // <-- Очищаем данные пользователя
        setUser(null);
    };

    return (
        <AuthContext.Provider value={{ user, login, logout, loading }}>
            {children}
        </AuthContext.Provider>
    );
};