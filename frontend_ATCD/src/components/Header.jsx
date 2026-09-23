// src/components/Header.jsx
import React, { useState, useEffect, useContext } from 'react';
import { useNavigate } from 'react-router-dom';
import { AuthContext } from '../context/AuthContext';
import ChangePasswordModal from './ChangePasswordModal'; // <-- НОВЫЙ ИМПОРТ
import styles from './Header.module.css';

const Header = () => {
    const { logout, showFirstLoginModal, setShowFirstLoginModal } = useContext(AuthContext); // <-- ОБНОВЛЕНО
    const navigate = useNavigate();
    
    const [userData, setUserData] = useState(null);
    const [activeRole, setActiveRole] = useState('');
    const [isDropdownOpen, setIsDropdownOpen] = useState(false);

    const roleConfig = {
        director: { label: '👔 Директор', path: '/director/dashboard' },
        methodist: { label: '📋 Методист', path: '/methodist' },
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

    // <-- НОВАЯ ФУНКЦИЯ закрытия модалки с очисткой флага
    const handleClosePasswordModal = () => {
        setShowFirstLoginModal(false);
        // Обновляем localStorage, чтобы при рефреше модалка не открылась снова
        const currentData = JSON.parse(localStorage.getItem('userData') || '{}');
        if (currentData.is_first_login) {
            currentData.is_first_login = false;
            localStorage.setItem('userData', JSON.stringify(currentData));
            setUserData(currentData);
        }
    };

    if (!userData) return null;

    const availableRoles = userData.available_roles || [];
    const effectiveRole = activeRole || (availableRoles.length === 1 ? availableRoles[0] : '');
    const currentRoleLabel = roleConfig[effectiveRole]?.label || 'Пользователь';
    const hasMultipleRoles = availableRoles.length > 1;

    return (
        <>
            <header className={styles.header}>
                <div className={styles.container}>
                    <div className={styles.logo}>
                        <img src="/logo-nordstar.png" alt="НордСтар" className={styles.logoImage} />
                        <span className={styles.logoText}>АУЦ</span>
                    </div>

                    <div className={styles.userInfo}>
                        <span className={styles.userName}>{userData.full_name}</span>
                        
                        {hasMultipleRoles ? (
                            <div className={styles.roleSwitcher}>
                                <button className={styles.roleButton} onClick={() => setIsDropdownOpen(!isDropdownOpen)}>
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
                            <span className={styles.singleRoleBadge}>{currentRoleLabel}</span>
                        )}

                        {/* <-- НОВАЯ КНОПКА СМЕНЫ ПАРОЛЯ */}
                        <button 
                            className={styles.passwordBtn} 
                            onClick={() => setShowFirstLoginModal(true)} 
                            title="Сменить пароль"
                        >
                            🔑
                        </button>

                        <button className={styles.logoutButton} onClick={handleLogout}>
                            Выйти
                        </button>
                    </div>
                </div>
            </header>

            {/* <-- РЕНДЕР МОДАЛКИ */}
            <ChangePasswordModal 
                isOpen={showFirstLoginModal} 
                onClose={handleClosePasswordModal} 
                isFirstLogin={userData.is_first_login} 
            />
        </>
    );
};

export default Header;