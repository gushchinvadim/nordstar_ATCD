// src/components/Footer.jsx
import packageJson from '../../package.json';
import styles from './Footer.module.css';

const Footer = () => {
    const currentYear = new Date().getFullYear();
    const appVersion = packageJson.version;

    return (
        <footer className={styles.footer}>
            <div className={styles.container}>
                <div className={styles.brand}>АУЦ НордСтар | ATCD</div>
                <div className={styles.info}>
                    <span className={styles.copyright}>© GVE, {currentYear}</span>
                    <span className={styles.version}>v{appVersion}</span>
                </div>
            </div>
        </footer>
    );
};

export default Footer;