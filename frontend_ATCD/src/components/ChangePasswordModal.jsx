// src/components/ChangePasswordModal.jsx
import { useState } from 'react';
import styles from './ChangePasswordModal.module.css';

const ChangePasswordModal = ({ isOpen, onClose, isFirstLogin }) => {
    const [oldPassword, setOldPassword] = useState('');
    const [newPassword, setNewPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [error, setError] = useState('');
    const [success, setSuccess] = useState('');
    const [loading, setLoading] = useState(false);

    if (!isOpen) return null;

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setSuccess('');

        if (newPassword.length < 8) {
            setError('Пароль должен содержать минимум 8 символов');
            return;
        }
        if (newPassword !== confirmPassword) {
            setError('Новые пароли не совпадают');
            return;
        }

        setLoading(true);
        const token = localStorage.getItem('accessToken');

        try {
            const response = await fetch(`${import.meta.env.VITE_API_URL}/api/execution/auth/change-password/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({ old_password: oldPassword, new_password: newPassword })
            });

            const data = await response.json();

            if (response.ok) {
                setSuccess('Пароль успешно изменен!');
                setTimeout(() => {
                    onClose(); // Закрываем модалку
                    setOldPassword(''); 
                    setNewPassword(''); 
                    setConfirmPassword('');
                }, 1500);
            } else {
                setError(data.error || 'Ошибка при смене пароля');
            }
        } catch (err) {
            setError('Ошибка сети. Попробуйте позже.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className={styles.overlay} onClick={isFirstLogin ? undefined : onClose}>
            <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
                <h2>🔑 Смена пароля</h2>
                
                {isFirstLogin && (
                    <div className={styles.welcomeBox}>
                        <p>Добро пожаловать в систему!</p>
                        <p>Ваш текущий пароль совпадает с вашим email. Чтобы вам было удобнее входить, мы рекомендуем задать свой собственный пароль.</p>
                        <p className={styles.hint}>Вы можете сделать это прямо сейчас или пропустить этот шаг и вернуться к нему позже через иконку 🔑 в шапке сайта.</p>
                    </div>
                )}

                {error && <div className={styles.error}>{error}</div>}
                {success && <div className={styles.success}>{success}</div>}

                <form onSubmit={handleSubmit}>
                    <div className={styles.field}>
                        <label>Текущий пароль</label>
                        <input 
                            type="password" 
                            value={oldPassword} 
                            onChange={(e) => setOldPassword(e.target.value)} 
                            required 
                            placeholder="Введите текущий пароль"
                        />
                    </div>
                    <div className={styles.field}>
                        <label>Новый пароль (мин. 8 символов)</label>
                        <input 
                            type="password" 
                            value={newPassword} 
                            onChange={(e) => setNewPassword(e.target.value)} 
                            required 
                            minLength="8"
                            placeholder="Придумайте новый пароль"
                        />
                    </div>
                    <div className={styles.field}>
                        <label>Повторите новый пароль</label>
                        <input 
                            type="password" 
                            value={confirmPassword} 
                            onChange={(e) => setConfirmPassword(e.target.value)} 
                            required 
                            placeholder="Повторите пароль"
                        />
                    </div>

                    <div className={styles.actions}>
                        {isFirstLogin && (
                            <button type="button" className={styles.skipBtn} onClick={onClose}>
                                Пропустить
                            </button>
                        )}
                        <button type="submit" className={styles.submitBtn} disabled={loading}>
                            {loading ? 'Сохранение...' : 'Сменить пароль'}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
};

export default ChangePasswordModal;