// src/components/Sidebar.jsx
import { Link, useLocation } from 'react-router-dom';
import styles from './Sidebar.module.css';

const Sidebar = ({ items }) => {
    const location = useLocation();

    const isActive = (path) => {
        if (path === '/') return location.pathname === '/';
        return location.pathname.startsWith(path);
    };

    const menuItems = items || [
        // { path: '/methodist', label: 'Панель управления', icon: '📊' },
        { path: '/groups', label: 'Документы группы', icon: '📄' },
        { path: '/create-group', label: 'Создать группу', icon: '⊕' },
        { path: '/create-student', label: 'Создать слушателя', icon: '👤' },
        { path: '/edit-student', label: 'Редактировать слушателя', icon: '✎' },
        { path: '/instructors', label: 'Преподаватели', icon: '♙' },
    ];

    return (
        <aside className={styles.sidebar}>
            <nav className={styles.nav}>
                {menuItems.map(item => (
                    <Link
                        key={item.path}
                        to={item.path}
                        className={`${styles.navItem} ${isActive(item.path) ? styles.active : ''}`}
                        aria-label={item.label}
                        title={item.label}
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
