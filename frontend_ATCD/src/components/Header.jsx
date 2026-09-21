// src/components/Header.jsx
import React, { useState, useEffect, useContext } from 'react';
import { useNavigate } from 'react-router-dom';
import { AuthContext } from '../context/AuthContext';
import styles from './Header.module.css';

const Header = () => {
    const { logout } = useContext(AuthContext);
    const navigate = useNavigate();
    
    const [userData, setUserData] = useState(null);
    const [activeRole, setActiveRole] = useState('');
    const [isDropdownOpen, setIsDropdownOpen] = useState(false);

    // Конфигурация отображения ролей
const roleConfig = {
    director: { label: '👔 Директор', path: '/director/dashboard' },
    methodist: { label: '📋 Методист', path: '/methodist' }, // <-- ИЗМЕНЕНО
    instructor: { label: '‍🏫 Инструктор', path: '/instructor/dashboard' },
    student: { label: '🎓 Слушатель', path: '/student/dashboard' }
};

    useEffect(() => {
        const updateUserData = () => {
            const savedUser = localStorage.getItem('userData');
            const currentRole = localStorage.getItem('activeRole') || '';
            
            if (savedUser) {
                const parsedUser = JSON.parse(savedUser);
                setUserData(parsedUser);
                setActiveRole(currentRole);
            }
        };

        updateUserData();
        window.addEventListener('storage', updateUserData);
        
        return () => window.removeEventListener('storage', updateUserData);
    }, []);

    const handleRoleSwitch = (role) => {
        localStorage.setItem('activeRole', role);
        setActiveRole(role);
        setIsDropdownOpen(false);
        
        const targetPath = roleConfig[role]?.path || '/';
        navigate(targetPath);
    };

    const handleLogout = () => {
        logout();
        navigate('/login');
    };

    if (!userData) return null;

    const availableRoles = userData.available_roles || [];
    // Если activeRole не установлен, но есть только одна доступная роль — используем её
    const effectiveRole = activeRole || (availableRoles.length === 1 ? availableRoles[0] : '');
    const currentRoleLabel = roleConfig[effectiveRole]?.label || 'Пользователь';
    const hasMultipleRoles = availableRoles.length > 1;

    return (
        <header className={styles.header}>
            <div className={styles.container}>
                <div className={styles.logo}>
                    <img 
                        src="/logo-nordstar.png" 
                        alt="НордСтар" 
                        className={styles.logoImage}
                    />
                    <span className={styles.logoText}>АУЦ</span>
                </div>

                <div className={styles.userInfo}>
                    <span className={styles.userName}>{userData.full_name}</span>
                    
                    {hasMultipleRoles ? (
                        <div className={styles.roleSwitcher}>
                            <button 
                                className={styles.roleButton}
                                onClick={() => setIsDropdownOpen(!isDropdownOpen)}
                            >
                                {currentRoleLabel} <span className={styles.arrow}>▼</span>
                            </button>
                            
                            {isDropdownOpen && (
                                <div className={styles.dropdownMenu}>
                                    {availableRoles.map(role => (
                                        <button
                                            key={role}
                                            className={`${styles.dropdownItem} ${activeRole === role ? styles.active : ''}`}
                                            onClick={() => handleRoleSwitch(role)}
                                        >
                                            {roleConfig[role].label}
                                        </button>
                                    ))}
                                </div>
                            )}
                        </div>
                    ) : (
                        <span className={styles.singleRoleBadge}>
                            {currentRoleLabel}
                        </span>
                    )}

                    <button className={styles.logoutButton} onClick={handleLogout}>
                        Выйти
                    </button>
                </div>
            </div>
        </header>
    );
};

export default Header;