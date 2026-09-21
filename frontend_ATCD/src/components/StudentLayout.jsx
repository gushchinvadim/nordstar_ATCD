// src/components/StudentLayout.jsx
import React from 'react';
import { Outlet } from 'react-router-dom';
import Header from './Header';
import Footer from './Footer';

const StudentLayout = () => {
    return (
        <div style={{ 
            display: 'flex', 
            flexDirection: 'column', 
            minHeight: '100vh', 
            backgroundColor: '#f4f6f8' 
        }}>
            {/* Шапка с именем пользователя и кнопкой выхода */}
            <Header />
            
            {/* Основной контент страницы студента */}
            <main style={{ 
                flex: 1, 
                padding: '20px', 
                maxWidth: '800px', 
                margin: '0 auto', 
                width: '100%' 
            }}>
                <Outlet />
            </main>
            
            {/* Простой подвал */}
            <Footer />
            {/* <footer style={{ 
                textAlign: 'center', 
                padding: '15px', 
                backgroundColor: '#ffffff', 
                borderTop: '1px solid #e0e0e0', 
                color: '#666',
                fontSize: '0.9rem'
            }}>
                © {new Date().getFullYear()} АУЦ НордСтар | Личный кабинет слушателя
            </footer> */}
        </div>
    );
};

export default StudentLayout;