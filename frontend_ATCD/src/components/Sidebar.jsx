// src/components/Sidebar.jsx
import { Link, useLocation } from 'react-router-dom';
import styles from './Sidebar.module.css';

const Sidebar = () => {
    const location = useLocation();

    const isActive = (path) => {
        if (path === '/') return location.pathname === '/';
        return location.pathname.startsWith(path);
    };

    const menuItems = [
        { path: '/', label: 'Панель управления', icon: '📊' },
        { path: '/create-group', label: 'Создать группу', icon: '⊕' },
        { path: '/groups', label: 'Документы группы', icon: '📄' },
    ];

    return (
        <aside className={styles.sidebar}>
            <nav className={styles.nav}>
                {menuItems.map(item => (
                    <Link
                        key={item.path}
                        to={item.path}
                        className={`${styles.navItem} ${isActive(item.path) ? styles.active : ''}`}
                        title={item.label} // Подсказка при наведении
                    >
                        <span className={styles.icon}>{item.icon}</span>
                        <span className={styles.label}>{item.label}</span>
                    </Link>
                ))}
            </nav>
        </aside>
    );
};

export default Sidebar;