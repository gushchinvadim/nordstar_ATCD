// src/components/RoleSelector.jsx
import React from 'react';
import styles from './RoleSelector.module.css';

const RoleSelector = ({ userData, onSelectRole, onLogout }) => {
    // Конфигурация внешнего вида для каждой роли
    const roleConfig = {
        director: { 
            title: 'Директор / Зам. директора', 
            icon: '👔', 
            desc: 'Утверждение расписаний, контроль учебного процесса, статистика' 
        },
        methodist: { 
            title: 'Методист', 
            icon: '📋', 
            desc: 'Создание групп, управление расписанием, генерация документов и отчетов' 
        },
        instructor: { 
            title: 'Инструктор / Преподаватель', 
            icon: '👨‍🏫', 
            desc: 'Просмотр своего расписания, подтверждение занятий, выставление оценок' 
        },
        student: { 
            title: 'Слушатель', 
            icon: '🎓', 
            desc: 'Просмотр расписания, подтверждение посещаемости и ознакомление с документами' 
        }
    };

    return (
        <div className={styles.container}>
            <div className={styles.card}>
                <h2 className={styles.title}>Добро пожаловать, {userData.full_name}!</h2>
                <p className={styles.subtitle}>Выберите режим работы для входа в систему:</p>
                
                <div className={styles.rolesGrid}>
                    {userData.available_roles.map(role => (
                        <div 
                            key={role} 
                            className={styles.roleCard}
                            onClick={() => onSelectRole(role)}
                        >
                            <div className={styles.roleIcon}>{roleConfig[role].icon}</div>
                            <h3 className={styles.roleTitle}>{roleConfig[role].title}</h3>
                            <p className={styles.roleDesc}>{roleConfig[role].desc}</p>
                            <button className={styles.selectButton}>Войти</button>
                        </div>
                    ))}
                </div>

                <button className={styles.logoutButton} onClick={onLogout}>
                    Выйти из системы
                </button>
            </div>
        </div>
    );
};

export default RoleSelector;