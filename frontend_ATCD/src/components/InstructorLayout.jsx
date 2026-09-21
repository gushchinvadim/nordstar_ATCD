// src/components/InstructorLayout.jsx
import React from 'react';
import { Outlet } from 'react-router-dom'; // <-- ВАЖНО: Импортируем Outlet
import Header from './Header';
import Footer from './Footer';

const InstructorLayout = () => {
    return (
        <div style={{ 
            display: 'flex', 
            flexDirection: 'column', 
            minHeight: '100vh', 
            backgroundColor: '#f4f6f8' 
        }}>
            {/* Шапка с именем и кнопкой выхода */}
            <Header />
            
            {/* Основной контент */}
            <main style={{ 
                flex: 1, 
                padding: '20px', 
                maxWidth: '1200px', 
                margin: '0 auto', 
                width: '100%' 
            }}>
                {/* ВАЖНО: Outlet рендерит текущую страницу (Dashboard или Grades) */}
                <Outlet /> 
            </main>
            
            {/* Подвал */}
            <Footer />

        </div>
    );
};

export default InstructorLayout;