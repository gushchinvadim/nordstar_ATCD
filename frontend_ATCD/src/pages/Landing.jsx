import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    Chart as ChartJS,
    CategoryScale,
    LinearScale,
    BarElement,
    Title,
    Tooltip,
    Legend,
    ArcElement,
    PointElement,
    LineElement,
    Filler,
} from 'chart.js';
import { Bar, Doughnut } from 'react-chartjs-2';
import styles from './Landing.module.css';
import api from '../api/config';

ChartJS.register(
    CategoryScale,
    LinearScale,
    BarElement,
    Title,
    Tooltip,
    Legend,
    ArcElement,
    PointElement,
    LineElement,
    Filler
);

const Landing = () => {
    const [content, setContent] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    
    // НОВЫЕ СОСТОЯНИЯ ДЛЯ СПРАВКИ
    const [showHelp, setShowHelp] = useState(false);
    const [helpData, setHelpData] = useState([]);
    const [helpLoading, setHelpLoading] = useState(false);

    const navigate = useNavigate();

    useEffect(() => {
        fetchContent();
        fetchHelpContent();
    }, []);

    const fetchContent = async () => {
        try {
            const response = await api.get('/api/landing/content/');
            setContent(response.data);
            setLoading(false);
        } catch (err) {
            console.error("Ошибка загрузки лендинга:", err);
            setError('Ошибка загрузки данных');
            setLoading(false);
        }
    };

    const fetchHelpContent = async () => {
        try {
            setHelpLoading(true);
            const response = await api.get('/api/docs/help/content/');
            setHelpData(response.data);
            setHelpLoading(false);
        } catch (err) {
            console.error("Ошибка загрузки справки:", err);
            setHelpLoading(false);
        }
    };

    if (loading) return <div className={styles.loading}>Загрузка...</div>;
    if (error) return <div className={styles.error}>{error}</div>;

    const { news, courses, stats, dynamic_stats, about, partners } = content;

    const popularCoursesChartData = {
        labels: dynamic_stats.popular_courses.map(c => c.title.length > 30 ? c.title.substring(0, 30) + '...' : c.title),
        datasets: [{
            label: 'Количество выпускников',
            data: dynamic_stats.popular_courses.map(c => c.enrollments),
            backgroundColor: 'rgba(52, 152, 219, 0.7)',
            borderColor: 'rgba(52, 152, 219, 1)',
            borderWidth: 1,
        }]
    };

    const popularCoursesChartOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { display: false },
            title: { display: true, text: 'Топ-5 популярных курсов', font: { size: 16 } }
        },
        scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } }
    };

    const monthlyChartData = {
        labels: dynamic_stats.monthly_enrollments.map(m => {
            const [year, month] = m.month.split('-');
            return `${month}.${year}`;
        }),
        datasets: [{
            label: 'Выпускников',
            data: dynamic_stats.monthly_enrollments.map(m => m.count),
            backgroundColor: [
                'rgba(46, 204, 113, 0.7)',
                'rgba(52, 152, 219, 0.7)',
                'rgba(155, 89, 182, 0.7)',
                'rgba(241, 196, 15, 0.7)',
                'rgba(230, 126, 34, 0.7)',
                'rgba(231, 76, 60, 0.7)',
            ],
            borderColor: '#fff',
            borderWidth: 2,
        }]
    };

    const monthlyChartOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { position: 'bottom' },
            title: { display: true, text: 'Выпускники по месяцам (последний год)', font: { size: 16 } }
        }
    };

    return (
        <div className={styles.landing}>
            <section className={styles.hero}>
                <div className={styles.heroContent}>
                    <h1 className={styles.heroTitle}>Авиационный Учебный Центр НордСтар</h1>
                    <p className={styles.heroSubtitle}>
                        Профессиональная подготовка авиационного персонала мирового уровня
                    </p>
                    <div className={styles.heroButtons}>
                        <button className={styles.btnPrimary} onClick={() => navigate('/login')}>
                            Войти в систему
                        </button>
                        <a href="#courses" className={styles.btnSecondary}>
                            Наши курсы
                        </a>
                        <button className={styles.btnHelp} onClick={() => setShowHelp(true)}>
                            📖 Быстрый старт
                        </button>
                    </div>
                </div>
            </section>

            <section className={styles.statsSection}>
                <div className={styles.container}>
                    <h2 className={styles.sectionTitle}>АУЦ в цифрах</h2>
                    <div className={styles.statsGrid}>
                        <div className={styles.statCard}>
                            <div className={styles.statIcon}>🎓</div>
                            <div className={styles.statValue}>{dynamic_stats.total_graduates}+</div>
                            <div className={styles.statLabel}>Выпускников</div>
                        </div>
                        <div className={styles.statCard}>
                            <div className={styles.statIcon}>📚</div>
                            <div className={styles.statValue}>{dynamic_stats.total_courses}</div>
                            <div className={styles.statLabel}>Учебных модулей</div>
                        </div>
                        <div className={styles.statCard}>
                            <div className={styles.statIcon}>👥</div>
                            <div className={styles.statValue}>{dynamic_stats.active_groups}</div>
                            <div className={styles.statLabel}>Активных групп</div>
                        </div>
                        {stats.map(stat => (
                            <div key={stat.id} className={styles.statCard}>
                                <div className={styles.statIcon}>{stat.icon}</div>
                                <div className={styles.statValue}>{stat.value}</div>
                                <div className={styles.statLabel}>{stat.title}</div>
                            </div>
                        ))}
                    </div>
                </div>
            </section>

            {about.length > 0 && (
                <section className={styles.aboutSection} id="about">
                    <div className={styles.container}>
                        <h2 className={styles.sectionTitle}>О нас</h2>
                        <div className={styles.aboutGrid}>
                            {about.map(item => (
                                <div key={item.id} className={styles.aboutCard}>
                                    <h3>{item.title}</h3>
                                    <p>{item.content}</p>
                                </div>
                            ))}
                        </div>
                    </div>
                </section>
            )}

            <section className={styles.coursesSection} id="courses">
                <div className={styles.container}>
                    <h2 className={styles.sectionTitle}>Популярные курсы</h2>
                    <div className={styles.coursesLayout}>
                        <div className={styles.chartContainer}>
                            <Bar data={popularCoursesChartData} options={popularCoursesChartOptions} />
                        </div>
                        <div className={styles.coursesList}>
                            {dynamic_stats.popular_courses.map((course, idx) => (
                                <div key={idx} className={styles.courseItem}>
                                    <div className={styles.courseRank}>#{idx + 1}</div>
                                    <div className={styles.courseInfo}>
                                        <h4>{course.title}</h4>
                                        <p className={styles.courseCode}>{course.code}</p>
                                    </div>
                                    <div className={styles.courseCount}>
                                        <span className={styles.countNumber}>{course.enrollments}</span>
                                        <span className={styles.countLabel}>выпускников</span>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            </section>

            {courses.length > 0 && (
                <section className={styles.featuredSection}>
                    <div className={styles.container}>
                        <h2 className={styles.sectionTitle}>Рекомендуемые программы</h2>
                        <div className={styles.featuredGrid}>
                            {courses.map(course => (
                                <div key={course.id} className={styles.featuredCard}>
                                    <div className={styles.featuredBadge}>⭐ Рекомендуем</div>
                                    <h3>{course.title}</h3>
                                    <p className={styles.featuredCode}>{course.code}</p>
                                    <p className={styles.featuredDesc}>{course.description}</p>
                                </div>
                            ))}
                        </div>
                    </div>
                </section>
            )}

            {dynamic_stats.monthly_enrollments.length > 0 && (
                <section className={styles.monthlySection}>
                    <div className={styles.container}>
                        <h2 className={styles.sectionTitle}>Динамика обучения</h2>
                        <div className={styles.monthlyChartWrapper}>
                            <Doughnut data={monthlyChartData} options={monthlyChartOptions} />
                        </div>
                    </div>
                </section>
            )}

            {news.length > 0 && (
                <section className={styles.newsSection}>
                    <div className={styles.container}>
                        <h2 className={styles.sectionTitle}>Новости АУЦ</h2>
                        <div className={styles.newsGrid}>
                            {news.map(item => (
                                <article key={item.id} className={styles.newsCard}>
                                    {item.image && (
                                        <img src={item.image} alt={item.title} className={styles.newsImage} />
                                    )}
                                    <div className={styles.newsContent}>
                                        <h3>{item.title}</h3>
                                        <p>{item.content.substring(0, 200)}...</p>
                                        <time className={styles.newsDate}>
                                            {new Date(item.published_at).toLocaleDateString('ru-RU')}
                                        </time>
                                    </div>
                                </article>
                            ))}
                        </div>
                    </div>
                </section>
            )}

            {partners.length > 0 && (
                <section className={styles.partnersSection}>
                    <div className={styles.container}>
                        <h2 className={styles.sectionTitle}>Наши партнеры</h2>
                        <div className={styles.partnersGrid}>
                            {partners.map(partner => (
                                <div key={partner.id} className={styles.partnerCard}>
                                    {partner.logo && <img src={partner.logo} alt={partner.name} />}
                                    <p>{partner.name}</p>
                                </div>
                            ))}
                        </div>
                    </div>
                </section>
            )}

            <section className={styles.ctaSection}>
                <div className={styles.container}>
                    <h2>Начните обучение уже сегодня</h2>
                    <p>Получите доступ к личному кабинету и отслеживайте свой прогресс</p>
                    <button className={styles.btnPrimary} onClick={() => navigate('/login')}>
                        Войти в систему
                    </button>
                </div>
            </section>

            {/* МОДАЛЬНОЕ ОКНО СПРАВКИ */}
            {showHelp && (
                <div className={styles.modalOverlay} onClick={() => setShowHelp(false)}>
                    <div className={styles.modalContent} onClick={(e) => e.stopPropagation()}>
                        <div className={styles.modalHeader}>
                            <h2> Быстрый старт ATCD</h2>
                            <button className={styles.closeBtn} onClick={() => setShowHelp(false)}>×</button>
                        </div>
                        
                        <div className={styles.modalBody}>
                            {helpLoading ? (
                                <p>Загрузка инструкции...</p>
                            ) : (
                                <div className={styles.accordion}>
                                    {helpData.map((section) => (
                                        <details key={section.id} className={styles.accordionItem}>
                                            <summary className={styles.accordionHeader}>
                                                {section.title}
                                            </summary>
                                            <div 
                                                className={styles.accordionContent}
                                                dangerouslySetInnerHTML={{ __html: section.content }} 
                                            />
                                        </details>
                                    ))}
                                </div>
                            )}
                        </div>

                        <div className={styles.modalFooter}>
                            <a 
                                href="http://127.0.0.1:8000/docs/help/pdf/" 
                                target="_blank" 
                                rel="noopener noreferrer"
                                className={styles.downloadPdfBtn}
                            >
                                 Скачать полную инструкцию (PDF)
                            </a>
                            <button className={styles.closeBtnFooter} onClick={() => setShowHelp(false)}>
                                Закрыть
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default Landing;