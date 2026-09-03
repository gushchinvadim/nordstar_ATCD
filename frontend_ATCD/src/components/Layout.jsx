import { Outlet } from 'react-router-dom';
import Header from './Header';
import Footer from './Footer';
import Sidebar from './Sidebar';
import styles from './Layout.module.css';

const Layout = () => {
    return (
        <div className={styles.wrapper}>
            <Header />
            <div className={styles.main}>
                <Sidebar />
                <main className={styles.content}>
                    <Outlet />
                </main>
            </div>
            <Footer />
        </div>
    );
};

export default Layout;