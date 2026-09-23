// src/pages/LoginPage.jsx
import { useState, useContext } from 'react';
import { useNavigate } from 'react-router-dom';
import { AuthContext } from '../context/AuthContext';
import RoleSelector from '../components/RoleSelector';
import styles from './LoginPage.module.css';

const LoginPage = () => {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [showRoleSelector, setShowRoleSelector] = useState(false);
    const [userData, setUserData] = useState(null);
    
    const { login, logout } = useContext(AuthContext);
    const navigate = useNavigate();

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        
        const success = await login(username, password);
        if (success) {
            const data = JSON.parse(localStorage.getItem('userData') || '{}');
            // console.log('🔍 DEBUG userData:', data);
            setUserData(data);
            
            const roles = data.available_roles || [];

            if (roles.length === 1) {
                // АВТОМАТИЧЕСКИЙ ВХОД, если роль всего одна
                const role = roles[0];
                
                // Сохраняем активную роль
                localStorage.setItem('activeRole', role);

                // Перенаправляем на правильный дашборд
                if (role === 'director') navigate('/director/dashboard', { replace: true });
                else if (role === 'methodist') navigate('/methodist', { replace: true }); // <-- ИСПРАВЛЕНО
                else if (role === 'instructor') navigate('/instructor/dashboard', { replace: true });
                else if (role === 'student') navigate('/student/dashboard', { replace: true });
                else navigate('/methodist', { replace: true }); // Запасной вариант для staff
            } else if (roles.length > 1) {
                // ПОКАЗЫВАЕМ ЭКРАН ВЫБОРА, если ролей несколько
                setShowRoleSelector(true);
            } else {
                setError('У вашей учетной записи нет доступа к внутренним разделам системы.');
            }
        } else {
            setError('Неверный логин или пароль');
        }
    };

    const handleRoleSelect = (role) => {
        // Сохраняем выбранную роль в localStorage
        localStorage.setItem('activeRole', role);
        
        // Перенаправляем на выбранный дашборд
        if (role === 'director') navigate('/director/dashboard', { replace: true });
        else if (role === 'methodist') navigate('/methodist', { replace: true }); // <-- ИСПРАВЛЕНО
        else if (role === 'instructor') navigate('/instructor/dashboard', { replace: true });
        else if (role === 'student') navigate('/student/dashboard', { replace: true });
    };

    const handleLogout = () => {
        logout();
        setShowRoleSelector(false);
        setUserData(null);
    };

    // Если выбран режим выбора роли, рендерим RoleSelector вместо формы входа
    if (showRoleSelector && userData) {
        return (
            <RoleSelector 
                userData={userData} 
                onSelectRole={handleRoleSelect} 
                onLogout={handleLogout} 
            />
        );
    }

    // Иначе показываем обычную форму входа
    return (
        <div className={styles.container}>
            <form className={styles.form} onSubmit={handleSubmit}>
                <h2 style={{ textAlign: 'center', marginBottom: 20 }}>Вход в систему АУЦ</h2>
                
                {error && <div className={styles.error}>{error}</div>}

                <input
                    type="text"
                    placeholder="Логин"
                    className={styles.input}
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    required
                    autoComplete="username"
                />
                <input
                    type="password"
                    placeholder="Пароль"
                    className={styles.input}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    autoComplete="current-password"
                />
                
                <button type="submit" className={styles.btn}>
                    Войти
                </button>
            </form>
        </div>
    );
};

export default LoginPage;