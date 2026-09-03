import { useContext } from 'react';
import { AuthContext } from '../context/AuthContext';
import styles from './Header.module.css';

const Header = () => {
    const { user, logout } = useContext(AuthContext);

    return (
        <header className={styles.header}>
            <div className={styles.logo}>АУЦ НордСтар | ATCD</div>
            <div>
                {/* Показываем full_name, если его нет - показываем username */}
                <span style={{ marginRight: 15 }}>
                    Привет, {user?.full_name || user?.username}!
                </span>
                <button className={styles.logoutBtn} onClick={logout}>
                    Выйти
                </button>
            </div>
        </header>
    );
};

export default Header;