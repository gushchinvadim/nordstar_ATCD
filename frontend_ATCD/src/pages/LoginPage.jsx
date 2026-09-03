import { useState, useContext } from 'react';
import { useNavigate } from 'react-router-dom';
import { AuthContext } from '../context/AuthContext';
import styles from './LoginPage.module.css';

const LoginPage = () => {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    
    const { login } = useContext(AuthContext);
    const navigate = useNavigate();

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        
        const success = await login(username, password);
        if (success) {
            navigate('/'); // Редирект на главную после успешного входа
        } else {
            setError('Неверный логин или пароль');
        }
    };

    return (
        <div className={styles.container}>
            <form className={styles.form} onSubmit={handleSubmit}>
                <h2 style={{ textAlign: 'center', marginBottom: 20 }}>Вход в систему</h2>
                
                {error && <div className={styles.error}>{error}</div>}

                <input
                    type="text"
                    placeholder="Логин"
                    className={styles.input}
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    required
                />
                <input
                    type="password"
                    placeholder="Пароль"
                    className={styles.input}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                />
                
                <button type="submit" className={styles.btn}>Войти</button>
            </form>
        </div>
    );
};

export default LoginPage;