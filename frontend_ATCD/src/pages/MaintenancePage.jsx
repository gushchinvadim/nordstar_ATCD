// src/pages/MaintenancePage.jsx
import React from 'react';

const MaintenancePage = () => {
    return (
        <div style={styles.container}>
            <div style={styles.card}>
                <div style={styles.icon}>🛠️</div>
                <h1 style={styles.title}>Ведутся регламентные работы</h1>
                <p style={styles.text}>
                    Уважаемые коллеги! В настоящее время проводятся технические работы по обновлению системы ATCD.
                </p>
                <p style={styles.text}>
                    Пожалуйста, попробуйте зайти позже. Приносим извинения за временные неудобства.
                </p>
                <div style={styles.footer}>
                    <p style={styles.contact}>
                        По срочным вопросам обращайтесь к администратору системы.
                    </p>
                </div>
            </div>
        </div>
    );
};

const styles = {
    container: {
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: '#f4f6f8',
        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
        padding: '20px',
    },
    card: {
        backgroundColor: '#ffffff',
        borderRadius: '12px',
        boxShadow: '0 8px 24px rgba(0, 0, 0, 0.1)',
        padding: '40px',
        maxWidth: '500px',
        width: '100%',
        textAlign: 'center',
        border: '1px solid #e0e0e0',
    },
    icon: { fontSize: '64px', marginBottom: '20px' },
    title: { fontSize: '24px', fontWeight: '700', color: '#1a1a1a', margin: '0 0 16px 0' },
    text: { fontSize: '16px', color: '#555555', lineHeight: '1.6', marginBottom: '12px' },
    footer: { marginTop: '32px', paddingTop: '24px', borderTop: '1px solid #eeeeee' },
    contact: { fontSize: '14px', color: '#888888', margin: 0 },
};

export default MaintenancePage;