// Footer.jsx
import { useContext } from 'react';
import { AuthContext } from '../context/AuthContext';
import styles from './Footer.module.css';

const Footer = () => {
    const { user, logout } = useContext(AuthContext);

    return (
        <header className={styles.footer}>
            <div className={styles.logo}>АУЦ НордСтар | ATCD</div>
            <div>
                <span style={{ marginRight: 15 }}>©️© GVE, 2026</span>

            </div>
        </header>
    );
};

export default Footer;