// src/components/Layout.jsx
import { Outlet } from 'react-router-dom';
import Header from './Header';
import Footer from './Footer';
import Sidebar from './Sidebar';
import styles from './Layout.module.css';

const Layout = ({ sidebar = true, narrow = false }) => {
    return (
        <div className={styles.wrapper}>
            <Header />
            <div className={styles.main}>
                {sidebar && <Sidebar />}
                <main className={`${styles.content} ${sidebar ? '' : styles.centered} ${narrow ? styles.narrow : ''}`}>
                    <Outlet />
                </main>
            </div>
            <Footer />
        </div>
    );
};

export default Layout;