// src/components/DirectorLayout.jsx
import React from 'react';
import { Outlet } from 'react-router-dom';
import Header from './Header';
import Footer from './Footer';

const DirectorLayout = () => {
    return (
        <div style={{ 
            display: 'flex', 
            flexDirection: 'column', 
            minHeight: '100vh', 
            backgroundColor: '#f4f6f8' 
        }}>
            <Header />
            <main style={{ 
                flex: 1, 
                padding: '20px', 
                maxWidth: '1200px', 
                margin: '0 auto', 
                width: '100%' 
            }}>
                <Outlet />
            </main>

            <Footer />

        </div>
    );
};

export default DirectorLayout;