// src/context/AuthContext.jsx
import { createContext, useState, useEffect } from 'react';
import api from '../api/config';

export const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);
    const [showFirstLoginModal, setShowFirstLoginModal] = useState(false); // <-- НОВОЕ

    useEffect(() => {
        const token = localStorage.getItem('accessToken');
        const savedUser = localStorage.getItem('userData');
        
        if (token && savedUser) {
            setUser(JSON.parse(savedUser));
        }
        setLoading(false);
    }, []);

    const login = async (username, password) => {
        try {
            const res = await api.post('/api/token/', { username, password });
            localStorage.setItem('accessToken', res.data.access);
            localStorage.setItem('refreshToken', res.data.refresh);
            
            const userRes = await api.get('/api/docs/me/roles/'); 
            const userData = userRes.data;
            
            localStorage.setItem('userData', JSON.stringify(userData));
            setUser(userData);
            
            // <-- НОВОЕ: Если это первый вход, открываем модалку
            if (userData.is_first_login) {
                setShowFirstLoginModal(true);
            }
            
            return true;
        } catch (err) {
            console.error('Ошибка входа:', err);
            return false;
        }
    };

    const logout = () => {
        localStorage.removeItem('accessToken');
        localStorage.removeItem('refreshToken');
        localStorage.removeItem('userData');
        localStorage.removeItem('activeRole');
        setUser(null);
        setShowFirstLoginModal(false); // <-- НОВОЕ
    };

    return (
        <AuthContext.Provider value={{ 
            user, 
            login, 
            logout, 
            loading, 
            showFirstLoginModal,       // <-- НОВОЕ
            setShowFirstLoginModal     // <-- НОВОЕ
        }}>
            {children}
        </AuthContext.Provider>
    );
};